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
        good = []
        if len(features1) >= 2 and len(features2) >= 2:

            if self.feature_extractor == "SIFT" or self.feature_extractor== 'KAZE' or self.feature_extractor== 'AKAZE':
                matches = self.bf.knnMatch(features1, features2, k=2)
            else:
                matches = self.bf.match(features1, features2)

            # Фильтрация признаков

            for match in matches:
                if self.feature_extractor == "SIFT" or self.feature_extractor=='KAZE' or self.feature_extractor=='AKAZE':
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