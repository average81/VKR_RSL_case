import cv2
import numpy as np

class BFMatcher:
    def __init__(self, feature_extractor="SIFT"):
        self.feature_extractor = feature_extractor
        if feature_extractor == "SIFT" or feature_extractor=="KAZE" or feature_extractor=="AKAZE":
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
    def match(self, kp1, features1, kp2, features2, threshold=0.75):
        # Implement feature matching
        good = []
        if len(features1) >= 2 and len(features2) >= 2:
            matches = self.flann.knnMatch(features1.astype(np.float32), features2.astype(np.float32), k=2)
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
    
    def find_nearest_neighbor(self,descriptor, descriptors):
        """Находит ближайшего соседа для заданного дескриптора."""
        min_dist = float('inf')
        nearest_idx = -1
        for i, desc in enumerate(descriptors):
            dist = self.calc_distance(descriptor, desc)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
        return nearest_idx, min_dist
    
    def is_mutual_nearest_neighbor(self, idx1, idx2, descriptors1, descriptors2):
        """
        Проверяет, являются ли две точки взаимно ближайшими соседями.
        """
        # Проверяем, что desc1[idx1] -> desc2[idx2]
        nn2_idx, _ = self.find_nearest_neighbor(descriptors1[idx1], descriptors2)
        if nn2_idx != idx2:
            return False
    
        # Проверяем, что desc2[idx2] -> desc1[idx1]
        nn1_idx, _ = self.find_nearest_neighbor(descriptors2[idx2], descriptors1)
        if nn1_idx != idx1:
            return False
    
        return True
    
    def match(self, kp1, desc1, kp2, desc2, threshold=0.75):
        """
        Выполняет симметричное взаимнооднозначное сопоставление ключевых точек.
        
        Возвращает:
        - matchesMask: маска совпадений
        - good_matches: список хороших матчей
        - oos: множество пар взаимно ближайших соседей
        """
        oos = []  # Множество пар взаимно ближайших соседей
    
        # Для каждой точки в первом изображении
        for i in range(len(desc1)):
            nn2_idx, dist1 = self.find_nearest_neighbor(desc1[i], desc2)
    
            # Проверяем условие взаимности
            if self.is_mutual_nearest_neighbor(i, nn2_idx, desc1, desc2):
                # Дополнительно применяем пороговое фильтрование по соотношению расстояний
                # Находим второго ближайшего соседа
                min_dist = float('inf')
                second_nn_idx = -1
                for j in range(len(desc2)):
                    if j != nn2_idx:
                        dist = self.calc_distance(desc1[i], desc2[j])
                        if dist < min_dist:
                            min_dist = dist
                            second_nn_idx = j
    
                if second_nn_idx != -1 and dist1 < threshold * min_dist:
                    oos.append((i, nn2_idx))
    
        # Формируем результат в формате, совместимом с существующим кодом
        good_matches = []
        for i, j in oos:
            # Создаем объект, имитирующий match от OpenCV
            match = type('Match', (), {
                'queryIdx': i,
                'trainIdx': j,
                'distance': self.calc_distance(desc1[i], desc2[j])
            })()
            good_matches.append(match)
    
        # Генерируем маску для RANSAC
        matchesMask = None
        if len(good_matches) > 10:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
    
        return matchesMask, good_matches, oos