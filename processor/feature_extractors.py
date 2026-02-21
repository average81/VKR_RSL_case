import cv2

class FeatureExtractorSIFT:
    def __init__(self):
        self.sift = cv2.SIFT_create()
    def extract_features(self, image):
        # Implement SIFT feature extraction
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, des = self.sift.detectAndCompute(grey, None)
        return kp,des

class FeatureExtractorORB:
    def __init__(self, nfeatures = 10000):
        self.orb = cv2.ORB_create(nfeatures = nfeatures)
    def extract_features(self, image):
        # Implement ORB feature extraction
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, des = self.orb.detectAndCompute(grey, None)
        return kp,des

class FeatureExtractorKAZE:
    def __init__(self):
        self.kaze = cv2.KAZE_create()
    
    def extract_features(self, image):
        # Implement KAZE feature extraction
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, des = self.kaze.detectAndCompute(grey, None)
        return kp, des

class FeatureExtractorAKAZE:
    def __init__(self):
        self.akaze = cv2.AKAZE_create()
    
    def extract_features(self, image):
        # Implement AKAZE feature extraction
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, des = self.akaze.detectAndCompute(grey, None)
        return kp, des