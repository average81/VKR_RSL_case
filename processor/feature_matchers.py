import cv2
import numpy as np
from multiprocessing import Pool, cpu_count
import multiprocessing
from functools import partial

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
    
    def find_nearest_neighbor(self, descriptor, descriptors):
        """Находит ближайшего соседа для заданного дескриптора."""
        if len(descriptors) == 0:
            return -1, float('inf')
        
        # Векторизованное вычисление расстояний
        distances = np.array([self.calc_distance(descriptor, desc) for desc in descriptors])
        nearest_idx = np.argmin(distances)
        min_dist = distances[nearest_idx]
        return nearest_idx, min_dist
    
    def is_mutual_nearest_neighbor(self, idx1, idx2, descriptors1, descriptors2):
        """
        Проверяет, являются ли две точки взаимно ближайшими соседями.
        """
        if idx1 >= len(descriptors1) or idx2 >= len(descriptors2):
            return False
            
        # Получаем дескрипторы
        desc1 = descriptors1[idx1]
        desc2 = descriptors2[idx2]
        
        # Векторизованное вычисление расстояний
        dists1_to_2 = np.array([self.calc_distance(desc1, desc) for desc in descriptors2])
        dists2_to_1 = np.array([self.calc_distance(desc2, desc) for desc in descriptors1])
        
        # Проверяем взаимность
        nn2_idx = np.argmin(dists1_to_2)
        nn1_idx = np.argmin(dists2_to_1)
        
        return nn2_idx == idx2 and nn1_idx == idx1
    
    def match(self, kp1, desc1, kp2, desc2, threshold=0.75):
        """
        Выполняет симметричное взаимнооднозначное сопоставление ключевых точек.
        
        Возвращает:
        - matchesMask: маска совпадений
        - good_matches: список хороших матчей
        - oos: множество пар взаимно ближайших соседей
        """
        if desc1 is None or desc2 is None or len(desc1) == 0 or len(desc2) == 0:
            return None, [], []
            
        oos = []  # Множество пар взаимно ближайших соседей
        
        # Преобразуем дескрипторы в numpy массивы
        desc1_array = np.array(desc1)
        desc2_array = np.array(desc2)
        
        # Оптимизация по памяти: обработка по блокам
        block_size = 500  # Размер блока для обработки
        n1, n2 = len(desc1), len(desc2)
        
        # Предварительная инициализация для поиска ближайших соседей
        nn2_indices = np.zeros(n1, dtype=int)
        nn1_distances = np.full(n2, np.inf)
        nn1_indices = np.zeros(n2, dtype=int)
        
        # Обработка по блокам для поиска ближайших соседей из второго изображения
        for i in range(0, n1, block_size):
            end_i = min(i + block_size, n1)
            block1 = desc1_array[i:end_i]
            
            if self.feature_extractor in ("SIFT", "KAZE", "AKAZE"):
                # Euclidean расстояние
                block_distances = np.linalg.norm(block1[:, np.newaxis] - desc2_array, axis=2)
            else:
                # Hamming расстояние
                if desc1_array.dtype != np.uint8:
                    block1 = (block1 > 0).astype(np.uint8)
                if desc2_array.dtype != np.uint8:
                    desc2_array_local = (desc2_array > 0).astype(np.uint8)
                else:
                    desc2_array_local = desc2_array
                xor_block = block1[:, np.newaxis] ^ desc2_array_local
                block_distances = np.count_nonzero(xor_block, axis=2)
            
            # Находим ближайших соседей в блоке
            block_nn2 = np.argmin(block_distances, axis=1)
            nn2_indices[i:end_i] = block_nn2
            
            # Обновляем ближайших соседей из первого изображения
            for j in range(n2):
                col_distances = block_distances[:, j]
                col_indices = np.argmin(col_distances)
                if col_distances[col_indices] < nn1_distances[j]:
                    nn1_distances[j] = col_distances[col_indices]
                    nn1_indices[j] = col_indices + i  # Смещение индекса
        
        # Параллельная проверка взаимности для всех пар
        def check_mutual_nn(i):
            j = nn2_indices[i]
            if nn1_indices[j] != i:  # Нет взаимности
                return None
                
            # Находим второе минимальное расстояние (кроме текущего)
            if self.feature_extractor in ("SIFT", "KAZE", "AKAZE"):
                # Для Euclidean расстояния используем broadcasting
                dist_i = np.linalg.norm(desc1_array[i] - desc2_array, axis=1)
            else:
                # Для Hamming расстояния используем broadcasting
                d1 = desc1_array[i]
                if d1.dtype != np.uint8:
                    d1 = (d1 > 0).astype(np.uint8)
                if desc2_array.dtype != np.uint8:
                    d2_array = (desc2_array > 0).astype(np.uint8)
                else:
                    d2_array = desc2_array
                # Вычисляем XOR для всех дескрипторов
                xor_result = d1 ^ d2_array
                # Считаем количество единиц для каждого дескриптора
                dist_i = np.count_nonzero(xor_result, axis=1)
            
            # Удаляем текущее расстояние и находим второе минимальное
            dist_i_without_j = np.delete(dist_i, j)
            if len(dist_i_without_j) > 0:
                second_min_dist = np.min(dist_i_without_j)
                if dist_i[j] < threshold * second_min_dist:
                    return (i, j)
            return None

        # Используем multiprocessing для параллельной обработки
        num_processes = min(cpu_count(), 4)  # Ограничиваем количество процессов
        with Pool(processes=num_processes) as pool:
            results = pool.map(check_mutual_nn, range(n1))
            
        # Собираем результаты
        oos = [result for result in results if result is not None]
    
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
        if len(good_matches) > 5:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
    
        return matchesMask, good_matches