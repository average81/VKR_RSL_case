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

class BFMatcher:
    def match(self, kp1, features1, kp2, features2, threshold=0.75):
        # Implement feature matching
        bf = cv2.BFMatcher()
        matches = bf.knnMatch(features1, features2, k=2)
        # Фильтрация признаков
        good = []
        for m, n in matches:
            if m.distance < threshold * n.distance:
                good.append(m)
        # Сравнение изображений
        matchesMask = None
        if len(good) > 10:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        return matchesMask

class FLANN:
    def match(self, kp1, features1, kp2, features2, threshold=0.75):
        # Implement feature matching
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        good = []
        if len(features1) >= 2 and len(features2) >= 2:
            matches = flann.knnMatch(features1, features2, k=2)

            for m, n in matches:
                if m.distance < threshold * n.distance:
                    good.append(m)
        matchesMask = None
        if len(good) > 10:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            matchesMask = mask.ravel().tolist()
        return matchesMask

matchers = {"BFmatcher": BFMatcher, "FLANN": FLANN}

class DuplicatesProcessor:
    def __init__(self, matcher_type="BFmatcher"):
        self.feature_extractor = FeatureExtractorSIFT()
        self.matcher = matchers[matcher_type]()
        self.last_kp = None
        self.last_features = None

    def compare(self,img1,img2, threshold=0.75):
        if img1 is None or img2 is None:
            print("Error: One or both images are None")
            return None
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