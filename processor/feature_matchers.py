import cv2
import numpy as np
import torch
from multiprocessing import Pool, cpu_count
import multiprocessing
from functools import partial
import kornia

class BFMatcher:
    def __init__(self, feature_extractor="SIFT"):
        self.feature_extractor = feature_extractor
        if feature_extractor == "SIFT" or feature_extractor=="KAZE" or feature_extractor=="AKAZE" or \
                feature_extractor=="DISK":
            params = dict(normType = cv2.NORM_L2)
        else:
            params = dict(normType = cv2.NORM_HAMMING, crossCheck=True)
        self.bf = cv2.BFMatcher(**params)
    def match(self, kp1, features1, kp2, features2, threshold=0.75):
        # Implement feature matching
        if features1 is None or features2 is None:
            return None, []
        good = []
        if features1.size >= 2 and features2.size >= 2:

            if self.feature_extractor in ("SIFT", "KAZE", "AKAZE"):
                matches = self.bf.knnMatch(features1, features2, k=2)
            else:
                matches = self.bf.match(features1, features2)

            # Фильтрация признаков

            for match in matches:
                if self.feature_extractor in ("SIFT", "KAZE", "AKAZE"):
                    if len(match) == 2:
                        m, n = match
                        if m.distance < threshold * n.distance:
                            good.append(m)
                else:
                    good.append(match)
        # Сравнение изображений
        matchesMask = None
        if len(good) > 10:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        return matchesMask, good

class FLANNmatcher:
    def __init__(self, feature_extractor="SIFT"):
        if feature_extractor == "ORB":
            index_params = dict(algorithm=6, table_number=6, key_size=12, multi_probe_level=1)
        else:
            index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=50)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)
        self.feature_extractor = feature_extractor
    def match(self, kp1, features1, kp2, features2, threshold=0.75):
        # Implement feature matching
        good = []
        if len(features1) >= 2 and len(features2) >= 2:
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
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        return matchesMask, good
# Согласно  Пименов В.Ю., Метод поиска нечетких дубликатов
# изображений на основе выявления
# точечных особенностей, 2008
class SymmetricMatcher():
    def __init__(self, feature_extractor="SIFT"):
        self.feature_extractor = feature_extractor
        if feature_extractor  in ("SIFT", "KAZE", "AKAZE"):
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
    
    def match(self, kp1, desc1, kp2, desc2, threshold=0.95):
        """
        Выполняет симметричное взаимнооднозначное сопоставление ключевых точек
        с использованием kornia.feature.match_smnn.
        
        Возвращает:
        - matchesMask: маска совпадений
        - good_matches: список хороших матчей
        """
        if desc1 is None or desc2 is None or len(desc1) == 0 or len(desc2) == 0:
            return None, []

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
                    if self.feature_extractor == "SIFT":
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
        if torch.cuda.is_available():
            desc1_t = desc1_t.cuda()
            desc2_t = desc2_t.cuda()
        
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
            if torch.cuda.is_available():
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
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            else:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        
        return matchesMask, good_matches