import cv2
import kornia as K
import kornia.feature as KF
import torch
import numpy as np
from kornia_moons import feature as KM


class FeatureExtractorSIFT:
    """
    Извлечение признаков SIFT с поддержкой KP_CV и LAF форматов.
    
    SIFT (Scale-Invariant Feature Transform) — устойчивый к масштабу и повороту
    дескриптор. Для LAF режима используется kornia обёртка OpenCVFeatureKornia.
    """
    
    def __init__(self, nfeatures=20000, kp_type="KP_CV", device="cpu"):
        self.kp_type = kp_type
        self.nfeatures = nfeatures
        
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        
        self.sift = cv2.SIFT_create(nfeatures=nfeatures)
        
        # Для LAF режима создаём локальный фич экстрактор через kornia обёртку
        if kp_type == "LAF":
            self.kornia_feature = KM.OpenCVFeatureKornia(self.sift)
    
    def extract_features(self, image):
        """
        Извлекает ключевые точки и дескрипторы SIFT.
        
        Параметры:
        - image: numpy array (BGR или grayscale)
        
        Возвращает:
        - kps: список cv2.KeyPoint (KP_CV) или (lafs, responses) tuple (LAF)
        - descs: numpy array (KP_CV) или torch tensor (LAF)
        """
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        
        if self.kp_type == "KP_CV":
            # OpenCV формат
            kp, des = self.sift.detectAndCompute(grey, None)
            return kp, des
        
        else:
            # LAF формат — через kornia обёртку OpenCVFeatureKornia
            img_tensor = (K.image_to_tensor(grey).float() / 255.0)[None, ...].to(self.device)
            lafs, resps, descs = self.kornia_feature(img_tensor)

            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            return (lafs, resps), descs


class FeatureExtractorKorniaSIFT:
    """
    Извлечение признаков SIFT с использованием kornia.feature.SIFTFeature.
    
    SIFT (Scale-Invariant Feature Transform) — устойчивый к масштабу и повороту
    дескриптор. Kornia реализует его через GPU-оптимизированный пайплайн.
    """
    
    def __init__(self, nfeatures=20000, kp_type="KP_CV", device="cpu"):
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        self.sift = KF.SIFTFeature(num_features=nfeatures)
        self.nfeatures = nfeatures
        self.kp_type = kp_type

    def extract_features(self, image):
        """
        Извлекает ключевые точки и дескрипторы из изображения.
        
        Параметры:
        - image: numpy array (BGR или grayscale)
        
        Возвращает:
        - kps: список cv2.KeyPoint (KP_CV) или (lafs, responses) tuple (LAF)
        - descs: numpy array (KP_CV) или torch tensor (LAF)
        """
        if len(image.shape) == 3 and image.shape[2] == 3:
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray_image = image
        
        img_tensor = (K.image_to_tensor(gray_image).float() / 255.0)[None, ...].to(self.device)
        
        # Извлекаем признаки через kornia SIFT
        lafs, responses, descriptors = self.sift(img_tensor)
        
        if self.kp_type == "KP_CV":
            # Конвертируем LAFs в OpenCV ключевые точки
            kps = KM.opencv_kpts_from_laf(lafs, 6.0, responses)
            descs = descriptors[0].detach().cpu().numpy().astype(np.float32)
        else:
            # Возвращаем LAF tuple + descriptors tensor
            kps = (lafs, responses)
            descs = descriptors
        
        if self.device == "cuda":
            torch.cuda.empty_cache()
        
        return kps, descs


class FeatureExtractorORB:
    """
    Извлечение признаков ORB с использованием kornia + OpenCV.
    
    ORB (Oriented FAST and Rotated BRIEF) — быстрый бинарный дескриптор.
    """
    
    def __init__(self, nfeatures=20000, kp_type="KP_CV", device="cpu"):
        self.kp_type = kp_type
        self.nfeatures = nfeatures
        
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        
        # Создаём обёртку OpenCVFeatureKornia для ORB
        try:
            if device == "cuda" and hasattr(cv2, 'cuda'):
                self.orb = cv2.cuda.createORB(nfeatures=nfeatures)
                self.use_cuda = True
            else:
                self.orb = cv2.ORB_create(nfeatures=nfeatures)
                self.use_cuda = False
        except AttributeError:
            self.orb = cv2.ORB_create(nfeatures=nfeatures)
            self.use_cuda = False
        
        # Для LAF режима создаём локальный фич экстрактор
        if kp_type == "LAF":
            self.kornia_feature = KM.OpenCVFeatureKornia(self.orb)
    
    def extract_features(self, image):
        """
        Извлекает ключевые точки и дескрипторы ORB.
        
        Параметры:
        - image: numpy array (BGR или grayscale)
        
        Возвращает:
        - kps: список cv2.KeyPoint (KP_CV) или (lafs, responses) tuple (LAF)
        - descs: numpy array (KP_CV) или torch tensor (LAF)
        """
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        
        if self.kp_type == "KP_CV":
            # OpenCV формат
            if self.use_cuda:
                grey_gpu = cv2.cuda_GpuMat()
                grey_gpu.upload(grey)
                kp, des = self.orb.detectAndCompute(grey_gpu, None)
                if des is not None:
                    des = des.cpu() if hasattr(des, 'cpu') else des
            else:
                kp, des = self.orb.detectAndCompute(grey, None)
            return kp, des
        
        else:
            # LAF формат — через kornia OpenCVFeatureKornia
            img_tensor = (K.image_to_tensor(grey).float() / 255.0)[None, ...].to(self.device)
            lafs, resps, descs = self.kornia_feature(img_tensor)
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            return (lafs, resps), descs


class FeatureExtractorKAZE:
    """
    Извлечение признаков KAZE с использованием kornia + OpenCV.
    
    KAZE — нелинейный скалообразный дескриптор, устойчивый к изменению
    освещённости и масштаба.
    """
    
    def __init__(self, nfeatures=20000, kp_type="KP_CV", device="cpu"):
        self.kp_type = kp_type
        self.nfeatures = nfeatures
        
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        
        self.kaze = cv2.KAZE_create()
        
        # Для LAF режима создаём локальный фич экстрактор
        if kp_type == "LAF":
            self.kornia_feature = KM.OpenCVFeatureKornia(self.kaze)
    
    def extract_features(self, image):
        """
        Извлекает ключевые точки и дескрипторы KAZE.
        
        Параметры:
        - image: numpy array (BGR или grayscale)
        
        Возвращает:
        - kps: список cv2.KeyPoint (KP_CV) или (lafs, responses) tuple (LAF)
        - descs: numpy array (KP_CV) или torch tensor (LAF)
        """
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        
        if self.kp_type == "KP_CV":
            # OpenCV формат
            kp, des = self.kaze.detectAndCompute(grey, None)
            if len(kp) > self.nfeatures:
                sorted_idx = sorted(range(len(kp)), key=lambda i: kp[i].response, reverse=True)[:self.nfeatures]
                kp = [kp[i] for i in sorted_idx]
                des = des[sorted_idx]
            return kp, des
        
        else:
            # LAF формат — через kornia OpenCVFeatureKornia
            img_tensor = (K.image_to_tensor(grey).float() / 255.0)[None, ...].to(self.device)
            lafs, resps, descs = self.kornia_feature(img_tensor)
            
            # Фильтрация по nfeatures
            if len(lafs[0]) > self.nfeatures:
                # Работаем с первым элементом batch
                k = min(self.nfeatures, resps.size(1))
                sorted_idx = torch.topk(resps[0].view(-1), k=k, dim=0, largest=True).indices
                # Используем index_select — без добавления осей
                lafs = lafs.index_select(1, sorted_idx)
                resps = resps.index_select(1, sorted_idx)
                descs = descs.index_select(1, sorted_idx)
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            return (lafs, resps), descs


class FeatureExtractorAKAZE:
    """
    Извлечение признаков AKAZE с использованием kornia + OpenCV.
    
    AKAZE — ускоренная версия KAZE, использует нелинейную шкалу
    и бинарные дескрипторы (по умолчанию).
    """
    
    def __init__(self, nfeatures=20000, kp_type="KP_CV", device="cpu"):
        self.kp_type = kp_type
        self.nfeatures = nfeatures
        
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        
        self.akaze = cv2.AKAZE_create()
        
        # Для LAF режима создаём локальный фич экстрактор
        if kp_type == "LAF":
            self.kornia_feature = KM.OpenCVFeatureKornia(self.akaze)
    
    def extract_features(self, image):
        """
        Извлекает ключевые точки и дескрипторы AKAZE.
        
        Параметры:
        - image: numpy array (BGR или grayscale)
        
        Возвращает:
        - kps: список cv2.KeyPoint (KP_CV) или (lafs, responses) tuple (LAF)
        - descs: numpy array (KP_CV) или torch tensor (LAF)
        """
        if len(image.shape) == 3:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grey = image
        
        if self.kp_type == "KP_CV":
            # OpenCV формат
            kp, des = self.akaze.detectAndCompute(grey, None)
            if len(kp) > self.nfeatures:
                sorted_idx = sorted(range(len(kp)), key=lambda i: kp[i].response, reverse=True)[:self.nfeatures]
                kp = [kp[i] for i in sorted_idx]
                des = des[sorted_idx]
            return kp, des
        
        else:
            # LAF формат — через kornia OpenCVFeatureKornia
            img_tensor = (K.image_to_tensor(grey).float() / 255.0)[None, ...].to(self.device)
            lafs, resps, descs = self.kornia_feature(img_tensor)
            
            # Фильтрация по nfeatures
            if len(lafs[0]) > self.nfeatures:
                # Работаем с первым элементом batch
                k = min(self.nfeatures, resps.size(1))
                sorted_idx = torch.topk(resps[0].view(-1), k=k, dim=0, largest=True).indices
                # Используем index_select — без добавления осей
                lafs = lafs.index_select(1, sorted_idx)
                resps = resps.index_select(1, sorted_idx)
                descs = descs.index_select(1, sorted_idx)
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            return (lafs, resps), descs


class FeatureExtractorDISK:
    """
    Извлечение признаков DISK с использованием kornia.feature.DISK.
    
    DISK (Deep Invariant Keypoint Detector) — предобученная нейросеть
    для обнаружения ключевых точек и извлечения дескрипторов.
    
    Michał Tyszkiewicz, Pascal Fua, and Eduard Trulls.
    DISK: learning local features with policy gradient.
    Advances in Neural Information Processing Systems, 33:14254–14265, 2020.
    """
    
    def __init__(self, nfeatures=200000, kp_type="KP_CV", device="cpu"):
        if device == "cuda":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        
        self.disk = KF.DISK.from_pretrained("depth").to(self.device)
        self.num_features = nfeatures
        self.kp_type = kp_type

    def extract_features(self, image):
        """
        Извлекает ключевые точки и дескрипторы DISK.
        
        Параметры:
        - image: numpy array (BGR или grayscale)
        
        Возвращает:
        - kps: список cv2.KeyPoint (KP_CV) или keypoints tensor (LAF)
        - descs: numpy array (KP_CV) или torch tensor (LAF)
        """
        if len(image.shape) == 3:
            if image.shape[2] == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                raise ValueError("Unexpected number of channels in input image")
        else:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Уменьшаем изображение до максимального размера 2500px
        h, w = rgb_image.shape[:2]
        max_size = 2500
        if h > max_size or w > max_size:
            scale = max_size / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb_image = cv2.resize(rgb_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        img_tensor = (K.image_to_tensor(rgb_image).float() / 255.0)[None, ...].to(self.device)
        
        features = self.disk(img_tensor, self.num_features, pad_if_not_divisible=True)
        features = features[0]  # убираем batch-размер
        kps = features.keypoints
        descs = features.descriptors
        
        if self.kp_type == "KP_CV":
            kps_np = kps.detach().cpu().numpy()
            descs_np = descs.detach().cpu().numpy()
            keypoints_cv = [
                cv2.KeyPoint(x=float(pt[0]), y=float(pt[1]), size=1)
                for pt in kps_np
            ]
            kps = keypoints_cv
            descs = descs_np.astype(np.float32)
        else:
            # Преобразуем в LAF
            lafs = KF.laf_from_center_scale_ori(kps[None])
            kps = (lafs, features.detection_scores.unsqueeze(0).unsqueeze(-1))
            descs = descs.unsqueeze(0)
        if self.device == "cuda":
            torch.cuda.empty_cache()
        
        return kps, descs
