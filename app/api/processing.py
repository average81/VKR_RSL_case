from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.api.auth import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.services.processing_service import ProcessingService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/processing",
    tags=["processing"],
    responses={404: {"description": "Not found"}}
)


@router.post("/{task_id}/start")
async def start_processing(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Запуск двухэтапной обработки изображений
    """
    try:
        processing_service = ProcessingService(db)
        result = await processing_service.start_processing(task_id, current_user)
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting processing for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{task_id}/status")
async def get_processing_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение статуса обработки
    """
    try:
        processing_service = ProcessingService(db)
        status_info = await processing_service.get_status(task_id, current_user)
        
        if status_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{task_id}/cancel")
async def cancel_processing(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Отмена обработки
    """
    try:
        processing_service = ProcessingService(db)
        result = await processing_service.cancel_processing(task_id, current_user)
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling processing for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )