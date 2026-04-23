import subprocess
import sys
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import asyncio
from app.models import Task
from app.database import SessionLocal
from processor.duplicates_processor import DuplicatesProcessor
from processor.preprocess import preprocess_image
from app import database, models
import pandas as pd
import numpy as np
import cv2
import shutil
import os
import re
from repository.sql_repository import SQLProcessedRepository, Processed_table, create_sqlengine
from utils import utils

# Глобальный словарь для хранения активных процессов обработки
ACTIVE_PROCESSES = {}

logger = logging.getLogger(__name__)

def update_task_status(task_id: int, status: str, db: Session = None):
    """Обновляет статус задачи в базе данных"""
    try:
        if db is None:
            db = SessionLocal()
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status
            task.updated_at = datetime.now()
            db.commit()
            db.refresh(task)
        
        if db is None:  # Если сессия была создана внутри функции
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса задачи {task_id}: {str(e)}")
        if db is None:
            db.close()
        raise
def natural_sort_key(filename):
    """Функция для естественной сортировки файлов по числовым значениям в имени"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]

def process_images_task(
        task_id: int,
        input_dir: str,
        output_dir: str,
        db_url: str,
        config: dict,
        shutdown_event: Optional[asyncio.Event] = None
):
    logging.basicConfig(level=logging.INFO)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    #import asyncio
    # Создаём новую сессию для фоновой задачи
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Добавляем задачу в список активных процессов
    ACTIVE_PROCESSES[task_id] = {'shutdown_event': shutdown_event, 'db': db}
    """Фоновая задача для обработки изображений"""
    try:

        # Получение списка изображений
        supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')
        input_images,__ = utils.open_dataset(input_dir)
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

        # Создание выходных директорий
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not os.path.exists(os.path.join(output_dir, "duplicates")):
            os.makedirs(os.path.join(output_dir, "duplicates"))

        # Инициализация процессора дубликатов
        matcher = config.get("matcher", "BF")
        extractor = config.get("feature_extractor", "ORB")
        Dprocessor = DuplicatesProcessor(extractor, matcher)
        logger.info(f"Using {matcher} matcher and {extractor} extractor.")
        #Убираем уже обработанные изображения из списка


        # Получение уже обработанных изображений из основной базы данных
        processed_images = db.query(models.Image.filename, models.Image.processed_path,models.Image.duplicate_group).filter(models.Image.task_id == task_id).all()
        processed_images = pd.DataFrame(processed_images, columns=['filename', 'processed_path','duplicate_group']) if processed_images else (
            pd.DataFrame(columns=['filename', 'processed_path','duplicate_group']))

        last_processed_image = None
        last_img = None
        local_duplicates = []
        duplicate_series_name = ''
        # Фильтрация входных изображений
        if len(processed_images) > 0:
            input_images = input_images[~input_images['filename'].isin(processed_images['filename'])]
            if len(processed_images) > 0:
                # Получаем последнее обработанное изображение
                last_row = processed_images.iloc[-1]
                last_processed_image = last_row['filename']
                
                # Формируем путь к изображению и загружаем его
                img_path = os.path.join(last_row['processed_path'], last_processed_image)
                try:
                    with open(img_path, 'rb') as f:
                        file_bytes = f.read()
                    np_arr = np.frombuffer(file_bytes, np.uint8)
                    last_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    if last_img is None:
                        logging.error(f"Failed to decode image at path '{img_path}'. Skipping.")
                    
                except Exception as e:
                    logging.error(f"Error reading the previous main duplicated image at path {img_path}: {str(e)}")

                # Инициализация local_duplicates на основе последней группы дубликатов
                duplicate_group = db.query(models.Image.duplicate_group).filter(
                    models.Image.duplicate_group == last_row['duplicate_group']
                ).first()

                if duplicate_group and duplicate_group[0]:  # Если последнее изображение было дубликатом
                    # Получаем все изображения из той же группы дубликатов
                    group_images = db.query(models.Image.filename).filter(
                        (models.Image.duplicate_group == duplicate_group[0]) | (models.Image.filename == duplicate_group[0]),
                        models.Image.task_id == task_id
                    ).all()
                    local_duplicates = [img[0] for img in group_images]
                    duplicate_series_name = last_row['duplicate_group'].split('.')[0]

        # Обновление задачи
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task:
            #task.total_images = len(input_images)
            task.status = "in_progress"
            db.commit()

        # Основной цикл обработки
        for i in input_images.index:
            img_name = input_images.loc[i, 'filename']
            img_path = os.path.join(input_dir, img_name)
            # Чтение изображения
            try:
                with open(img_path, 'rb') as f:
                    file_bytes = f.read()
                np_arr = np.frombuffer(file_bytes, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if img is None:
                    continue
            except Exception as e:
                continue

            # Предварительная обработка
            #img = preprocess_image(img)

            if last_img is not None:
                if Dprocessor.last_kp is None:
                    score = Dprocessor.compare(img, last_img, config["match_threshold"])
                else:
                    score = Dprocessor.compare_w_last(img, config["match_threshold"])
                logger.info(f"Image {input_images.loc[i, 'filename']} has a score of {score} for comparison with {last_processed_image}.")
                if score > config["duplicate_threshold"]:
                    # Обработка дубликата
                    if len(local_duplicates) == 0:
                        # Первый дубликат в серии
                        duplicates_dir = os.path.join(output_dir, "duplicates", last_processed_image.split(".")[0])
                        if not os.path.exists(duplicates_dir):
                            os.makedirs(duplicates_dir)

                        # Перемещение основного дубликата
                        src = os.path.join(output_dir, last_processed_image)
                        dst = os.path.join(duplicates_dir, last_processed_image)
                        if os.path.exists(src):
                            shutil.move(src, dst)

                        # Обновление записи в базе данных
                        db_image = db.query(models.Image).filter(
                            models.Image.filename == last_processed_image,
                            models.Image.task_id == task_id
                        ).first()
                        duplicate_series_name = last_processed_image.split(".")[0]
                        if db_image:
                            db_image.is_duplicate = True
                            db_image.is_main_duplicate = True
                            db_image.processed_path = duplicates_dir
                            db_image.duplicate_group=duplicate_series_name
                            db.commit()

                    local_duplicates.append(last_processed_image)


                    # Копирование текущего дубликата
                    duplicates_dir = os.path.join(output_dir, "duplicates", duplicate_series_name)
                    dst = os.path.join(duplicates_dir, img_name)
                    shutil.copy2(img_path, dst)

                    # Создание записи в базе данных
                    current_time = datetime.now()
                    db_image = models.Image(
                        filename=img_name,
                        original_path=img_path,
                        processed_path=duplicates_dir,
                        task_id=task_id,
                        is_duplicate=True,
                        duplicate_group=duplicate_series_name,
                        validation_status="pending",
                        created_at=current_time,
                        updated_at=current_time
                    )
                    db.add(db_image)
                    db.commit()
                    logger.info(f"Image {input_images.loc[i, 'filename']} is a duplicate of {last_processed_image}.")
                else:
                    # Проверка наличия серии дубликатов
                    if len(local_duplicates) > 0:
                        # Определение лучшего изображения из серии
                        local_dup_imgs = []
                        for dup_name in local_duplicates:
                            dup_path = os.path.join(output_dir, "duplicates", duplicate_series_name, dup_name)
                            print(dup_path)
                            try:
                                with open(dup_path, 'rb') as f:
                                    file_bytes = f.read()
                                np_arr = np.frombuffer(file_bytes, np.uint8)
                                dup_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                                if dup_img is not None:
                                    local_dup_imgs.append(dup_img)
                            except:
                                pass

                        if len(local_dup_imgs) > 0:
                            best_img_id = Dprocessor.get_best_quality_image(local_dup_imgs)
                            best_img_name = local_duplicates[best_img_id]

                            # Перемещение лучшего изображения в основную директорию
                            src = os.path.join(output_dir, "duplicates", duplicate_series_name, best_img_name)
                            dst = os.path.join(output_dir, best_img_name)
                            shutil.move(src, dst)

                            # Обновление записи в базе данных
                            db_image = db.query(models.Image).filter(
                                models.Image.filename == best_img_name,
                                models.Image.task_id == task_id
                            ).first()

                            if db_image:
                                db_image.is_main_duplicate = True
                                db_image.processed_path = output_dir
                                db.commit()

                        local_duplicates = []

                    # Обработка обычного изображения
                    dst = os.path.join(output_dir, img_name)
                    shutil.copy2(img_path, dst)

                    current_time = datetime.now()
                    db_image = models.Image(
                        filename=img_name,
                        original_path=img_path,
                        processed_path=output_dir,
                        task_id=task_id,
                        is_duplicate=False,
                        validation_status="pending",
                        created_at=current_time,
                        updated_at=current_time
                    )
                    db.add(db_image)
                    db.commit()

            else:
                # Первое изображение
                dst = os.path.join(output_dir, img_name)
                shutil.copy2(img_path, dst)

                current_time = datetime.now()
                db_image = models.Image(
                    filename=img_name,
                    original_path=img_path,
                    processed_path=output_dir,
                    task_id=task_id,
                    is_duplicate=False,
                    validation_status="pending",
                    created_at=current_time,
                    updated_at=current_time
                )
                db.add(db_image)
                db.commit()

            last_img = img
            last_processed_image = img_name

            # Обновление прогресса
            if task:
                task.progress = i + 1
                db.commit()

            # Проверка на сигнал остановки
            if shutdown_event and shutdown_event.is_set():
                logger.info(f"Задача {task_id} остановлена по запросу")
                update_task_status(task_id, "paused", db)
                # Очистка ссылки на задачу
                if task_id in ACTIVE_PROCESSES:
                    del ACTIVE_PROCESSES[task_id]
                return

        logger.info(f"End processing")
        # Завершение задачи
        if task:
            task.status = "on_user_review"
            task.completed_at = datetime.now()
            task.updated_at = datetime.now()
            db.commit()
    finally:
        db.close()  # Важно закрыть!

def group_by_logo_task(task_id: int, input_dir: str, output_dir: str, config_file: str) -> dict:
    """Запускает группировку по логотипам через CLI-скрипт как фоновую задачу"""
    result = {
        "success": False,
        "message": "",
        "stats": {},
        "groups": [],
        "output_files": []
    }
    
    try:
        # Обновляем статус задачи
        update_task_status(task_id, "processing")
        
        # Подготавливаем аргументы для CLI-скрипта
        cmd = [
            sys.executable, "logo_grouping_cli.py",
            input_dir,
            output_dir,
            "logo_grouping"  # Папка с логотипами
        ]
        
        # Добавляем путь к конфигурации
        if config_file:
            cmd.extend(["--config_path", config_file])
        else:
            cmd.extend(["--config_path", "config_logo.yml"])
        
        # Всегда включаем метрики для сбора статистики
        cmd.append("--metrics")
        
        logger.info(f"Запуск группировки по логотипам для задачи {task_id}")
        logger.info(f"Команда: {' '.join(cmd)}")
        
        # Запускаем CLI-скрипт
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="C:/Users/above/IdeaProjects/VKR_RSL_case"
        )
        
        # Читаем вывод в реальном времени
        for line in process.stdout:
            logger.info(f"[logo_grouping] {line.strip()}")
            
        for line in process.stderr:
            logger.error(f"[logo_grouping] {line.strip()}")
        
        # Ждем завершения процесса
        return_code = process.wait()
        
        if return_code == 0:
            result["success"] = True
            result["message"] = "Группировка по логотипам успешно завершена"
            
            # Собираем информацию о результатах
            metrics_file = f"{output_dir}/metrics.csv"
            result["output_files"].append(metrics_file)
            
            # Анализируем метрики для сбора статистики
            try:
                import pandas as pd
                if pd is not None:
                    df = pd.read_csv(metrics_file)
                    
                    # Статистика по группам
                    if 'название логотипа' in df.columns:
                        groups_stats = df['название логотипа'].value_counts().to_dict()
                        result["stats"] = groups_stats
                        
                    # Список созданных групп
                    result["groups"] = list(set(
                        [f.split('_')[0] for f in os.listdir(output_dir) 
                         if os.path.isdir(os.path.join(output_dir, f))]
                    ))
                    
            except Exception as e:
                logger.warning(f"Не удалось проанализировать метрики: {str(e)}")
                
            # Обновляем статус задачи
            update_task_status(task_id, "completed")
            
        else:
            result["message"] = f"Ошибка при группировке по логотипам: код возврата {return_code}"
            update_task_status(task_id, "failed")
            
    except Exception as e:
        result["message"] = f"Исключение при группировке по логотипам: {str(e)}"
        logger.error(f"Ошибка в group_by_logo_task: {str(e)}")
        update_task_status(task_id, "failed")
        
    return result

def process_logos_task(
        task_id: int,
        input_dir: str,
        output_dir: str,
        db_url: str,
        logos_dir: str, config,
        shutdown_event: Optional[asyncio.Event] = None):
    # Создаём новую сессию для фоновой задачи
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Добавляем задачу в список активных процессов
    if task_id not in ACTIVE_PROCESSES:
        ACTIVE_PROCESSES[task_id] = {}
    ACTIVE_PROCESSES[task_id] = {'shutdown_event': shutdown_event, 'db': db}
    """Фоновая задача для поиска логотипов на страницах и их группировки в подпапки выпусков"""
    result = {
        "success": False,
        "message": "",
        "stats": {},
        "groups": [],
        "output_files": []
    }
    
    try:
        # Обновляем статус задачи
        update_task_status(task_id, "in_progress")
        
        # Получение задачи
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        # Проверка существования папок
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"Папка входных изображений не найдена: {input_dir}")
        
        if not os.path.exists(logos_dir):
            raise FileNotFoundError(f"Папка логотипов не найдена: {logos_dir}")
        
        # Создание выходной директории
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Папка для несортированных изображений
        unsorted_dir = os.path.join(output_dir, "unsorted")
        if not os.path.exists(unsorted_dir):
            os.makedirs(unsorted_dir)
        
        # Поддерживаемые форматы изображений
        supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')
        
        # Получение и сортировка списков изображений
        input_images = [
            f for f in os.listdir(input_dir)
            if f.lower().endswith(supported_formats)
        ]
        
        # Естественная сортировка
        input_images.sort(key=natural_sort_key)
        
        if not input_images:
            logger.warning(f"Нет подходящих изображений во входной папке: {input_dir}")

            # Закрываем сессию перед выходом
            db.close()
            return

        # Получение уже обработанных изображений из базы данных
        existing_images = db.query(models.Image.filename).filter(models.Image.task_id == task_id).all()

        processed_images = db.query(models.Image.filename).filter(models.Image.task_id == task_id,
                                                                    models.Image.issue_number >= 0).all()

        
        # Создание простого списка имён файлов из processed_images
        processed_filenames = [img.filename for img in processed_images]
        
        # Фильтрация: пропускаем изображения с совпадающим именем и путем обработки
        input_images = [img for img in input_images if img not in processed_filenames]

        # Инициализация процессора дубликатов
        feature_extractor = config.get("feature_extractor", "KAZE")
        matcher_type = config.get("matcher", "BF")
        similarity_threshold = config.get("duplicate_threshold", 0.7)
        match_threshold = config.get("match_threshold", 0.75)
        
        processor = DuplicatesProcessor(feature_extractor=feature_extractor, matcher_type=matcher_type)
        # Словарь для хранения счётчиков по каждой папке
        folder_counters = {}
        # Получение подпапок с логотипами (выпуски)
        logo_subfolders = [f for f in os.listdir(logos_dir) if os.path.isdir(os.path.join(logos_dir, f))]
        
        # Предварительная загрузка признаков логотипов
        logo_features = {}
        for folder_name in logo_subfolders:
            folder_counters[folder_name] = 0
            folder_path = os.path.join(logos_dir, folder_name)
            logo_images = [f for f in os.listdir(folder_path) if f.lower().endswith(supported_formats)]
            
            for logo_name in logo_images:
                logo_path = os.path.join(folder_path, logo_name)
                try:
                    with open(logo_path, 'rb') as f:
                        file_bytes = f.read()
                    np_arr = np.frombuffer(file_bytes, np.uint8)
                    logo_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if logo_img is None:
                        logger.error(f"Не удалось декодировать логотип: {logo_path}")
                        continue
                    
                    kp, des = processor.feature_extractor.extract_features(logo_img)
                    logo_features[(folder_name, logo_name)] = (kp, des)
                    logger.info(f"Извлечены признаки из логотипа: {folder_name}/{logo_name}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке логотипа {logo_path}: {e}")
                    continue
        

        # Переменные для отслеживания группы
        current_group = None
        group_folder_path = None
        is_first_logo_found = False
        unsorted_count = 0
        
        logger.info(f"Начинаю обработку {len(input_images)} изображений...")
        
        for input_img_name in input_images:
            input_img_path = os.path.join(input_dir, input_img_name)
            # Проверка на сигнал остановки
            if shutdown_event and shutdown_event.is_set():
                logger.info(f"Задача {task_id} остановлена по запросу")
                update_task_status(task_id, "paused", db)
                # Очистка ссылки на задачу
                if task_id in ACTIVE_PROCESSES:
                    del ACTIVE_PROCESSES[task_id]
                return
            # Чтение изображения
            try:
                with open(input_img_path, 'rb') as f:
                    file_bytes = f.read()
                np_arr = np.frombuffer(file_bytes, np.uint8)
                input_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if input_img is None:
                    logger.error(f"Не удалось декодировать изображение: {input_img_path}")
                    continue
            except Exception as e:
                logger.error(f"Ошибка при чтении изображения {input_img_path}: {e}")
                continue
            
            # Извлечение признаков
            kp2, des2 = processor.feature_extractor.extract_features(input_img)
            
            if des2 is None or des2.size == 0:
                logger.warning(f"Пропуск изображения {input_img_name}: не найдено ключевых точек")
                
                # Сохраняем в unsorted, если еще не найден первый логотип
                if not is_first_logo_found:
                    dst_path = os.path.join(unsorted_dir, input_img_name)
                    try:
                        success, encoded_img = cv2.imencode('.png', input_img)
                        if success:
                            with open(dst_path, 'wb') as f:
                                f.write(encoded_img)
                                # Сохраняем запись в базу данных

                                current_time = datetime.now()
                                db_image = models.Image(
                                    filename=input_img_name,
                                    original_path=input_img_path,
                                    processed_path=unsorted_dir,
                                    task_id=task_id,
                                    is_duplicate=False,
                                    validation_status="pending",
                                    created_at=current_time,
                                    updated_at=current_time,
                                    issue_name = "unsorted",
                                    issue_number = 0,
                                    is_title_page = False
                                )
                                db.add(db_image)
                                db.commit()
                            unsorted_count += 1
                        else:
                            logger.error(f"Не удалось закодировать изображение для сохранения: {dst_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении в unsorted {dst_path}: {e}")
                else:
                    # Если группа открыта, копируем в нее
                    if current_group and group_folder_path:
                        dst_path = os.path.join(group_folder_path, input_img_name)
                        try:
                            success, encoded_img = cv2.imencode('.png', input_img)
                            if success:
                                with open(dst_path, 'wb') as f:
                                    f.write(encoded_img)
                                
                                # Сохраняем запись в базу данных
                                current_time = datetime.now()
                                db_image = models.Image(
                                    filename=input_img_name,
                                    original_path=input_img_path,
                                    processed_path=group_folder_path,
                                    task_id=task_id,
                                    is_duplicate=False,
                                    validation_status="pending",
                                    created_at=current_time,
                                    updated_at=current_time,
                                    issue_name = current_group,
                                    issue_number = folder_counters[current_group],
                                    is_title_page = False
                                )
                                db.add(db_image)
                                db.commit()

                                # Инкрементируем прогресс
                                if task:
                                    task.progress += 1
                                    db.commit()
                            else:
                                logger.error(f"Не удалось закодировать изображение для сохранения: {dst_path}")
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении в группу {dst_path}: {e}")
                

                continue
            
            # Поиск лучшего совпадения
            max_similarity = 0
            best_folder_name = ""
            best_logo_name = None
            
            for (folder_name, logo_name), (kp1, des1) in logo_features.items():
                try:
                    similarity = processor.compare_features(kp1, des1, kp2, des2, match_threshold)
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_folder_name = folder_name
                        best_logo_name = logo_name
                except Exception as e:
                    logger.error(f"Ошибка при сравнении с логотипом {folder_name}/{logo_name}: {e}")
                    continue
            
            # Проверка на срабатывание логотипа
            if max_similarity >= similarity_threshold:
                is_first_logo_found = True
                
                # Начинаем новую группу
                # Увеличиваем счётчик для данной папки
                folder_counters[best_folder_name] = folder_counters.get(best_folder_name, 0) + 1
                current_group = best_folder_name
                group_folder_path = os.path.join(output_dir, current_group)
                
                if not os.path.exists(group_folder_path):
                    os.makedirs(group_folder_path)
                
                logger.info(f"Создана группа {current_group} для выпуска {best_folder_name} (схожесть: {max_similarity:.3f})")
                
                # Копируем изображение в группу
                dst_path = os.path.join(group_folder_path, input_img_name)
                try:
                    success, encoded_img = cv2.imencode('.png', input_img)
                    if success:
                        with open(dst_path, 'wb') as f:
                            f.write(encoded_img)
                        # Создаем новую запись
                        current_time = datetime.now()
                        db_image = models.Image(
                            filename=input_img_name,
                            original_path=input_img_path,
                            processed_path=group_folder_path,
                            task_id=task_id,
                            is_duplicate=False,
                            validation_status="pending",
                            created_at=current_time,
                            updated_at=current_time,
                            issue_name = current_group,
                            issue_number = folder_counters[current_group],
                            is_title_page = True
                        )
                        db.add(db_image)
                        db.commit()
                    else:
                        logger.error(f"Не удалось закодировать изображение для сохранения: {dst_path}")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении изображения {dst_path}: {e}")
                
                logger.info(f"{input_img_name}, Логотип '{best_logo_name}' ({round(max_similarity * 100, 4):>6}%) -> {current_group}")
                
            else:
                # Копируем по правилам
                if not is_first_logo_found:
                    # Сохраняем в unsorted до первого логотипа
                    dst_path = os.path.join(unsorted_dir, input_img_name)
                    try:
                        success, encoded_img = cv2.imencode('.png', input_img)
                        if success:
                            with open(dst_path, 'wb') as f:
                                f.write(encoded_img)
                            unsorted_count += 1
                            
                            # Сохраняем запись в базу данных
                            current_time = datetime.now()
                            db_image = models.Image(
                                filename=input_img_name,
                                original_path=input_img_path,
                                processed_path=unsorted_dir,
                                task_id=task_id,
                                is_duplicate=False,
                                validation_status="pending",
                                created_at=current_time,
                                updated_at=current_time,
                                issue_name = "unsorted",
                                issue_number = 0,
                                is_title_page = False
                            )
                            db.add(db_image)
                            db.commit()

                            # Инкрементируем прогресс
                            if task:
                                task.progress += 1
                                db.commit()
                        else:
                            logger.error(f"Не удалось закодировать изображение для сохранения: {dst_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении в unsorted {dst_path}: {e}")
                    
                    logger.info(f"{input_img_name} -> unsorted (до первого логотипа)")
                elif current_group and group_folder_path:
                    # Продолжаем текущую группу
                    dst_path = os.path.join(group_folder_path, input_img_name)
                    try:
                        success, encoded_img = cv2.imencode('.png', input_img)
                        if success:
                            with open(dst_path, 'wb') as f:
                                f.write(encoded_img)
                            
                            # Создаем новую запись
                            current_time = datetime.now()
                            db_image = models.Image(
                                filename=input_img_name,
                                original_path=input_img_path,
                                processed_path=group_folder_path,
                                task_id=task_id,
                                is_duplicate=False,
                                validation_status="pending",
                                created_at=current_time,
                                updated_at=current_time,
                                issue_name = current_group,
                                issue_number = folder_counters[current_group],
                                is_title_page = True
                            )
                            db.add(db_image)
                            db.commit()

                            # Инкрементируем прогресс
                            if task:
                                task.progress += 1
                                db.commit()
                        else:
                            logger.error(f"Не удалось закодировать изображение для сохранения: {dst_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении в группу {dst_path}: {e}")
                    
                    logger.info(f"{input_img_name} -> {current_group} (продолжение группы)")
                else:
                    # Не копируем, если нет активной группы
                    logger.info(f"{input_img_name} -> пропущено (после окончания групп)")
            


        # Формируем результат
        result["success"] = True
        result["message"] = f"Группировка по логотипам завершена. Обработано {len(input_images)} изображений, {unsorted_count} в unsorted."
        result["groups"] = [f for f in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, f))]

        
        # Обновляем статус задачи
        update_task_status(task_id, "on_user_review")
        
    except Exception as e:
        result["message"] = f"Исключение при группировке по логотипам: {str(e)}"
        logger.error(f"Ошибка в process_logos_task: {str(e)}")
        update_task_status(task_id, "paused")
        
    return