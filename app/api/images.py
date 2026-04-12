from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import os
import shutil
import json

from app import database, models
from app.database import get_db
from app.api.auth import get_current_active_user, get_current_superuser
from app.models.image import Image, ImageBase, ImageCreate, ImageSchema, ImageValidation, ImageMove
from app.models.task import Task
from app.models.user import User
from processor.duplicates_processor import DuplicatesProcessor
from processor.preprocess import preprocess_image
import cv2
import re
import time
import pandas as pd
from repository.sql_repository import SQLProcessedRepository, Processed_table, create_sqlengine

router = APIRouter(prefix="/images")

def natural_sort_key(filename):
    """Функция для естественной сортировки файлов по числовым значениям в имени"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]

def process_images_task(
    task_id: int,
    input_dir: str,
    output_dir: str,
    db: Session,
    config: dict
):
    """Фоновая задача для обработки изображений"""
    
    # Инициализация репозитория базы данных
    sqlengine = create_sqlengine(config["db_path"])
    processed_repository = SQLProcessedRepository(sqlengine)
    
    # Получение списка изображений
    supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')
    input_images = [
        f for f in os.listdir(input_dir)
        if f.lower().endswith(supported_formats)
    ]
    
    # Естественная сортировка
    input_images.sort(key=natural_sort_key)
    
    # Создание выходных директорий
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if not os.path.exists(os.path.join(output_dir, "duplicates")):
        os.makedirs(os.path.join(output_dir, "duplicates"))
    
    # Инициализация процессора дубликатов
    matcher = config.get("matcher", "BF")
    extractor = config.get("feature_extractor", "KAZE")
    Dprocessor = DuplicatesProcessor(extractor, matcher)
    
    # Получение уже обработанных изображений из базы данных
    processed_images = processed_repository.get_proc_images()
    processed_images_df = pd.DataFrame(processed_images)
    
    # Фильтрация входных изображений
    if len(processed_images_df) > 0:
        input_images = [img for img in input_images if img not in processed_images_df['filename'].values]
    
    # Обновление задачи
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.total_images = len(input_images)
        task.status = "in_progress"
        db.commit()
    
    # Основной цикл обработки
    last_img = None
    last_processed_image = None
    local_duplicates = []
    duplicate_series_name = ''
    
    for i, img_name in enumerate(input_images):
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
        img = preprocess_image(img)
        
        if last_img is not None:
            if Dprocessor.last_kp is None:
                score = Dprocessor.compare(last_img, img, config["match_threshold"])
            else:
                score = Dprocessor.compare_w_last(img, config["match_threshold"])
            
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
                    
                    if db_image:
                        db_image.is_duplicate = True
                        db_image.is_main_duplicate = True
                        db_image.processed_path = duplicates_dir
                        db.commit()
                        
                    local_duplicates.append(last_processed_image)
                    duplicate_series_name = last_processed_image.split(".")[0]
                
                # Копирование текущего дубликата
                duplicates_dir = os.path.join(output_dir, "duplicates", duplicate_series_name)
                dst = os.path.join(duplicates_dir, img_name)
                shutil.copy2(img_path, dst)
                
                # Создание записи в базе данных
                db_image = models.Image(
                    filename=img_name,
                    original_path=img_path,
                    processed_path=duplicates_dir,
                    task_id=task_id,
                    is_duplicate=True,
                    duplicate_group=last_processed_image,
                    validation_status="pending"
                )
                db.add(db_image)
                db.commit()
                
            else:
                # Проверка наличия серии дубликатов
                if len(local_duplicates) > 0:
                    # Определение лучшего изображения из серии
                    local_dup_imgs = []
                    for dup_name in local_duplicates:
                        dup_path = os.path.join(output_dir, "duplicates", duplicate_series_name, dup_name)
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
                        
                        # Копирование лучшего изображения в основную директорию
                        src = os.path.join(output_dir, "duplicates", duplicate_series_name, best_img_name)
                        dst = os.path.join(output_dir, best_img_name)
                        shutil.copy2(src, dst)
                        
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
                
                db_image = models.Image(
                    filename=img_name,
                    original_path=img_path,
                    processed_path=output_dir,
                    task_id=task_id,
                    is_duplicate=False,
                    validation_status="pending"
                )
                db.add(db_image)
                db.commit()
                
        else:
            # Первое изображение
            dst = os.path.join(output_dir, img_name)
            shutil.copy2(img_path, dst)
            
            db_image = models.Image(
                filename=img_name,
                original_path=img_path,
                processed_path=output_dir,
                task_id=task_id,
                is_duplicate=False,
                validation_status="pending"
            )
            db.add(db_image)
            db.commit()
            
        last_img = img
        last_processed_image = img_name
        
        # Обновление прогресса
        if task:
            task.progress = i + 1
            db.commit()
    
    # Завершение задачи
    if task:
        task.status = "completed"
        task.completed_at = datetime.utcnow()
        db.commit()

@router.get("/task/{task_id}")
def get_task_images(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Получение всех изображений задачи
    Требует аутентификацию
    Проверяет существование задачи и права доступа
    Возвращает список изображений (Image)
    """
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and task.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    images = db.query(models.Image).filter(models.Image.task_id == task_id).all()
    return images

@router.get("/{image_id}")
def get_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Получение изображения по ID
    Требует аутентификацию
    Проверяет существование изображения и права доступа
    Возвращает изображение (Image)
    """
    
    image = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    task = db.query(models.Task).filter(models.Task.id == image.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and task.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return image

@router.post("/{image_id}/validate")
def validate_image(
    image_id: int,
    validation_data: ImageValidation,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Валидация изображения
    Требует аутентификацию
    Проверяет существование изображения и права доступа
    Обновляет is_validated и validation_result
    Возвращает обновленное изображение (Image)
    """
    
    image = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    task = db.query(models.Task).filter(models.Task.id == image.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    image.is_validated = True
    image.validation_result = validation_data.validation_result
    image.validated_by = current_user.id
    image.validated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(image)
    
    return image

@router.post("/task/{task_id}/validate-all")
def validate_all_images(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Массовая валидация всех изображений задачи
    Требует аутентификацию
    Проверяет существование задачи и права доступа
    Обновляет is_validated для всех изображений задачи
    Возвращает сообщение об успешной валидации
    """
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db.query(models.Image).filter(models.Image.task_id == task_id).update({
        models.Image.is_validated: True,
        models.Image.validated_by: current_user.id,
        models.Image.validated_at: datetime.utcnow()
    })
    
    db.commit()
    
    return {"message": f"All images in task {task_id} have been validated"}

@router.get("/duplicates/{task_id}")
def get_duplicate_groups(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Получение групп дубликатов для задачи
    Требует аутентификацию
    Проверяет существование задачи и права доступа
    Группирует изображения по duplicate_group
    Возвращает структуру с группами дубликатов
    """
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and task.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Получаем все дубликаты задачи
    duplicate_images = db.query(models.Image).filter(
        models.Image.task_id == task_id,
        models.Image.is_duplicate == True
    ).all()
    
    # Группируем по duplicate_group
    duplicate_groups = {}
    for image in duplicate_images:
        group_id = image.duplicate_group
        if group_id not in duplicate_groups:
            duplicate_groups[group_id] = []
        duplicate_groups[group_id].append(image)
    
    return duplicate_groups

@router.post("/{image_id}/move-duplicate")
def move_image_from_duplicate_group(
    image_id: int,
    move_data: ImageMove,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Перемещение изображения из группы дубликатов
    Требует аутентификацию
    Проверяет существование изображения и права доступа
    Изменяет is_duplicate на False
    Обновляет путь в файловой системе
    Возвращает обновленное изображение (Image)
    """
    
    image = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    task = db.query(models.Task).filter(models.Task.id == image.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    if not image.is_duplicate:
        raise HTTPException(status_code=400, detail="Image is not a duplicate")
    
    # Определяем новый путь
    new_path = move_data.new_path if move_data.new_path else task.output_path
    
    # Перемещаем файл в файловой системе
    old_file_path = os.path.join(image.processed_path, image.filename)
    new_file_path = os.path.join(new_path, image.filename)
    
    if os.path.exists(old_file_path):
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        shutil.move(old_file_path, new_file_path)
    
    # Обновляем запись в базе данных
    image.is_duplicate = False
    image.processed_path = new_path
    image.duplicate_group = None
    
    db.commit()
    db.refresh(image)
    
    return image

@router.get("/progress/{task_id}")
def get_processing_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Получение прогресса обработки
    Требует аутентификацию
    Проверяет существование задачи и права доступа
    Возвращает JSON с полями: total, processed, duplicates_found, clusters_found, progress_percent
    """
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and task.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Получаем общее количество изображений в задаче
    total_images = db.query(models.Image).filter(models.Image.task_id == task_id).count()
    
    # Получаем количество обработанных изображений (валидированных)
    processed_images = db.query(models.Image).filter(
        models.Image.task_id == task_id,
        models.Image.is_validated == True
    ).count()
    
    # Получаем количество найденных дубликатов
    duplicates_found = db.query(models.Image).filter(
        models.Image.task_id == task_id,
        models.Image.is_duplicate == True
    ).count()
    
    # Получаем количество кластеров (уникальных групп дубликатов)
    clusters_found = db.query(models.Image.duplicate_group).filter(
        models.Image.task_id == task_id,
        models.Image.duplicate_group.isnot(None)
    ).distinct().count() or 0
    
    # Вычисляем процент прогресса
    progress_percent = 0
    if total_images > 0:
        progress_percent = round((processed_images / total_images) * 100, 2)
    
    return {
        "total": total_images,
        "processed": processed_images,
        "duplicates_found": duplicates_found,
        "clusters_found": clusters_found,
        "progress_percent": progress_percent
    }

@router.post("/{task_id}/process")
def start_image_processing(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Запуск обработки изображений для задачи"""
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.assigned_to != current_user.id and task.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    if task.status in ["in_progress", "completed", "validated"]:
        raise HTTPException(status_code=400, detail="Task is already in progress, completed or validated")
    
    # Загрузка конфигурации
    config = {
        "db_path": "processed_images.db",
        "match_threshold": 0.75,
        "duplicate_threshold": 0.7,
        "matcher": "BF",
        "feature_extractor": "KAZE"
    }
    
    # Добавление фоновой задачи
    background_tasks.add_task(
        process_images_task,
        task_id=task_id,
        input_dir=task.input_path,
        output_dir=task.output_path,
        db=db,
        config=config
    )
    
    return {"status": "processing started", "task_id": task_id}