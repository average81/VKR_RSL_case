# process_images_cli.py

import logging
import argparse
import utils.utils as utils
import os
import pandas as pd
from repository.sql_repository import SQLProcessedRepository, Processed_table, create_sqlengine
import datetime

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=str, help="Input directory containing images to process.")
    parser.add_argument("--output_dir", type=str, default="output", help="Output directory to save processed images.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("--db_path", type=str, default="processed_images.db", help="Path to the SQLite database.")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    logger.info("Starting image processing...")
    if not os.path.exists(args.input_dir):
        logger.error(f"Input directory {args.input_dir} does not exist.")
        exit()
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        logger.info(f"Created output directory {args.output_dir}.")
    logger.info("Connecting to or creating database...")
    sqlengine = create_sqlengine(args.db_path)
    logger.info("Getting list of images...")
    input_images,__ = utils.open_dataset(args.input_dir)
    input_images = pd.DataFrame(input_images, columns=['filename'])
    # Сортировка с учетом длины имени файла
    logger.info("Sorting images...")
    max_len = input_images['filename'].apply(len).max()
    input_images['filename_max'] = input_images['filename']
    for i in input_images.index:
        input_images.loc[i, 'filename_max'] = "0"*(max_len-len(input_images.loc[i, 'filename'])) + input_images.loc[i, 'filename']
    input_images = input_images.sort_values(by='filename_max').reset_index(drop=True)
    input_images = input_images.drop(columns=['filename_max'])

    # Поиск по базе уже обработанных изображений и удаление их из списка
    logger.info("Searching for processed images...")
    processed_repository = SQLProcessedRepository(sqlengine)
    processed_images = processed_repository.get_proc_images()
    processed_images = pd.DataFrame(processed_images, columns=['filename'])
    processed_images = processed_images.sort_values(by='filename').reset_index(drop=True)
    input_images = input_images[~input_images['filename'].isin(processed_images['filename'])]
    logger.info("Processing images...")
    # Последняя запись в таблице обработанных изображений
    cur_idx = 0
    if len(processed_images) > 0:
        last_processed_image = processed_images.iloc[-1]['filename']
        last_processed_image_path = processed_images.iloc[-1]['path']
    else:
        # Добавляем строку с первой записью
        last_processed_image = input_images.iloc[0]['filename']
        last_processed_image_path = args.input_dir
        # Добавляем в базу данных
        processed_repository.add_proc_image(Processed_table(filename=input_images.loc[0, 'filename'], path=args.input_dir,
                                                            timestamp = datetime.datetime.now(), user = os.getlogin(), duplicates = 0,
                                                            main_double = input_images.loc[0, 'filename'], enhanced_path = ""))

    exit()