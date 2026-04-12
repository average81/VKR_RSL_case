from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.api.auth import get_current_user, check_group_leader, check_task_access
from app.models.task import Task, TaskCreate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])

task_service = TaskService()


@router.get("/", response_model=List[Task])
async def get_tasks(current_user = Depends(get_current_user)):
    """
    Получение списка всех задач.
    Для начальника группы - все задачи, для сотрудника - только его задачи.
    """
    return await task_service.get_user_tasks(current_user)


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int, current_user = Depends(get_current_user)):
    """
    Получение задачи по ID.
    Проверяет существование задачи и права доступа.
    """
    task = await task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    if not check_task_access(current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return task


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_create: TaskCreate,
    current_user = Depends(get_current_user),
    _ = Depends(check_group_leader)
):
    """
    Создание новой задачи.
    Доступно только начальнику группы.
    """
    return await task_service.create_task(task_create, current_user)


@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskCreate,
    current_user = Depends(get_current_user),
    _ = Depends(check_group_leader)
):
    """
    Обновление задачи.
    Доступно только начальнику группы.
    """
    task = await task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    return await task_service.update_task(task_id, task_update)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user = Depends(get_current_user),
    _ = Depends(check_group_leader)
):
    """
    Удаление задачи.
    Доступно только начальнику группы.
    """
    task = await task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    await task_service.delete_task(task_id)
    return {"message": "Task deleted successfully"}


@router.post("/{task_id}/start", response_model=Task)
async def start_task_processing(
    task_id: int,
    current_user = Depends(get_current_user)
):
    """
    Запуск обработки задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task = await task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    if not check_task_access(current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return await task_service.start_task(task_id)


@router.post("/{task_id}/complete", response_model=Task)
async def complete_task(
    task_id: int,
    current_user = Depends(get_current_user)
):
    """
    Завершение обработки задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task = await task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    if not check_task_access(current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return await task_service.complete_task(task_id)


@router.post("/{task_id}/validate", response_model=Task)
async def validate_task(
    task_id: int,
    current_user = Depends(get_current_user)
):
    """
    Валидация результатов задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task = await task_service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    if not check_task_access(current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return await task_service.validate_task(task_id)