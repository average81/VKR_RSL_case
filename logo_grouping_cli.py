import os
import cv2
import argparse
import yaml
import logging
import numpy as np
import re
from processor.duplicates_processor import DuplicatesProcessor
import utils.utils as utils
from tqdm import tqdm
import pandas as pd

default_config = {
    "db_path": "processed_images.db",
    "match_threshold": 0.75,
    "duplicate_threshold": 0.7}

def main(input_folder, output_folder, logos_folder, config, save_metrics=False, metrics=None):
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
    input_images = [
        f for f in os.listdir(input_folder)
        if f.lower().endswith(supported_formats)
    ]
    # Сортировка с учетом длины имени файла
    max_len = max([len(f) for f in input_images]) if input_images else 0
    input_images_with_key = []
    for f in input_images:
        # Извлекаем номер из названия файла
        num_match = re.search(r"(\d+)", f)
        if num_match:
            prefix = f[:num_match.start()]
            postfix = f[num_match.end():]
            num = num_match.group()
            # Формируем ключ сортировки с дополнением нулями
            sort_key = prefix + "0"*(max_len-len(f)) + num + postfix
        else:
            sort_key = f
        input_images_with_key.append((f, sort_key))
    # Сортируем по ключу
    input_images_with_key.sort(key=lambda x: x[1])
    # Извлекаем отсортированные имена файлов
    input_images = [f for f, key in input_images_with_key]
    
    # Получаем список подпапок в папке логотипов
    logo_subfolders = [f for f in os.listdir(logos_folder) if os.path.isdir(os.path.join(logos_folder, f))]
    
    # Словарь для хранения изображений логотипов по папкам
    logos_by_folder = {}
    for folder in logo_subfolders:
        folder_path = os.path.join(logos_folder, folder)
        logo_images = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith(supported_formats)
        ]
        if logo_images:
            logos_by_folder[folder] = sorted(logo_images)
    
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
    
    # Словарь для хранения счётчиков по каждой папке
    folder_counters = {}
    
    # Предварительная загрузка и извлечение признаков из логотипов
    logo_features = {}
    for folder_name, logo_list in logos_by_folder.items():
        folder_counters[folder_name] = 0
        for logo_name in logo_list:
            logo_path = os.path.join(logos_folder, folder_name, logo_name)
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
                # Используем составной ключ (папка, имя_логотипа) для уникальности
                logo_features[(folder_name, logo_name)] = (kp, des)
                logging.info(f"Извлечены признаки из логотипа: {folder_name}/{logo_name}")
                
            except Exception as e:
                logging.error(f"Ошибка при обработке логотипа {logo_path}: {e}")
                continue
    current_group = None
    group_folder_path = None  # Переменная для хранения пути текущей папки группы
    logging.info(f"Начинаю обработку {len(input_images)} изображений...")
    
    # Импортируем pandas здесь, чтобы не требовать его при отключенном режиме метрик
    if save_metrics:
        import pandas as pd
        
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
        
        # Извлекаем признаки из изображения
        kp2, des2 = processor.feature_extractor.extract_features(input_img)
        max_similarity = 0
        best_logo_name = None
        
        # Сравнение с каждым логотипом для нахождения максимальной схожести
        for (folder_name, logo_name) in logo_features.keys():
            logo_path = os.path.join(logos_folder, folder_name, logo_name)
            
            try:
                # Получение признаков из кэша
                if (folder_name, logo_name) not in logo_features:
                    continue
                
                kp1, des1 = logo_features[(folder_name, logo_name)]

                # Сравнение изображения с признаками логотипа
                similarity = processor.compare_features(kp1, des1, kp2, des2, match_threshold)
                
                # Обновляем лучшее совпадение
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_folder_name = folder_name
                    best_logo_name = logo_name
                    
            except Exception as e:
                logging.error(f"Ошибка при обработке логотипа {logo_path}: {e}")
                continue
        
        # Создание новой группы по максимальной схожести, если она превышает порог
        if max_similarity >= similarity_threshold:
            # Если нашли подходящий логотип, создаем новую группу
            current_group = best_folder_name
            # Увеличиваем счётчик для данной папки
            folder_counters[best_folder_name] = folder_counters.get(best_folder_name, 0) + 1

            # Создаем имя папки группы
            group_folder_name = f"{best_folder_name}_{folder_counters[best_folder_name]}"
            group_folder_path = os.path.join(output_folder, group_folder_name)

            if not os.path.exists(group_folder_path):
                os.makedirs(group_folder_path)

            logging.info(f"Создана группа {group_folder_name} для папки {best_folder_name} (схожесть: {max_similarity:.3f})")
            
            # Сохраняем метрики, если включен режим
            if save_metrics:
                metrics.loc[len(metrics)] = [input_img_name, f"{best_folder_name}/{best_logo_name}", max_similarity]
            
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
            
            logging.info(
                f"{input_img_name}, Логотип '{best_logo_name}' ({round(max_similarity * 100, 4):>6}%)"
            )
            logging.info(f"  -> {input_img_name}")
        
        # Если логотип не найден, но мы в группе - продолжаем копировать
        # Если мы не в группе - пропускаем изображение
        if max_similarity < similarity_threshold and current_group is not None:
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
            logging.info(f"  -> {input_img_name} (продолжение группы), наиболее близкое: {best_folder_name}/{best_logo_name}, схожесть: {max_similarity:.3f}")
            
            # Сохраняем метрики, если включен режим
            if save_metrics:
                metrics.loc[len(metrics)] = [input_img_name, f"{best_folder_name}/{best_logo_name}", max_similarity]
    
    logging.info("Обработка завершена.")
    
    # Сохраняем метрики в файл, если включен режим
    if save_metrics:
        metrics.to_csv(f"{output_folder}/metrics.csv", index=False)
        logging.info(f"Метрики сохранены в {output_folder}/metrics.csv")

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
    parser.add_argument("-m", "--metrics", action="store_true", help="Enable metrics logging.")

    args = parser.parse_args()
    # Читаем или создаем конфигурацию
    if os.path.exists(args.config_path):
        config = utils.open_yaml(args.config_path)
    else:
        config = default_config
        utils.save_yaml(args.config_path, config)
    
    # Инициализация DataFrame для метрик
    metrics = pd.DataFrame(columns=['название файла', 'название логотипа', 'степень схожести'])
    
    main(args.input_folder, args.output_folder, args.logos_folder, config, args.metrics, metrics)