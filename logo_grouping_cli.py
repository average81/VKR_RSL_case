import os
import cv2
import argparse
import yaml
import logging
import numpy as np
from processor.duplicates_processor import DuplicatesProcessor
import utils.utils as utils

default_config = {
    "db_path": "processed_images.db",
    "match_threshold": 0.75,
    "duplicate_threshold": 0.7}

def main(input_folder, output_folder, logos_folder, config):
    # Проверка существования папок
    if not os.path.exists(input_folder):
        raise FileNotFoundError(f"Папка входных изображений не найдена: {input_folder}")
    
    if not os.path.exists(logos_folder):
        raise FileNotFoundError(f"Папка логотипов не найдена: {logos_folder}")
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Поддерживаемые форматы изображений
    supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')
    
    # Получение и сортировка списков изображений
    input_images = sorted([
        f for f in os.listdir(input_folder)
        if f.lower().endswith(supported_formats)
    ])
    
    logo_images = sorted([
        f for f in os.listdir(logos_folder)
        if f.lower().endswith(supported_formats)
    ])
    
    if not input_images:
        logging.warning(f"Нет подходящих изображений во входной папке: {input_folder}")
        return
    
    if not logo_images:
        logging.warning(f"Нет подходящих изображений в папке логотипов: {logos_folder}")
        return

    
    feature_extractor = config.get("feature_extractor", "KAZE")
    matcher_type = config.get("matcher", "BF")
    similarity_threshold = config.get("duplicate_threshold", 0.7)
    match_threshold = config.get("match_threshold", 0.75)
    
    # Инициализация процессора дубликатов
    processor = DuplicatesProcessor(feature_extractor=feature_extractor, matcher_type=matcher_type)
    
    # Словарь для хранения счётчиков по каждому логотипу
    logo_counters = {}
    
    # Предварительная загрузка и извлечение признаков из логотипов
    logo_features = {}
    for logo_name in logo_images:
        logo_path = os.path.join(logos_folder, logo_name)
        try:
            # Чтение изображения логотипа с поддержкой кириллицы
            try:
                with open(logo_path, 'rb') as f:
                    file_bytes = f.read()
                np_arr = np.frombuffer(file_bytes, np.uint8)
                logo_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if logo_img is None:
                    logging.error(f"Не удалось декодировать логотип: {logo_path}")
                    continue
            except Exception as e:
                logging.error(f"Ошибка при чтении логотипа {logo_path}: {e}")
                continue
            
            # Извлечение ключевых точек и дескрипторов
            kp, des = processor.feature_extractor.extract_features(logo_img)
            logo_features[logo_name] = (kp, des)
            logging.info(f"Извлечены признаки из логотипа: {logo_name}")
            
        except Exception as e:
            logging.error(f"Ошибка при обработке логотипа {logo_path}: {e}")
            continue
    current_group = None
    group_folder_path = None  # Переменная для хранения пути текущей папки группы
    logging.info(f"Начинаю обработку {len(input_images)} изображений...")
    
    for input_img_name in input_images:
        input_img_path = os.path.join(input_folder, input_img_name)
        
        # Попытка чтения входного изображения
        try:
            # Чтение изображения с поддержкой кириллицы
            try:
                with open(input_img_path, 'rb') as f:
                    file_bytes = f.read()
                np_arr = np.frombuffer(file_bytes, np.uint8)
                input_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if input_img is None:
                    logging.error(f"Не удалось декодировать изображение: {input_img_path}")
                    continue
            except Exception as e:
                logging.error(f"Ошибка при чтении изображения {input_img_path}: {e}")
                continue
        except Exception as e:
            logging.error(f"Ошибка при чтении изображения {input_img_path}: {e}")
            continue
        
        found_logo = False
        
        # Сравнение с каждым логотипом
        for logo_name in logo_images:
            logo_path = os.path.join(logos_folder, logo_name)
            
            try:

                # Получение признаков из кэша
                if logo_name not in logo_features:
                    continue
                
                kp1, des1 = logo_features[logo_name]

                # Сравнение изображения с признаками логотипа
                similarity = processor.compare_with_features(input_img, kp1, des1,match_threshold)

                if similarity >= similarity_threshold:
                    found_logo = True
                    logging.info(
                        f"{input_img_name}, Логотип '{logo_name}' ({round(similarity * 100, 4):>6}%)"
                    )# Найдено совпадающее название лого
                    # Если нашли новый логотип, создаем новую группу
                    current_group = logo_name
                    # Увеличиваем счётчик для данного логотипа
                    logo_counters[logo_name] = logo_counters.get(logo_name, 0) + 1

                    # Создаем имя папки группы
                    logo_name_without_ext = os.path.splitext(logo_name)[0]
                    group_folder_name = f"{logo_name_without_ext}_{logo_counters[logo_name]}"
                    group_folder_path = os.path.join(output_folder, group_folder_name)

                    if not os.path.exists(group_folder_path):
                        os.makedirs(group_folder_path)

                    logging.info(f"Создана группа {group_folder_name} для логотипа {logo_name} (схожесть: {similarity:.3f})")
                    
                    # Копируем изображение в текущую группу
                    output_img_path = os.path.join(group_folder_path, input_img_name)
                    # Сохранение изображения с поддержкой кириллицы
                    try:
                        success, encoded_img = cv2.imencode('.png', input_img)
                        if success:
                            with open(output_img_path, 'wb') as f:
                                f.write(encoded_img)
                        else:
                            logging.error(f"Не удалось закодировать изображение для сохранения: {output_img_path}")
                    except Exception as e:
                        logging.error(f"Ошибка при сохранении изображения {output_img_path}: {e}")
                    logging.info(f"  -> {input_img_name}")
                    
                    break  # Переход к следующему изображению после нахождения подходящего логотипа
                    
            except Exception as e:
                logging.error(f"Ошибка при обработке логотипа {logo_path}: {e}")
                continue
        
        # Если логотип не найден, но мы в группе - продолжаем копировать
        # Если мы не в группе - пропускаем изображение
        if not found_logo and current_group is not None:
            output_img_path = os.path.join(group_folder_path, input_img_name)
            # Сохранение изображения с поддержкой кириллицы
            try:
                success, encoded_img = cv2.imencode('.png', input_img)
                if success:
                    with open(output_img_path, 'wb') as f:
                        f.write(encoded_img)
                else:
                    logging.error(f"Не удалось закодировать изображение для сохранения: {output_img_path}")
            except Exception as e:
                logging.error(f"Ошибка при сохранении изображения {output_img_path}: {e}")
            logging.info(f"  -> {input_img_name} (продолжение группы)")
    
    logging.info("Обработка завершена.")

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logo_grouping.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    
    parser = argparse.ArgumentParser(description='Группировка изображений по схожести с логотипами')
    parser.add_argument('input_folder', help='Путь к папке с входными изображениями')
    parser.add_argument('output_folder', help='Путь к выходной папке')
    parser.add_argument('logos_folder', help='Путь к папке с изображениями логотипов')
    parser.add_argument("--config_path", type=str, default="config_logo.yml", help="Path to the configuration file.")

    args = parser.parse_args()
    # Читаем или создаем конфигурацию
    if os.path.exists(args.config_path):
        config = utils.open_yaml(args.config_path)
    else:
        config = default_config
        utils.save_yaml(args.config_path, config)
    main(args.input_folder, args.output_folder, args.logos_folder, config)