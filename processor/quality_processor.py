# класс сравнения качества изображений и выбора лучшего
import cv2
import numpy as np
import os
from skimage.util import img_as_float
import torch


class QualityProcessor_brisque:
    def __init__(self):
        """
        Инициализирует модель BRISQUE через библиотеку pyiqa.
        pyiqa - это современная библиотека для оценки качества изображений.
        """
        try:
            import pyiqa
            
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            # Загружаем модель BRISQUE через pyiqa
            self.iqa_metric = pyiqa.create_metric('brisque', device=self.device)
            self.use_pyiqa = True
            print("BRISQUE model loaded via pyiqa")
            
        except ImportError:
            print("pyiqa not found, trying old brisque library...")
            self._try_old_brisque()
        except Exception as e:
            print(f"pyiqa loading warning: {e}")
            print("Falling back to old brisque library")
            self._try_old_brisque()
    
    def _try_old_brisque(self):
        """Попытка использовать старую библиотеку brisque."""
        try:
            from brisque import BRISQUE
            self.brisque = BRISQUE()
            self.use_pyiqa = False
            print("Using old brisque library")
        except Exception as e:
            print(f"Failed to load BRISQUE: {e}")
            self.use_pyiqa = False
            self.brisque = None

    def score(self, img):
        """
        Оценивает качество изображения с помощью BRISQUE.
        Чем ниже значение — тем выше качество.

        :param img: изображение (numpy array, BGR)
        :return: оценка BRISQUE (float)
        """
        if self.use_pyiqa and hasattr(self, 'iqa_metric'):
            try:
                # Конвертируем BGR в RGB
                if len(img.shape) == 3 and img.shape[2] == 3:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                else:
                    img_rgb = img
                
                # pyiqa ожидает tensor в диапазоне [0, 1]
                img_tensor = torch.from_numpy(img_rgb).float() / 255.0
                if len(img_tensor.shape) == 3:
                    img_tensor = img_tensor.permute(2, 0, 1)  # HWC -> CHW
                img_tensor = img_tensor.unsqueeze(0).to(self.device)
                
                with torch.no_grad():
                    score = self.iqa_metric(img_tensor)
                    
                # В pyiqa BRISQUE выдает положительное значение (меньше = лучше)
                return score.item() if isinstance(score, torch.Tensor) else float(score)
                
            except Exception as e:
                print(f"pyiqa BRISQUE error: {e}")
                # Fallback
                return self._score_old_brisque(img)
        else:
            return self._score_old_brisque(img)
    
    def _score_old_brisque(self, img):
        """Счет BRISQUE через старую библиотеку."""
        if self.brisque is None:
            return float('inf')
        
        img_float = img_as_float(img)
        try:
            score = self.brisque.score(img_float)
            return score
        except Exception as e:
            print(f"Old BRISQUE error: {e}")
            return float('inf')

    def compare(self, imgs):
        """
        Сравнивает изображения по метрике BRISQUE и выбирает лучшее (с наименьшей оценкой).

        :param imgs: список изображений (numpy array, BGR)
        :return: индекс лучшего изображения
        """
        scores = []
        for img in imgs:
            score = self.score(img)
            scores.append(score)

        # Лучшее изображение — с минимальным BRISQUE-скором
        return np.argmin(scores)

