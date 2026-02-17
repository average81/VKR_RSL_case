
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
    def __init__(self):
        self.orb = cv2.ORB_create()
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