# processor/duplicates_processor.py

from processor.feature_extractors import FeatureExtractorSIFT, FeatureExtractorORB, FeatureExtractorKAZE
from processor.feature_matchers import BFMatcher, FLANNmatcher
from processor.quality_processor import QualityProcessor



matchers = {"BF": BFMatcher, "FLANN": FLANNmatcher}
extractors = {"SIFT": FeatureExtractorSIFT, "ORB": FeatureExtractorORB, "KAZE": FeatureExtractorKAZE}

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

    def compare(self,img1,img2, threshold=0.75):
        if img1 is None or img2 is None:
            print("Error: One or both images are None")
            return 0.0
        kp1,features1 = self.feature_extractor.extract_features(img1)
        kp2,features2 = self.feature_extractor.extract_features(img2)
        self.last_kp = kp2
        self.last_features = features2
        matches = self.matcher.match(kp1,features1,kp2,features2,threshold)
        if matches is not None:
            if len(matches) > 10:
                return sum(matches) / len(matches)
            else:
                return 0.0
        return 0.0
    def compare_w_last(self,img2,threshold=0.75):
        if self.last_kp is None or self.last_features is None:
            print("Error: No last features available")
            return None
        else:
            if img2 is None:
                print("Error: Image is None")
                return None
        kp1 = self.last_kp
        features1 = self.last_features
        kp2,features2 = self.feature_extractor.extract_features(img2)
        self.last_kp = kp2
        self.last_features = features2
        matches = self.matcher.match(kp1,features1,kp2,features2,threshold)
        if matches is not None:
            if len(matches) > 10:
                return sum(matches) / len(matches)
            else:
                return 0
        return 0
    #Сравнение изображений по качеству и возврат наилучшего
    def get_best_quality_image(self, imgs):
        if imgs is None:
            print("Error: One or both images are None")
            return 0
        else:
            return self.quality_processor.compare(imgs)