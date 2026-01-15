# process_images_cli.py

import logging
import argparse
import utils.utils as utils
import os
import shutil
import pandas as pd
from repository.sql_repository import SQLProcessedRepository, Processed_table, create_sqlengine
import datetime
from processor.duplicates_processor import DuplicatesProcessor
import cv2
import re
import time

logger = logging.getLogger(__name__)

default_config = {
"db_path": "processed_images.db",
"match_threshold": 0.75,
"duplicate_threshold": 0.7}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=str, help="Input directory containing images to process.")
    parser.add_argument("--output_dir", type=str, default="output", help="Output directory to save processed images.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("-m", "--metrics", action="store_true", help="Enable metrics logging.")
    parser.add_argument("--config_path", type=str, default="config.yml", help="Path to the configuration file.")
    #parser.add_argument("--db_path", type=str, default="processed_images.db", help="Path to the SQLite database.")
    #parser.add_argument("--cthreshold", type=float, default=0.7, help="Threshold for duplicate detection.")
    #parser.add_argument("--match_threshold", type=float, default=0.75, help="Threshold for matching.")
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
    if not os.path.exists(args.output_dir + "/duplicates/"):
        os.makedirs(args.output_dir + "/duplicates/")
        logger.info(f"Created output directory {args.output_dir}/duplicates/.")
    logger.info("Connecting to or creating database...")
    # Читаем или создаем конфигурацию
    if os.path.exists(args.config_path):
        config = utils.open_yaml(args.config_path)
    else:
        config = default_config
        utils.save_yaml(args.config_path, config)
    sqlengine = create_sqlengine(config["db_path"])
    logger.info("Getting list of images...")
    input_images,__ = utils.open_dataset(args.input_dir)
    input_images = pd.DataFrame(input_images, columns=['filename'])
    # Сортировка с учетом длины имени файла
    logger.info("Sorting images...")
    max_len = input_images['filename'].apply(len).max()
    input_images['filename_max'] = input_images['filename']
    for i in input_images.index:
        # Извлекаем номер из названия файла
        num_match = re.search(r"(\d+)", input_images.loc[i, 'filename'])
        prefix = input_images.loc[i, 'filename'][:num_match.start()]
        postfix = input_images.loc[i, 'filename'][num_match.end():]
        num = num_match.group()
        input_images.loc[i, 'filename_max'] = prefix + "0"*(max_len-len(input_images.loc[i, 'filename'])) + num + postfix
    input_images = input_images.sort_values(by='filename_max').reset_index(drop=True)
    input_images = input_images.drop(columns=['filename_max'])

    # Поиск по базе уже обработанных изображений и удаление их из списка
    logger.info("Searching for processed images...")
    processed_repository = SQLProcessedRepository(sqlengine)
    processed_images = processed_repository.get_proc_images()
    processed_images = pd.DataFrame(processed_images)
    if len(processed_images) > 0:
        #processed_images = processed_images.sort_values(by='filename').reset_index(drop=True)
        input_images = input_images[~input_images['filename'].isin(processed_images['filename'])]
    logger.info("Processing images...")
    start_idx = 0   # Индекс последней записи в таблице обработанных изображений (с него начинаем сравнение)
    # Последняя запись в таблице обработанных изображений
    if len(processed_images) > 0:
        last_processed_image = processed_images.iloc[-1]['filename']
        last_processed_image_path = processed_images.iloc[-1]['path']
        start_idx = processed_images.index[-1]
    else:
        # Создаем пустую таблицу
        processed_images = pd.DataFrame(columns=['sqlid','filename', 'path', 'timestamp', 'user', 'duplicates', 'main_double', 'enhanced_path'])
        # duplicates преобразуем в int
        processed_images['duplicates'] = processed_images['duplicates'].astype(int)
        processed_images['sqlid'] = processed_images['sqlid'].astype(int)
        # Добавляем строку с первой записью
        processed_images.loc[0] = [0,input_images.loc[0, 'filename'], args.output_dir, datetime.datetime.now(), os.getlogin(),
                                   0, input_images.loc[0, 'filename'], ""]
        # Добавляем строку с первой записью
        last_processed_image = input_images.iloc[0]['filename']
        last_processed_image_path = args.input_dir
        # Добавляем в базу данных
        processed_images.loc[0, 'sqlid'] = processed_repository.add_proc_image(Processed_table(filename=input_images.loc[0, 'filename'], path=args.output_dir,
                                                            timestamp = processed_images.iloc[0].timestamp, user = os.getlogin(),
                                                            duplicates = 0, main_double = input_images.loc[0, 'filename'],
                                                            enhanced_path = ""))

        input_images = input_images.drop(0).reset_index(drop=True)
        # Копируем в выходную папку
        if not os.path.exists(args.output_dir + "/" + processed_images.loc[0, 'filename']):
            shutil.copy2(os.path.join(args.input_dir, processed_images.loc[0, 'filename']),
                         os.path.join(args.output_dir, processed_images.loc[0, 'filename']))
            logger.info(f"Copied {processed_images.loc[0, 'filename']} to {args.output_dir}.")

    last_img = cv2.imread(last_processed_image_path + "/" + last_processed_image)

    # Создаем объект сравнения
    if "matcher" in config.keys():
        Dprocessor = DuplicatesProcessor(config["matcher"])
        logger.info(f"Using {config['matcher']} matcher.")
    else:
        Dprocessor = DuplicatesProcessor()
        logger.info("Using BF matcher.")
    duplicate_series_name = ''
    metrics = pd.DataFrame(columns=['image', 'score'])
    start_time = time.time()
    for i in input_images.index:
        img = cv2.imread(args.input_dir + "/" + input_images.loc[i, 'filename'])
        if Dprocessor.last_kp is None:
            score = Dprocessor.compare(last_img,img, config["match_threshold"])
        else:
            score = Dprocessor.compare_w_last(img, config["match_threshold"])
        logger.info(f"Image {input_images.loc[i, 'filename']} has a score of {score} for comparison with {last_processed_image}.")
        if args.metrics:
            metrics.loc[len(metrics)] = [input_images.loc[i, 'filename'], score]
        if score > config["duplicate_threshold"]:
            # Добавляем запись в таблицу

            if processed_images.iloc[-1].duplicates == 0:
                # Это первый обнаруженный дубликат в серии

                if not os.path.exists(args.output_dir + "/duplicates/" + processed_images.iloc[-1].filename.split(".")[0]):
                    os.mkdir(args.output_dir + "/duplicates/" + processed_images.iloc[-1].filename.split(".")[0])
                # Перемещаем предыдущий файл в папку дубликатов с его названием
                shutil.move(f"{processed_images.iloc[-1].path}/{processed_images.iloc[-1].filename}", f"{args.output_dir}/"
                          f"duplicates/{processed_images.iloc[-1].filename.split('.')[0]}/{processed_images.iloc[-1].filename}")
                # Изменяем адрес файла в таблице
                processed_images.loc[processed_images.index[-1], 'path'] = os.path.join(
                    args.output_dir,
                    "duplicates",
                    processed_images.iloc[-1].filename.split(".")[0]
                )

                # Изменяем запись в базе
                processed_repository.update_proc_image(int(processed_images.iloc[-1].sqlid),
                                                       {'path': processed_images.iloc[-1].path})
                duplicate_series_name = processed_images.iloc[-1].filename.split(".")[0]
            # Копируем текущее изображение в папку дубликатов
            src = os.path.join(args.input_dir, input_images.loc[i, 'filename'])
            dst = os.path.join(args.output_dir, "duplicates", duplicate_series_name, input_images.loc[i, 'filename'])
            shutil.copy2(src, dst)
            dst = os.path.join(args.output_dir, "duplicates", duplicate_series_name)
            processed_images.loc[len(processed_images)] = [0,input_images.loc[i, 'filename'], dst, datetime.datetime.now(),
                                                           os.getlogin(), processed_images.iloc[-1].duplicates + 1,
                                                           processed_images.iloc[-processed_images.iloc[-1].duplicates - 1]['filename'], ""]

            # Добавляем в базу данных
            processed_images.loc[processed_images.index[-1], 'sqlid'] = processed_repository.add_proc_image(Processed_table(filename=input_images.loc[i, 'filename'], path=dst,
                                                                timestamp = processed_images.iloc[-1].timestamp, user = os.getlogin(), duplicates = int(processed_images.iloc[-1].duplicates),
                                                                main_double = processed_images.iloc[-processed_images.iloc[-1].duplicates - 1]['filename'], enhanced_path = ""))
            logger.info(f"Image {input_images.loc[i, 'filename']} is a duplicate of {last_processed_image}.")
        else:
            # Добавляем запись в таблицу
            processed_images.loc[len(processed_images)] = [0,input_images.loc[i, 'filename'], args.output_dir, datetime.datetime.now(),
                                                           os.getlogin(), 0,
                                                           processed_images.iloc[-processed_images.iloc[-1].duplicates - 1]['filename'], ""]
            processed_images.loc[processed_images.index[-1], 'sqlid'] = processed_repository.add_proc_image(Processed_table(filename=input_images.loc[i, 'filename'], path=args.output_dir,
                                                                timestamp = processed_images.iloc[-1].timestamp, user = os.getlogin(), duplicates = 0,
                                                                main_double = input_images.loc[i, 'filename'], enhanced_path = ""))
            # Копируем в выходную папку
            shutil.copy2(os.path.join(args.input_dir, input_images.loc[i, 'filename']),
                         os.path.join(args.output_dir, input_images.loc[i, 'filename']))
        last_img = img
        last_processed_image = input_images.loc[i, 'filename']
    end_time = time.time()
    logger.info(f"Processing time: {end_time - start_time} seconds.")
    logger.info(f"Average time per image: {(end_time - start_time)/len(input_images)} seconds.")
    if args.metrics:
        # Сохраняем метрики в файл
        metrics.to_csv(f"{args.output_dir}/metrics.csv", index=False)
    logger.info("Image processing completed.")
    exit()