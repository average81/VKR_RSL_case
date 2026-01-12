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


class DuplicatesProcessor:
    def __init__(self):
        self.feature_extractor = FeatureExtractorSIFT()
        self.matcher = BFMatcher()

    def compare(self,img1,img2, threshold=0.75):
        if img1 is None or img2 is None:
            print("Error: One or both images are None")
            return None
        kp1,features1 = self.feature_extractor.extract_features(img1)
        kp2,features2 = self.feature_extractor.extract_features(img2)
        matches = self.matcher.match(kp1,features1,kp2,features2,threshold)
        if matches is not None:
            if len(matches) > 10:
                return sum(matches) / len(matches)
            else:
                return 0
        return 0