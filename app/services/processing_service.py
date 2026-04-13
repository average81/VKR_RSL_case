from typing import Optional
import logging
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException

from app.models.task import Task
from app.database import get_db
from app.api.auth import get_current_active_user, check_task_access
from app.api.images import start_image_processing as start_duplicates_processing
from app.api.grouping import start_grouping as start_clustering

# Настройка логирования
logger = logging.getLogger(__name__)

class ProcessingService:
    """
    Сервис для управления двухэтапной обработкой изображений.
    
    Первый этап: поиск дубликатов через images.router
    Второй этап: кластеризация через grouping.router
    """
    
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
    
    def start_two_stage_processing(self, task_id: int, current_user = Depends(get_current_active_user)) -> dict:
        """
        Запуск двухэтапной обработки изображений.
        
        Args:
            task_id: Идентификатор задачи
            current_user: Текущий пользователь (автоматически внедряется)
            
        Returns:
            Словарь с результатом запуска обработки
            
        Raises:
            HTTPException: При ошибках проверки прав доступа или статуса задачи
        """
        try:
            # Получение задачи
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Проверка прав доступа
            if not check_task_access(current_user, task):
                raise HTTPException(status_code=403, detail="Not enough permissions")
            
            # Проверка статуса задачи
            if task.status in ["in_progress", "completed", "validated"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Task is already {task.status}"
                )
            
            # Обновление статуса задачи и этапа
            task.status = "in_progress"
            task.stage = 1  # Первый этап - поиск дубликатов
            self.db.commit()
            
            logger.info(f"Запуск двухэтапной обработки для задачи {task_id}")
            
            # Запуск первого этапа - поиск дубликатов
            duplicates_result = start_duplicates_processing(
                task_id=task_id,
                background_tasks=None,  # Будет обработано в роутере
                db=self.db,
                current_user=current_user
            )
            
            # При успешном запуске первого этапа, обновляем статус
            task.stage = 1
            self.db.commit()
            
            return {
                "message": "Two-stage processing started",
                "task_id": task_id,
                "stage": 1,
                "duplicates_processing": duplicates_result
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка при запуске двухэтапной обработки для задачи {task_id}: {str(e)}")
            # Откат изменений в случае ошибки
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_processing_status(self, task_id: int, current_user = Depends(get_current_active_user)) -> dict:
        """
        Получение статуса двухэтапной обработки.
        
        Args:
            task_id: Идентификатор задачи
            current_user: Текущий пользователь (автоматически внедряется)
            
        Returns:
            Словарь с информацией о статусе обработки
            
        Raises:
            HTTPException: При ошибках проверки прав доступа
        """
        try:
            # Получение задачи
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Проверка прав доступа
            if not check_task_access(current_user, task):
                raise HTTPException(status_code=403, detail="Not enough permissions")
            
            # Получение прогресса обработки
            progress = self._get_progress_info(task_id)
            
            return {
                "task_id": task_id,
                "status": task.status,
                "stage": task.stage,
                "progress": progress,
                "updated_at": task.updated_at
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении статуса обработки для задачи {task_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def cancel_processing(self, task_id: int, current_user = Depends(get_current_active_user)) -> dict:
        """
        Отмена двухэтапной обработки.
        
        Args:
            task_id: Идентификатор задачи
            current_user: Текущий пользователь (автоматически внедряется)
            
        Returns:
            Словарь с результатом отмены обработки
            
        Raises:
            HTTPException: При ошибках проверки прав доступа или статуса задачи
        """
        try:
            # Получение задачи
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Проверка прав доступа
            if not check_task_access(current_user, task):
                raise HTTPException(status_code=403, detail="Not enough permissions")
            
            # Проверка возможности отмены
            if task.status not in ["in_progress", "pending"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot cancel task with status {task.status}"
                )
            
            # Обновление статуса задачи
            task.status = "cancelled"
            task.completed_at = None
            self.db.commit()
            
            logger.info(f"Обработка для задачи {task_id} отменена пользователем {current_user.username}")
            
            return {
                "message": "Processing cancelled",
                "task_id": task_id,
                "status": "cancelled"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка при отмене обработки для задачи {task_id}: {str(e)}")
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    def _get_progress_info(self, task_id: int) -> dict:
        """
        Получение детальной информации о прогрессе обработки.
        
        Args:
            task_id: Идентификатор задачи
            
        Returns:
            Словарь с информацией о прогрессе
        """
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from app.api.images import get_processing_progress
        
        try:
            # Получаем прогресс из API images
            progress = get_processing_progress(task_id, self.db)
            return progress
        except Exception as e:
            logger.error(f"Ошибка при получении прогресса для задачи {task_id}: {str(e)}")
            return {
                "total": 0,
                "processed": 0,
                "duplicates_found": 0,
                "clusters_found": 0,
                "progress_percent": 0
            }
    
    def _complete_stage_one(self, task_id: int) -> None:
        """
        Завершение первого этапа и подготовка ко второму этапу.
        
        Args:
            task_id: Идентификатор задачи
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.stage = 2  # Второй этап - кластеризация
            self.db.commit()
            logger.info(f"Завершен первый этап обработки для задачи {task_id}")
    
    def _complete_stage_two(self, task_id: int) -> None:
        """
        Завершение второго этапа и завершение задачи.
        
        Args:
            task_id: Идентификатор задачи
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.stage = 2
            from datetime import datetime
            task.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Завершена двухэтапная обработка для задачи {task_id}")
    
    def _start_clustering(self, task_id: int) -> dict:
        """
        Запуск второго этапа - кластеризации.
        
        Args:
            task_id: Идентификатор задачи
            
        Returns:
            Результат запуска кластеризации
        """
        try:
            # Запуск кластеризации
            clustering_result = start_clustering(
                task_id=str(task_id),
                background_tasks=None,
                db=self.db
            )
            
            logger.info(f"Запущена кластеризация для задачи {task_id}")
            return clustering_result
            
        except Exception as e:
            logger.error(f"Ошибка при запуске кластеризации для задачи {task_id}: {str(e)}")
            raise