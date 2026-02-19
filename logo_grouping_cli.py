import os
import cv2
import argparse
import yaml
import logging
from processor.duplicates_processor import DuplicatesProcessor

def main(input_folder, output_folder, logos_folder):
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
    
    # Чтение конфигурации из config.yml
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    feature_extractor = config.get("feature_extractor", "KAZE")
    matcher_type = config.get("matcher", "BF")
    similarity_threshold = config.get("match_threshold", 0.7)
    
    # Инициализация процессора дубликатов
    processor = DuplicatesProcessor(feature_extractor=feature_extractor, matcher_type=matcher_type)
    
    # Словарь для хранения счётчиков по каждому логотипу
    logo_counters = {}
    
    # Предварительная загрузка и извлечение признаков из логотипов
    logo_features = {}
    for logo_name in logo_images:
        logo_path = os.path.join(logos_folder, logo_name)
        try:
            logo_img = cv2.imread(logo_path)
            if logo_img is None:
                logging.error(f"Не удалось прочитать логотип: {logo_path}")
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
            input_img = cv2.imread(input_img_path)
            if input_img is None:
                logging.error(f"Не удалось прочитать изображение: {input_img_path}")
                continue
        except Exception as e:
            logging.error(f"Ошибка при чтении изображения {input_img_path}: {e}")
            continue
        
        found_logo = False
        
        # Сравнение с каждым логотипом
        for logo_name in logo_images:
            logo_path = os.path.join(logos_folder, logo_name)
            
            try:
                # logo_img больше не нужен для чтения, так как признаки уже извлечены
                if logo_name not in logo_features:
                    continue
                
                # Получение признаков из кэша
                if logo_name not in logo_features:
                    continue
                
                kp1, des1 = logo_features[logo_name]
                
                # Сравнение изображения с признаками логотипа
                similarity = processor.compare_with_features(input_img, kp1, des1)
                
                if similarity >= similarity_threshold:
                    found_logo = True
                    
                    # Если нашли новый логотип, создаем новую группу
                    if current_group is None or current_group != logo_name:
                        current_group = logo_name
                        # Увеличиваем счётчик для данного логотипа
                        logo_counters[logo_name] = logo_counters.get(logo_name, 0) + 1
                        
                        # Создаем имя папки группы
                        logo_name_without_ext = os.path.splitext(logo_name)[0]
                        group_folder_name = f"logo_{logo_name_without_ext}_{logo_counters[logo_name]}"
                        group_folder_path = os.path.join(output_folder, group_folder_name)
                        
                        if not os.path.exists(group_folder_path):
                            os.makedirs(group_folder_path)
                            
                        logging.info(f"Создана группа {group_folder_name} для логотипа {logo_name} (схожесть: {similarity:.3f})")
                    
                    # Копируем изображение в текущую группу
                    output_img_path = os.path.join(group_folder_path, input_img_name)
                    cv2.imwrite(output_img_path, input_img)
                    logging.info(f"  -> {input_img_name}")
                    
                    break  # Переход к следующему изображению после нахождения подходящего логотипа
                    
            except Exception as e:
                logging.error(f"Ошибка при обработке логотипа {logo_path}: {e}")
                continue
        
        # Если логотип не найден, но мы в группе - продолжаем копировать
        # Если мы не в группе - пропускаем изображение
        if not found_logo and current_group is not None:
            output_img_path = os.path.join(group_folder_path, input_img_name)
            cv2.imwrite(output_img_path, input_img)
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
    
    args = parser.parse_args()
    
    main(args.input_folder, args.output_folder, args.logos_folder)