import os
import logging
import time
from typing import List, Tuple

import pandas as pd

from processor.duplicates_processor import DuplicatesProcessor


def setup_logging(verbose: bool):
    if verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING)


def load_images_in_order(input_dir: str) -> List[str]:
    """
    Load image file paths from input directory in alphabetical order.
    """
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    images = []
    
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    
    for file_name in sorted(os.listdir(input_dir)):
        file_path = os.path.join(input_dir, file_name)
        if os.path.isfile(file_path):
            _, ext = os.path.splitext(file_name.lower())
            if ext in supported_extensions:
                images.append(file_path)
    
    return images


def compare_images(
    input_dir: str,
    extractor: str = "SIFT",
    matcher: str = "BF",
    match_threshold: float = 0.75,
    verbose: bool = False
) -> pd.DataFrame:
    """
    Compare images sequentially and return performance metrics.
    
    Args:
        input_dir: Path to directory with images
        extractor: Feature extractor to use (SIFT, ORB, etc.)
        matcher: Matcher to use (BF, FLANN)
        match_threshold: Threshold for feature matching
        verbose: Enable detailed logging
    
    Returns:
        DataFrame with performance metrics
    """
    setup_logging(verbose)
    
    logging.info(f"Loading images from {input_dir}")
    
    images = load_images_in_order(input_dir)
    
    if len(images) == 0:
        raise FileNotFoundError(f"No images found in the input directory: {input_dir}")
    
    logging.info(f"Loaded {len(images)} images")
    
    processor = DuplicatesProcessor(
        feature_extractor=extractor,
        matcher_type=matcher
    )

    metrics = pd.DataFrame(columns=['image1','image2', 'score'])
    
    # Process images sequentially, comparing each with the previous one
    for i in range(1, len(images)):
        img_path = images[i]
        prev_img_path = images[i-1]
        
        logging.info(f"Comparing {prev_img_path} with {img_path}")

        try:
            if i == 1:
                score = processor.compare(img_path, prev_img_path,
                                          threshold=match_threshold)
            else:
                score = processor.compare_w_last(img_path,
                                           threshold=match_threshold)

            metrics.loc[len(metrics)] = [img_path, prev_img_path, score]

            logging.info(f"Score: {score:.4f}")
        except Exception as e:
            raise FileNotFoundError(f"Error processing {img_path}: {e}")
    

    # Return metrics as DataFrame
    return metrics



