import cv2
import numpy as np
import unittest

from processor.duplicates_processor import DuplicatesProcessor
from processor.feature_extractors import *
from processor.feature_matchers import *

class TestDuplicatesProcessor(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Создаем заглушки изображений для тестов
        cls.img1 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        cls.img2 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    
    def test_kaze_with_bf_matcher_initialization(self):
        processor = DuplicatesProcessor(feature_extractor="KAZE", matcher_type="BF")
        self.assertIsInstance(processor.feature_extractor, FeatureExtractorKAZE)
        self.assertIsInstance(processor.matcher, BFMatcher)
    
    def test_kaze_with_flann_matcher_initialization(self):
        processor = DuplicatesProcessor(feature_extractor="KAZE", matcher_type="FLANN")
        self.assertIsInstance(processor.feature_extractor, FeatureExtractorKAZE)
        self.assertIsInstance(processor.matcher, FLANNmatcher)
    
    def test_kaze_bf_comparison_success(self):
        processor = DuplicatesProcessor(feature_extractor="KAZE", matcher_type="BF")
        result = processor.compare(self.img1, self.img2)
        self.assertIsInstance(result, float)
        
    def test_kaze_flann_comparison_success(self):
        processor = DuplicatesProcessor(feature_extractor="KAZE", matcher_type="FLANN")
        result = processor.compare(self.img1, self.img2)
        self.assertIsInstance(result, float)


if __name__ == '__main__':
    unittest.main()

