
# класс сравнения качества изображений и выбора лучшего
import cv2
import numpy as np
from skimage.util import img_as_float
from skimage.metrics import peak_signal_noise_ratio as psnr
from brisque import BRISQUE

# Класс оценки качества изображения по методике BRISQUE
class QualityProcessor:

    def __init__(self):
        self.brisque = BRISQUE()

    def score_brisque(self, img):
        """
        Оценивает качество изображения с помощью BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator).
        Чем ниже значение — тем выше качество.

        :param img: изображение (numpy array, BGR)
        :return: оценка BRISQUE (float)
        """
        # BRISQUE работает с изображениями в формате float [0, 1]
        img_float = img_as_float(img)

        try:
            score = self.brisque.score(img_float)
        except Exception as e:
            # На некоторых изображениях (например, слишком однородных) BRISQUE может падать
            print(f"BRISQUE error: {e}")
            score = float('inf')  # худшая возможная оценка

        return score

    def compare(self, imgs):
        """
        Сравнивает изображения по метрике BRISQUE и выбирает лучшее (с наименьшей оценкой).

        :param imgs: список изображений (numpy array, BGR)
        :return: индекс лучшего изображения
        """
        scores = []
        for img in imgs:
            score = self.score_brisque(img)
            scores.append(score)

        # Лучшее изображение — с минимальным BRISQUE-скором
        return np.argmin(scores)
