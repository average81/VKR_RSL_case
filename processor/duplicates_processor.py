# processor/duplicates_processor.py

from processor.feature_extractors import FeatureExtractorSIFT, FeatureExtractorORB, FeatureExtractorKAZE, FeatureExtractorAKAZE, FeatureExtractorDISK
from processor.feature_matchers import BFMatcher, FLANNmatcher,SymmetricMatcher,SymmetricAdalamMatcher
from processor.quality_processor import QualityProcessor_brisque


matchers = {"BF": BFMatcher, "FLANN": FLANNmatcher, "SM": SymmetricMatcher,"SMADALAM":SymmetricAdalamMatcher}
extractors = {"SIFT": FeatureExtractorSIFT, "ORB": FeatureExtractorORB, "KAZE": FeatureExtractorKAZE,
              "AKAZE": FeatureExtractorAKAZE,"DISK":FeatureExtractorDISK}
quality_methods = {"BRISQUE": QualityProcessor_brisque}

class DuplicatesProcessor:
    def __init__(self, feature_extractor="SIFT",nfeatures = 20000, matcher_type="BF", quality_method = "BRISQUE"):
        if feature_extractor not in extractors:
            feature_extractor="SIFT"
            self.feature_extractor = FeatureExtractorSIFT()
        else:
            if feature_extractor == "DISK":
                self.feature_extractor = extractors[feature_extractor](matcher = matcher_type)
            else:
                self.feature_extractor = extractors[feature_extractor](nfeatures=nfeatures)
        if matcher_type not in matchers:
            self.matcher = BFMatcher(feature_extractor)
        else:
            self.matcher = matchers[matcher_type](feature_extractor)
        self.last_kp = None
        self.last_features = None
        if quality_method in quality_methods.keys():
            self.quality_processor = quality_methods[quality_method]()
        else:
            self.quality_processor = QualityProcessor_brisque()


    def compare_features(self, kp1, features1, kp2, features2, hw1, hw2, threshold=0.75):
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
            
        matches, good = self.matcher.match(kp1, features1, kp2, features2, hw1, hw2, threshold)

        if matches is not None and len(matches) > 5:
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
        self.last_hw = img2.shape[:2]

        return self.compare_features(kp1, features1, kp2, features2, img1.shape[:2], img2.shape[:2], threshold)
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
        kp1 = self.last_kp
        features1 = self.last_features
        hw1 = self.last_hw
        kp2, features2 = self.feature_extractor.extract_features(img2)
        
        # Сохраняем текущие признаки для следующего сравнения
        self.last_kp = kp2
        self.last_features = features2
        self.last_hw = img2.shape[:2]
        
        # Используем общий метод сравнения фич
        return self.compare_features(kp1, features1, kp2, features2, hw1, img2.shape[:2], threshold)
    #Сравнение изображений по качеству и возврат наилучшего
    def get_best_quality_image(self, imgs):
        if imgs is None:
            print("Error: One or both images are None")
            return 0
        else:
            return self.quality_processor.compare(imgs)

    def compare_with_features(self, img, kp1, features1, hw1, threshold=0.75):
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
        hw2 = img.shape[:2]
        
        # Используем общий метод сравнения фич
        return self.compare_features(kp1, features1, kp2, features2, hw1, hw2, threshold)