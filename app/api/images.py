from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import os
import shutil
from app.background_tasks import process_images_task, ACTIVE_PROCESSES, process_logos_task
from app import models
from app.database import get_db, SQLALCHEMY_DATABASE_URL
from app.api.auth import get_current_active_user
from app.models.image import  ImageValidation, ImageMove
import asyncio

import re
from datetime import datetime

router = APIRouter(prefix="/images")



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
    
    if task.owner_id != current_user.id and not current_user.is_superuser:
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
    
    if task.owner_id != current_user.id and not current_user.is_superuser:
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
    
    if task.owner_id != current_user.id and not current_user.is_superuser:
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
    
    if task.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Получаем общее количество изображений в задаче
    total_images = task.total_images
    processed_images = task.progress

    # Получаем количество найденных дубликатов
    duplicates_found = db.query(models.Image).filter(
        models.Image.task_id == task_id,
        models.Image.is_duplicate == True,
        models.Image.is_main_duplicate == False
    ).count()

    # Получаем количество кластеров (уникальных групп дубликатов)
    clusters_found = db.query(models.Image.duplicate_group).filter(
        models.Image.task_id == task_id,
        models.Image.duplicate_group.isnot(None)
    ).distinct().count() or 0
    # Вычисляем процент прогресса
    progress_percent = 0
    if total_images > 0:
        progress_percent = int((processed_images / total_images) * 100)
    
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Запуск обработки изображений для задачи"""
    
    # Импорт asyncio здесь, чтобы избежать проблем с импортом
    import asyncio
    """Запуск обработки изображений для задачи"""

    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    if task.status in ["in_progress", "completed", "validated"]:
        raise HTTPException(status_code=400, detail="Task is already in progress, completed or validated")
    
    # Создаем событие для остановки
    shutdown_event = asyncio.Event()
    
    # Проверка этапа задачи и запуск соответствующего процесса
    if task.stage == 1:
        # Загрузка конфигурации для первого этапа (поиск дубликатов)
        config = {
            "db_path": "processed_images.db",
            "match_threshold": task.match_threshold_stage1 or 0.75,
            "duplicate_threshold": task.duplicate_threshold_stage1 or 0.7,
            "matcher": task.matcher_stage1 or "BF",
            "feature_extractor": task.feature_extractor_stage1 or "KAZE"
        }
        
        # Запуск обработки изображений для поиска дубликатов
        import threading
        threading.Thread(target=process_images_task, kwargs={
            "task_id": task_id,
            "input_dir": task.input_path,
            "output_dir": task.output_path,
            "db_url": SQLALCHEMY_DATABASE_URL,
            "config": config,
            "shutdown_event": shutdown_event
        }, daemon=True).start()
        
    elif task.stage == 2:
        # Загрузка конфигурации для второго этапа (группировка по логотипам)
        config = {
            "db_path": "processed_images.db",
            "match_threshold": task.match_threshold_stage2 or 0.75,
            "duplicate_threshold": task.duplicate_threshold_stage2 or 0.7,
            "matcher": task.matcher_stage2 or "BF",
            "feature_extractor": task.feature_extractor_stage2 or "KAZE"
        }
        
        # Запуск группировки по логотипам
        input_dir = task.input_path if not task.validate_stage1 else task.output_path
        
        import threading
        threading.Thread(target=process_logos_task, kwargs={
            "task_id": task_id,
            "input_dir": input_dir,
            "output_dir": task.output_path_stage2,
            "config": config,
            "logos_path": task.logos_path
        }, daemon=True).start()
    
    # Сохраняем событие остановки для задачи
    ACTIVE_PROCESSES[task_id]['shutdown_event'] = shutdown_event
    return {"status": "processing started", "task_id": task_id}