# processor/duplicates_processor.py
import cv2
import numpy as np



class FeatureExtractorSIFT:
    def __init__(self):
        self.sift = cv2.SIFT_create()
    def extract_features(self, image):
        # Implement SIFT feature extraction
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, des = self.sift.detectAndCompute(grey, None)
        return kp,des

class FeatureExtractorORB:
    def __init__(self):
        self.orb = cv2.ORB_create()
    def extract_features(self, image):
        # Implement ORB feature extraction
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, des = self.orb.detectAndCompute(grey, None)
        return kp,des

class BFMatcher:
    def __init__(self, feature_extractor="SIFT"):
        self.feature_extractor = feature_extractor
        if feature_extractor == "SIFT":
            params = dict(normType = cv2.NORM_L2)
        else:
            params = dict(normType = cv2.NORM_HAMMING, crossCheck=True)
        self.bf = cv2.BFMatcher(**params)
    def match(self, kp1, features1, kp2, features2, threshold=0.75):
        # Implement feature matching
        if len(features1) >= 2 and len(features2) >= 2:

            if self.feature_extractor == "SIFT":
                matches = self.bf.knnMatch(features1, features2, k=2)
            else:
                matches = self.bf.match(features1, features2)

            # Фильтрация признаков
            good = []
            for match in matches:
                if self.feature_extractor == "SIFT":
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
        return matchesMask

class FLANN:
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
        return matchesMask

matchers = {"BF": BFMatcher, "FLANN": FLANN}
extractors = {"SIFT": FeatureExtractorSIFT, "ORB": FeatureExtractorORB}

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

    def compare(self,img1,img2, threshold=0.75):
        if img1 is None or img2 is None:
            print("Error: One or both images are None")
            return 0
        kp1,features1 = self.feature_extractor.extract_features(img1)
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