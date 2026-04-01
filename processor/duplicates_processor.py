# processor/duplicates_processor.py

from processor.feature_extractors import FeatureExtractorSIFT, FeatureExtractorORB, FeatureExtractorKAZE, FeatureExtractorAKAZE
from processor.feature_matchers import BFMatcher, FLANNmatcher
from processor.quality_processor import QualityProcessor


matchers = {"BF": BFMatcher, "FLANN": FLANNmatcher}
extractors = {"SIFT": FeatureExtractorSIFT, "ORB": FeatureExtractorORB, "KAZE": FeatureExtractorKAZE, "AKAZE": FeatureExtractorAKAZE}

class DuplicatesProcessor:
    def __init__(self, feature_extractor="SIFT", matcher_type="BF"):
        if feature_extractor not in extractors:
            feature_extractor="SIFT"
            self.feature_extractor = FeatureExtractorSIFT()
        else:
            self.feature_extractor = extractors[feature_extractor]()
        if matcher_type not in matchers:
            self.matcher = BFMatcher(feature_extractor)
        else:
            self.matcher = matchers[matcher_type](feature_extractor)
        self.last_kp = None
        self.last_features = None
        self.quality_processor = QualityProcessor()

    def compare_features(self, kp1, features1, kp2, features2, threshold=0.75):
        """
        Метод сравнения двух наборов ключевых точек и дескрипторов.
        
        Параметры:
        - kp1, features1: ключевые точки и дескрипторы первого изображения
        - kp2, features2: ключевые точки и дескрипторы второго изображения
        - threshold: порог фильтрации матчей
        
        Возвращает:
        - Среднее значение совпадений (0.0–1.0) или 0.0 при отсутствии совпадений
        """
        if kp1 is None or features1 is None or kp2 is None or features2 is None:
            print("Error: One or more feature sets are None")
            return 0.0
            
        matches, good = self.matcher.match(kp1, features1, kp2, features2, threshold)

        if matches is not None and len(matches) > 10:
            return sum(matches) / len(matches)
        return 0.0
        
    def compare(self, img1, img2, threshold=0.75):
        """
        Сравнивает два изображения по их визуальному сходству.
        
        Параметры:
        - img1, img2: изображения в формате numpy array
        - threshold: порог фильтрации матчей
        
        Возвращает:
        - Среднее значение совпадений (0.0–1.0) или 0.0 при отсутствии совпадений
        """
        if img1 is None or img2 is None:
            print("Error: One or both images are None")
            return 0.0
            
        kp1, features1 = self.feature_extractor.extract_features(img1)
        kp2, features2 = self.feature_extractor.extract_features(img2)
        self.last_kp = kp2
        self.last_features = features2
        
        return self.compare_features(kp1, features1, kp2, features2, threshold)
    def compare_w_last(self, img2, threshold=0.75):
        """
        Сравнивает изображение с последним обработанным изображением.
        
        Параметры:
        - img2: изображение для сравнения (numpy array)
        - threshold: порог фильтрации матчей
        
        Возвращает:
        - Среднее значение совпадений (0.0–1.0) или 0.0 при отсутствии совпадений
        """
        if self.last_kp is None or self.last_features is None:
            print("Error: No last features available")
            return 0.0
            
        if img2 is None:
            print("Error: Image is None")
            return 0.0
            
        kp2, features2 = self.feature_extractor.extract_features(img2)
        current_kp, current_features = kp2, features2
        
        # Сохраняем текущие признаки для следующего сравнения
        self.last_kp = current_kp
        self.last_features = current_features
        
        # Используем общий метод сравнения фич
        return self.compare_features(self.last_kp, self.last_features, current_kp, current_features, threshold)
    #Сравнение изображений по качеству и возврат наилучшего
    def get_best_quality_image(self, imgs):
        if imgs is None:
            print("Error: One or both images are None")
            return 0
        else:
            return self.quality_processor.compare(imgs)

    def compare_with_features(self, img, kp1, features1, threshold=0.75):
        """
        Сравнивает изображение с предоставленными ключевыми точками и дескрипторами другого изображения.
        
        Параметры:
        - img: текущее изображение (numpy array)
        - kp1: ключевые точки первого изображения
        - features1: дескрипторы первого изображения
        - threshold: порог фильтрации матчей
        
        Возвращает:
        - Среднее значение совпадений (0.0–1.0) или 0.0 при отсутствии совпадений
        """
        if img is None or kp1 is None or features1 is None:
            print("Error: Image or features are None")
            return 0.0
            
        kp2, features2 = self.feature_extractor.extract_features(img)
        
        # Используем общий метод сравнения фич
        return self.compare_features(kp1, features1, kp2, features2, threshold)