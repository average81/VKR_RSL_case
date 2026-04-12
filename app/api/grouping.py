from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
import yaml
import os
from typing import Dict, Any
import logging

from processor.duplicates_processor import DuplicatesProcessor
from app.models.image import Image
from app.database import get_db
from app.api.auth import get_current_user

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание роутера с префиксом /grouping
router = APIRouter(prefix="/grouping", tags=["grouping"])

# Загрузка конфигурации
config_path = "config_logo.yml"
if not os.path.exists(config_path):
    raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)


def process_grouping_task(task_id: str, db: Session, output_path: str):
    """
    Фоновая задача для кластеризации изображений по выпускам газет/журналов на основе логотипов.
    
    Args:
        task_id: Идентификатор задачи
        db: Сессия базы данных
        output_path: Путь для сохранения результатов
    """
    try:
        logger.info(f"Запуск кластеризации для задачи {task_id}")
        
        # Создание процессора дубликатов с конфигурацией из config_logo.yml
        processor = DuplicatesProcessor(
            db_path=config['db_path'],
            duplicate_threshold=config['duplicate_threshold'],
            match_threshold=config['match_threshold'],
            matcher=config['matcher'],
            feature_extractor=config['feature_extractor']
        )
        
        # Получение всех изображений для данной задачи
        images = db.query(Image).filter(Image.task_id == task_id).all()
        
        if not images:
            logger.warning(f"Нет изображений для кластеризации в задаче {task_id}")
            return
        
        # Извлечение путей к изображениям
        image_paths = [img.path for img in images]
        
        # Выполнение кластеризации
        clusters = processor.process_images(image_paths)
        
        # Обновление информации об изображениях в базе данных
        for cluster_id, image_paths_in_cluster in clusters.items():
            for image_path in image_paths_in_cluster:
                image = db.query(Image).filter(Image.path == image_path).first()
                if image:
                    # Пометка первого изображения в кластере как титульной страницы
                    image.is_cover = image_path == image_paths_in_cluster[0]
                    image.issue_id = cluster_id
                    
        # Сохранение изменений в базе данных
        db.commit()
        
        # Сохранение результатов кластеризации в output_path
        results_path = os.path.join(output_path, "grouping_results.yml")
        with open(results_path, 'w', encoding='utf-8') as f:
            yaml.dump({
                "task_id": task_id,
                "total_clusters": len(clusters),
                "clusters": clusters
            }, f, allow_unicode=True, default_flow_style=False)
        
        logger.info(f"Кластеризация завершена для задачи {task_id}. Найдено {len(clusters)} кластеров.")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении кластеризации для задачи {task_id}: {str(e)}")
        db.rollback()
        raise

@router.post("/{task_id}/start")
async def start_grouping(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Dict[Any, Any] = Depends(get_current_user)
):
    """
    Запуск процесса кластеризации по выпускам газет/журналов на основе логотипов.
    """
    # Проверка существования задачи (наличие хотя бы одного изображения с таким task_id)
    image_count = db.query(Image).filter(Image.task_id == task_id).count()
    if image_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена или не содержит изображений"
        )
    
    # Определение output_path (предполагаем, что он основан на task_id)
    output_path = os.path.join("output2", task_id)
    os.makedirs(output_path, exist_ok=True)
    
    # Добавление фоновой задачи
    background_tasks.add_task(process_grouping_task, task_id, db, output_path)
    
    return {
        "message": "Процесс кластеризации запущен",
        "task_id": task_id,
        "output_path": output_path
    }