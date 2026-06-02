import cv2
import kornia as K
import kornia.feature as KF
import torch
import numpy as np

class FeatureExtractorSIFT:
    def __init__(self):
        self.sift = cv2.SIFT_create()
    
    def extract_features(self, image):
        # Implement SIFT feature extraction
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        kp, des = self.sift.detectAndCompute(grey, None)
        return kp, des

class FeatureExtractorORB:
    def __init__(self, nfeatures=10000):
        self.orb = cv2.ORB_create(nfeatures=nfeatures)
    
    def extract_features(self, image):
        # Implement ORB feature extraction
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        kp, des = self.orb.detectAndCompute(grey, None)
        return kp, des

class FeatureExtractorKAZE:
    def __init__(self):
        self.kaze = cv2.KAZE_create()
    
    def extract_features(self, image):
        # Implement KAZE feature extraction
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        kp, des = self.kaze.detectAndCompute(grey, None)
        return kp, des

class FeatureExtractorAKAZE:
    def __init__(self):
        self.akaze = cv2.AKAZE_create()
    
    def extract_features(self, image):
        # Implement AKAZE feature extraction
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        kp, des = self.akaze.detectAndCompute(grey, None)
        return kp, des


#Michał Tyszkiewicz, Pascal Fua, and Eduard Trulls. Disk: learning local features with policy gradient.
# #Advances in Neural Information Processing Systems, 33:14254–14265, 2020.
class FeatureExtractorDISK:
    def __init__(self, num_features=200000, matcher = "BF"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        self.disk = KF.DISK.from_pretrained("depth").to(self.device)
        self.num_features = num_features
        self.matcher = matcher

    def extract_features(self, image):
        # Преобразуем к RGB
        if len(image.shape) == 3:
            if image.shape[2] == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                raise ValueError("Unexpected number of channels in input image")
        else:
            # Для ч/б изображения дублируем канал
            rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            
        # Уменьшаем изображение до максимального размера 3000x3000 с сохранением пропорций
        h, w = rgb_image.shape[:2]
        max_size = 2500
        if h > max_size or w > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            rgb_image = cv2.resize(rgb_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
        img1 = (K.image_to_tensor(rgb_image).float() / 255.0)[None, ...].to(self.device)
        features = self.disk(img1, self.num_features, pad_if_not_divisible=True)
        features = features[0]
        kps = features.keypoints.cpu()
        descs = features.descriptors.cpu()
        if self.matcher != "SM":
            kps = kps.detach().numpy()
            descs = descs.detach().numpy()
            # Преобразуем ключевые точки в формат OpenCV
            kps_cv2 = []
            for pt in kps:
                kp = cv2.KeyPoint(x=float(pt[0]), y=float(pt[1]), size=1)
                kps_cv2.append(kp)

            # Убеждаемся, что дескрипторы имеют тип float32
            descs = descs.astype(np.float32)
            kps = kps_cv2
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return kps, descs