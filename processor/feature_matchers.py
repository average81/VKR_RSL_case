import cv2
import numpy as np
import torch
from multiprocessing import Pool, cpu_count
import multiprocessing
from functools import partial
import kornia
from kornia.feature.adalam import AdalamFilter
from kornia_moons import feature as KM


class BFMatcher:
    def __init__(self, feature_extractor="SIFT", kp_type="KP_CV", device="cpu"):
        self.feature_extractor = feature_extractor
        self.kp_type = kp_type
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device("cpu")
        if feature_extractor in ("SIFT", "KORNIA_SIFT", "KAZE", "AKAZE", "DISK"):
            params = dict(normType = cv2.NORM_L2)
        else:
            params = dict(normType = cv2.NORM_HAMMING, crossCheck=True)
        self.bf = cv2.BFMatcher(**params)
    
    def match(self, kp1, features1, kp2, features2, hw1, hw2, threshold=0.75):
        # Convert LAF format to OpenCV keypoints if needed
        if self.kp_type == "LAF":
            kp1 = kp1[0][0][:,:,2]
            kp2 = kp2[0][0][:,:,2]
            #Преобразуем тензоры features в numpy и убираем batch ось
            features1 = features1.detach().cpu().numpy().squeeze(0)
            features2 = features2.detach().cpu().numpy().squeeze(0)
        
        # Implement feature matching
        if features1 is None or features2 is None:
            return None, []
        good = []
        if features1.size >= 2 and features2.size >= 2:

            if self.feature_extractor in ("SIFT", "KAZE", "AKAZE", "KORNIA_SIFT"):
                matches = self.bf.knnMatch(features1, features2, k=2)
            else:
                matches = self.bf.match(features1, features2)

            # Фильтрация признаков

            for match in matches:
                if self.feature_extractor in ("SIFT", "KAZE", "AKAZE", "KORNIA_SIFT"):
                    if len(match) == 2:
                        m, n = match
                        if m.distance < threshold * n.distance:
                            good.append(m)
                else:
                    good.append(match)
        # Сравнение изображений
        matchesMask = None
        if len(good) > 10:
            if torch.is_tensor(kp1) and torch.is_tensor(kp2):
                src_pts = np.float32([kp1[m.queryIdx].cpu().detach().numpy() for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].cpu().detach().numpy() for m in good]).reshape(-1, 1, 2)
                if self.device.type == "cuda":
                    torch.cuda.empty_cache()
            else:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        return matchesMask, good


class FLANNmatcher:
    def __init__(self, feature_extractor="SIFT", kp_type="KP_CV", device="cpu"):
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device("cpu")
        if feature_extractor == "ORB":
            index_params = dict(algorithm=6, table_number=6, key_size=12, multi_probe_level=1)
        else:
            index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=50)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)
        self.feature_extractor = feature_extractor
        self.kp_type = kp_type
    
    def match(self, kp1, features1, kp2, features2, hw1, hw2, threshold=0.75):
        # Convert LAF format to OpenCV keypoints if needed
        if self.kp_type == "LAF":
            kp1 = kp1[0][0][:,:,2]
            kp2 = kp2[0][0][:,:,2]
            #Преобразуем тензоры features в numpy и убираем batch ось
            features1 = features1.detach().cpu().numpy().squeeze(0)
            features2 = features2.detach().cpu().numpy().squeeze(0)
        # Implement feature matching
        if features1 is None or features2 is None:
            return None, []
        # Implement feature matching
        good = []
        if features1.size >= 2 and features2.size >= 2:
            if self.feature_extractor == "AKAZE":
                matches = self.flann.knnMatch(features1.astype(np.float32), features2.astype(np.float32), k=2)
            else:
                matches = self.flann.knnMatch(features1, features2, k=2)
            for match in matches:
                if len(match) == 2:
                    m, n = match
                    if m.distance < threshold * n.distance:
                        good.append(m)
        matchesMask = None
        if len(good) > 10:
            if torch.is_tensor(kp1) and torch.is_tensor(kp2):
                src_pts = np.float32([kp1[m.queryIdx].cpu().detach().numpy() for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].cpu().detach().numpy() for m in good]).reshape(-1, 1, 2)
                if self.device.type == "cuda":
                    torch.cuda.empty_cache()
            else:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        return matchesMask, good


# Согласно  Пименов В.Ю., Метод поиска нечетких дубликатов
# изображений на основе выявления
# точечных особенностей, 2008
class SymmetricMatcher():
    def __init__(self, feature_extractor="SIFT", kp_type="KP_CV", device="cpu"):
        self.feature_extractor = feature_extractor
        self.kp_type = kp_type
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device("cpu")
        if feature_extractor  in ("SIFT", "KAZE", "AKAZE","KORNIA_SIFT"):
            self.calc_distance = self.euclidean_distance
        else:
            self.calc_distance = self.hamming_distance
    
    def euclidean_distance(self,desc1, desc2):
        """Вычисляет евклидово расстояние между двумя дескрипторами."""
        return np.linalg.norm(desc1 - desc2)

    def hamming_distance(self,desc1, desc2):
        """Вычисляет расстояние Хэмминга между двумя дескрипторами."""
        # Преобразуем дескрипторы в бинарный формат, если они не являются таковыми
        if desc1.dtype != np.uint8:
            desc1 = (desc1 > 0).astype(np.uint8)
        if desc2.dtype != np.uint8:
            desc2 = (desc2 > 0).astype(np.uint8)
            
        # Вычисляем расстояние Хэмминга с использованием XOR и подсчета единиц
        xor_result = desc1 ^ desc2
        hamming_dist = np.count_nonzero(xor_result)
        return hamming_dist
    
    def match(self, kp1, desc1, kp2, desc2, hw1, hw2, threshold=0.95):
        """
        Выполняет симметричное взаимнооднозначное сопоставление ключевых точек
        с использованием kornia.feature.match_smnn.
        
        Возвращает:
        - matchesMask: маска совпадений
        - good_matches: список хороших матчей
        """
        if desc1 is None or desc2 is None or len(desc1) == 0 or len(desc2) == 0:
            return None, []

        # Преобразуем в KP_CV формат если нужно
        if self.kp_type == "LAF":
            kp1 = kp1[0][0][:,:,2]
            kp2 = kp2[0][0][:,:,2]
            desc1 = desc1.squeeze(0).float()
            desc2 = desc2.squeeze(0).float()
        # Проверяем, являются ли входные дескрипторы уже тензорами
        if torch.is_tensor(desc1) and torch.is_tensor(desc2):
            # Если оба дескриптора уже тензоры, используем их напрямую
            desc1_t = desc1
            desc2_t = desc2
            desc1 = desc1.cpu().detach().numpy()
            desc2 = desc2.cpu().detach().numpy()
        else:
            # Преобразуем дескрипторы в numpy массивы, если они еще не являются тензорами
            if torch.is_tensor(desc1):
                desc1_np = desc1.cpu().numpy()
            else:
                desc1_np = np.array(desc1)
                
            if torch.is_tensor(desc2):
                desc2_np = desc2.cpu().numpy()
            else:
                desc2_np = np.array(desc2)
            
            # Проверяем и корректируем форму данных в соответствии с ожидаемым форматом (B, D)
            if desc1_np.ndim == 1:
                # Одномерный массив - считаем его как B векторов размерности 1
                if desc1_np.size == 1:
                    desc1_np = desc1_np.reshape(-1, 1)  # (1, 1)
                else:
                    # Для дескрипторов вроде SIFT, ORB - считаем что это N векторов размерности D
                    # Определяем размерность D как 128 для SIFT, 32 для ORB, иначе 64
                    if self.feature_extractor in( "SIFT","DISK", "KORNIA_SIFT"):
                        D = 128
                    elif self.feature_extractor == "ORB":
                        D = 32
                    else:
                        D = 64
                        
                    # Если размер кратен D, считаем что это N x D
                    if desc1_np.size % D == 0:
                        desc1_np = desc1_np.reshape(-1, D)
                    else:
                        # Иначе считаем что это N векторов размерности 1
                        desc1_np = desc1_np.reshape(-1, 1)
                        
            elif desc1_np.ndim == 2:
                # Двумерный массив
                if desc1_np.shape[0] == 1 and desc1_np.shape[1] > 1:
                    # Одна строка - транспонируем для получения (N, D)
                    desc1_np = desc1_np.T

            if desc2_np.ndim == 1:
                # Одномерный массив - аналогично
                if desc2_np.size == 1:
                    desc2_np = desc2_np.reshape(-1, 1)
                else:
                    if self.feature_extractor in("SIFT", "KORNIA_SIFT"):
                        D = 128
                    elif self.feature_extractor == "ORB":
                        D = 32
                    else:
                        D = 64
                        
                    if desc2_np.size % D == 0:
                        desc2_np = desc2_np.reshape(-1, D)
                    else:
                        desc2_np = desc2_np.reshape(-1, 1)
                        
            elif desc2_np.ndim == 2:
                if desc2_np.shape[0] == 1 and desc2_np.shape[1] > 1:
                    desc2_np = desc2_np.T
                    
            # Преобразуем в тензоры
            desc1_t = torch.from_numpy(desc1_np).float()
            desc2_t = torch.from_numpy(desc2_np).float()
        
        # Перемещаем тензоры на GPU, если доступен
        desc1_t = desc1_t.to(self.device)
        desc2_t = desc2_t.to(self.device)
        
        # Используем kornia для сопоставления симметричных ближайших соседей
        try:
            matches = kornia.feature.match_smnn(desc1_t, desc2_t, threshold)
            
            # Проверяем результат согласно документации
            # match_smnn возвращает кортеж (distances, indices)
            if not isinstance(matches, tuple) or len(matches) != 2:
                return None, []
                
            distances, indices = matches
            
            # Проверяем, что indices имеет форму (B3, 2)
            if not torch.is_tensor(indices) or indices.ndim != 2 or indices.shape[1] != 2:
                return None, []
                
            # Перемещаем индексы обратно на CPU и преобразуем в numpy массив
            matches_indices = indices.cpu().numpy()
            
            # Очистка памяти GPU
            del desc1_t, desc2_t, distances, indices
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        except Exception as e:
            print(f"Kornia matching error: {e}")
            return None, []
        
        # Формируем список совпадений в формате OpenCV
        good_matches = []
        for idx1, idx2 in matches_indices:
            # Проверяем валидность индексов
            idx1, idx2 = int(idx1), int(idx2)
            if 0 <= idx1 < len(desc1) and 0 <= idx2 < len(desc2):
                match = type('Match', (), {
                    'queryIdx': idx1,
                    'trainIdx': idx2,
                    'distance': float(self.calc_distance(desc1[idx1], desc2[idx2]))
                })()
                good_matches.append(match)
        
        # Генерируем маску для RANSAC
        matchesMask = None
        if len(good_matches) > 5:
            if torch.is_tensor(kp1) and torch.is_tensor(kp2):
                src_pts = np.float32([kp1[m.queryIdx].cpu().detach().numpy() for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].cpu().detach().numpy() for m in good_matches]).reshape(-1, 1, 2)
                if self.device.type == "cuda":
                    torch.cuda.empty_cache()
            else:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        
        return matchesMask, good_matches


class SymmetricAdalamMatcher():
    def __init__(self, feature_extractor="SIFT", kp_type="KP_CV", device="cpu"):
        self.feature_extractor = feature_extractor
        self.kp_type = kp_type
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device("cpu")
        self.feature_extractor = feature_extractor

    def match(self, kp1, desc1, kp2, desc2, hw1,hw2,threshold=0.95):
        """
        Выполняет симметричное взаимнооднозначное сопоставление ключевых точек
        с использованием kornia.feature.match_adalam.

        Возвращает:
        - matchesMask: маска совпадений
        - good_matches: список хороших матчей
        """
        adalam_config = kornia.feature.adalam.get_adalam_default_config()
        # adalam_config['orientation_difference_threshold'] = None
        # adalam_config['scale_rate_threshold'] = None
        adalam_config["force_seed_mnn"] = False
        adalam_config["search_expansion"] = 16
        adalam_config["ransac_iters"] = 256

        if desc1 is None or desc2 is None or len(desc1) == 0 or len(desc2) == 0:
            return None, []

        # Преобразуем в KP_CV формат если нужно
        if self.kp_type == "LAF":
            desc1 = desc1.squeeze(0).float()
            desc2 = desc2.squeeze(0).float()
        # Проверяем, являются ли входные дескрипторы уже тензорами
        if torch.is_tensor(desc1) and torch.is_tensor(desc2):
            # Если оба дескриптора уже тензоры, используем их напрямую
            desc1_t = desc1
            desc2_t = desc2
            desc1 = desc1.cpu().detach().numpy()
            desc2 = desc2.cpu().detach().numpy()
        else:
            # Преобразуем дескрипторы в numpy массивы, если они еще не являются тензорами
            if torch.is_tensor(desc1):
                desc1_np = desc1.cpu().numpy()
            else:
                desc1_np = np.array(desc1)

            if torch.is_tensor(desc2):
                desc2_np = desc2.cpu().numpy()
            else:
                desc2_np = np.array(desc2)

            # Проверяем и корректируем форму данных в соответствии с ожидаемым форматом (B, D)
            if desc1_np.ndim == 1:
                # Одномерный массив - считаем его как B векторов размерности 1
                if desc1_np.size == 1:
                    desc1_np = desc1_np.reshape(-1, 1)  # (1, 1)
                else:
                    # Для дескрипторов вроде SIFT, ORB - считаем что это N векторов размерности D
                    # Определяем размерность D как 128 для SIFT, 32 для ORB, иначе 64
                    if self.feature_extractor == "SIFT" or self.feature_extractor == "DISK":
                        D = 128
                    elif self.feature_extractor == "ORB":
                        D = 32
                    else:
                        D = 64

                    # Если размер кратен D, считаем что это N x D
                    if desc1_np.size % D == 0:
                        desc1_np = desc1_np.reshape(-1, D)
                    else:
                        # Иначе считаем что это N векторов размерности 1
                        desc1_np = desc1_np.reshape(-1, 1)

            elif desc1_np.ndim == 2:
                # Двумерный массив
                if desc1_np.shape[0] == 1 and desc1_np.shape[1] > 1:
                    # Одна строка - транспонируем для получения (N, D)
                    desc1_np = desc1_np.T

            if desc2_np.ndim == 1:
                # Одномерный массив - аналогично
                if desc2_np.size == 1:
                    desc2_np = desc2_np.reshape(-1, 1)
                else:
                    if self.feature_extractor in("SIFT", "KORNIA_SIFT"):
                        D = 128
                    elif self.feature_extractor == "ORB":
                        D = 32
                    else:
                        D = 64

                    if desc2_np.size % D == 0:
                        desc2_np = desc2_np.reshape(-1, D)
                    else:
                        desc2_np = desc2_np.reshape(-1, 1)

            elif desc2_np.ndim == 2:
                if desc2_np.shape[0] == 1 and desc2_np.shape[1] > 1:
                    desc2_np = desc2_np.T

            # Преобразуем в тензоры
            desc1_t = torch.from_numpy(desc1_np).float()
            desc2_t = torch.from_numpy(desc2_np).float()

        # Обработка ключевых точек для формата LAF
        # kornia.feature.laf_from_center_scale_ori ожидает xy с форматом (B, N, 2)
        if self.kp_type == "LAF" and isinstance(kp1, tuple):
            # kp1 - это (lafs, responses), используем lafs напрямую
            lafs1 = kp1[0]
            lafs2 = kp2[0]


        # Перемещаем тензоры на GPU, если доступен
        desc1_t = desc1_t.to(self.device)
        desc2_t = desc2_t.to(self.device)

        # Используем kornia для сопоставления с Adalam
        try:
            if self.kp_type == "LAF" and isinstance(kp1, tuple):
                # Используем LAFs напрямую для Adalam
                hw1_tensor = torch.tensor(hw1, device=self.device)
                hw2_tensor = torch.tensor(hw2, device=self.device)
                matches = kornia.feature.match_adalam(desc1_t, desc2_t, lafs1, lafs2, 
                                                      hw1=hw1_tensor, hw2=hw2_tensor, 
                                                      config=adalam_config)

            else:
                # Создаём LAFs из ключевых точек
                if self.feature_extractor in ("SIFT", "KORNIA_SIFT"):
                    lafs1 = KM.laf_from_opencv_SIFT_kpts(kp1, device=self.device)
                    lafs2 = KM.laf_from_opencv_SIFT_kpts(kp2, device=self.device)
                elif self.feature_extractor == "ORB":
                    lafs1 = KM.laf_from_opencv_ORB_kpts(kp1, device=self.device)
                    lafs2 = KM.laf_from_opencv_ORB_kpts(kp2, device=self.device)
                else:
                    lafs1 = KM.laf_from_opencv_kpts(kp1, mrSize = 1.0, device=self.device)
                    lafs2 = KM.laf_from_opencv_kpts(kp2, mrSize = 1.0, device=self.device)

                hw1_tensor = torch.tensor(hw1, device=self.device)
                hw2_tensor = torch.tensor(hw2, device=self.device)
                matches = kornia.feature.match_adalam(desc1_t, desc2_t, lafs1, lafs2, 
                                                      hw1=hw1_tensor, hw2=hw2_tensor, 
                                                      config=adalam_config)

            # Проверяем результат согласно документации
            # match_adalam возвращает кортеж (distances, indices)
            if not isinstance(matches, tuple) or len(matches) != 2:
                return None, []

            distances, indices = matches

            # Проверяем, что indices имеет форму (B3, 2)
            if not torch.is_tensor(indices) or indices.ndim != 2 or indices.shape[1] != 2:
                return None, []

            # Перемещаем индексы обратно на CPU и преобразуем в numpy массив
            matches_indices = indices.cpu().numpy()

            # Очистка памяти GPU
            del desc1_t, desc2_t
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        except Exception as e:
            print(f"Kornia matching error: {e}")
            return None, []

        # Формируем список совпадений в формате OpenCV
        good_matches = []
        for id, (idx1, idx2) in enumerate(matches_indices):
            # Проверяем валидность индексов
            idx1, idx2 = int(idx1), int(idx2)
            if 0 <= idx1 < len(desc1) and 0 <= idx2 < len(desc2):
                match = type('Match', (), {
                    'queryIdx': idx1,
                    'trainIdx': idx2,
                    'distance': distances[id]
                })()
                good_matches.append(match)

        # Генерируем маску для RANSAC
        matchesMask = None
        if len(good_matches) > 5:
            src_pts = lafs1[0][:,:,2]
            dst_pts = lafs2[0][:,:,2]
            src_pts = np.float32([src_pts.cpu().detach().numpy()[m.queryIdx] for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([dst_pts.cpu().detach().numpy()[m.trainIdx] for m in good_matches]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        return matchesMask, good_matches
