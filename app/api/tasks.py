from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form, Body
from starlette.responses import RedirectResponse
from typing import List, Dict, Any, Optional
import json

from pydantic import BaseModel

from app.api.auth import get_current_user, get_current_user_optional, check_group_leader, check_task_access
from app.models.task import Task, TaskCreate, TaskSchema
from app.models.enums import TaskType
from app.models.user import User
from app.models.image import Image
from app.services.task_service import TaskService
from app.database import get_db
from app.main import templates
import asyncio

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/")
async def get_tasks(request: Request, response: Response, current_user = Depends(get_current_user_optional), db = Depends(get_db)):
    """
    Получение списка всех задач.
    Для начальника группы - все задачи, для сотрудника - только его задачи.
    Если пользователь не найден в базе, удаляет cookie и перенаправляет на страницу авторизации.
    """
    if not current_user:
        # Создаем ответ с перенаправлением и удаляем cookie
        redirect_response = RedirectResponse(url="/auth/login", status_code=303)
        redirect_response.delete_cookie(key="access_token")
        return redirect_response

    # Проверяем права пользователя на создание задач
    can_create_task = hasattr(current_user, 'is_group_leader') and current_user.is_group_leader

    # Extract query parameters from request
    status_filter = request.query_params.get('status', '')
    stage_filter = request.query_params.get('stage', '')
    search_query = request.query_params.get('q', '')
    owner_id_filter = request.query_params.get('owner_id', '')
    page = max(1, int(request.query_params.get('page', 1)))
    per_page = 12  # Number of tasks per page

    # Get filtered tasks
    task_service = TaskService(db)

    # Для начальника группы получаем все задачи без ограничения по user_id
    if hasattr(current_user, 'is_group_leader') and current_user.is_group_leader:
        # Получаем задачи, созданные этим начальником группы
        tasks = task_service.task_repo.get_tasks_by_validator_id(current_user.id)
        # Добавляем задачи, назначенные ему лично
        own_tasks = task_service.task_repo.get_tasks_by_user_id(current_user.id)
        # Объединяем списки без дубликатов
        task_dict = {task.id: task for task in tasks}
        for task in own_tasks:
            task_dict[task.id] = task
        tasks = list(task_dict.values())

        # Применяем фильтры к объединенному списку
        if status_filter:
            tasks = [task for task in tasks if task.status == status_filter]
        if stage_filter:
            tasks = [task for task in tasks if task.stage == int(stage_filter)]
        if search_query:
            tasks = [task for task in tasks if
                   search_query.lower() in task.title.lower() or
                   search_query.lower() in task.description.lower() if task.description]
        if owner_id_filter:
            tasks = [task for task in tasks if task.owner_id == int(owner_id_filter)]
    else:
        # Для обычных пользователей - только их задачи
        tasks = task_service.get_user_tasks(
            current_user.id,
            current_user,
            status=status_filter if status_filter else None,
            stage=stage_filter if stage_filter else None,
            search_query=search_query if search_query else None,
            owner_id=int(owner_id_filter) if owner_id_filter else None
        )

    # Calculate pagination
    total_tasks = len(tasks)
    total_pages = max(1, (total_tasks + per_page - 1) // per_page)

    # Apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_tasks = tasks[start_idx:end_idx]

    users = db.query(User).all()

    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={
            "request": request,
            "current_user": current_user,
            "tasks": paginated_tasks,
            "users": users,
            "page": page,
            "total_pages": total_pages,
            "status": status_filter,
            "stage": stage_filter,
            "q": search_query,
            "can_create_task": can_create_task
        }
    )


@router.get("/{task_id}")
async def get_task(request: Request, response: Response, task_id: int, current_user = Depends(get_current_user_optional), db = Depends(get_db)):
    """
    Получение задачи по ID.
    Возвращает страницу с описанием задачи, если задача найдена и есть права доступа.
    В противном случае возвращает сообщение об ошибке или перенаправляет на страницу входа.
    """
    # Проверяем аутентификацию
    if not current_user:
        # Создаем ответ с перенаправлением и удаляем cookie
        redirect_response = RedirectResponse(url="/auth/login", status_code=303)
        redirect_response.delete_cookie(key="access_token")
        return redirect_response
    """
    Получение задачи по ID.
    Возвращает страницу с описанием задачи, если задача найдена и есть права доступа.
    В противном случае возвращает сообщение об ошибке.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        return templates.TemplateResponse(
            request=request,
            name="task_detail.html",
            context={
                "request": request,
                "current_user": current_user,
                "error": "Задача не найдена"
            }
        )

    if not check_task_access(request, current_user, task):
        return templates.TemplateResponse(
            request=request,
            name="task_detail.html",
            context={
                "request": request,
                "current_user": current_user,
                "error": "Доступ запрещен"
            }
        )

    # Получаем статистику и другие данные для задачи
    stats = {
        'total_images': 0,
        'processed_images': 0,
        'validated_images': 0,
        'duplicate_images': 0,
        'title_pages': 0
    }
    progress_history = []  # Инициализация истории прогресса

    # Получаем все изображения задачи
    images = db.query(Image).filter(Image.task_id == task.id).all()

    # Обновляем статистику
    stats['total_images'] = task.total_images
    stats['processed_images'] = task.progress
    stats['validated_images'] = sum(1 for image in images if image.validation_status not in ['pending', None])
    stats['duplicate_images'] = sum(1 for image in images if image.is_duplicate and not image.is_main_duplicate)
    stats['title_pages'] = sum(1 for image in images if image.is_title_page)

    # Если задача в активном статусе, формируем историю прогресса
    if task.status in ['in_progress', 'pending', 'completed', 'paused']:
        # Сортируем изображения по времени обновления
        sorted_images = sorted(images, key=lambda x: x.updated_at or x.created_at)

        processed_count = 0
        for image in sorted_images:
            # Увеличиваем счётчик, если изображение обработано или валидировано
            if image.processed_path is not None or (image.validation_status is not None and image.validation_status != 'pending'):
                processed_count += 1

            # Форматируем время как строку в формате 'YYYY-MM-DD HH:MM:SS'
            if image.updated_at:
                timestamp_str = image.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            elif image.created_at:
                timestamp_str = image.created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                continue  # Пропускаем, если оба поля None

            progress_history.append({
                'timestamp': timestamp_str,
                'progress': processed_count
            })

    while len(progress_history)>100 :
        progress_history = progress_history[::2]
    # Получаем владельца задачи
    owner = db.query(User).filter(User.id == task.owner_id).first()

    return templates.TemplateResponse(
        request=request,
        name="task_detail.html",
        context={
            "request": request,
            "task": task,
            "owner": owner,
            "current_user": current_user,
            "stats": stats,
            "progress_history": progress_history
        }
    )



@router.post("/", response_model=TaskSchema, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: Request,
    task_create: TaskCreate,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    _ = Depends(check_group_leader)
):
    """
    Создание новой задачи.
    Доступно только начальнику группы.
    """
    assigned_user = db.query(User).filter(User.id == task_create.owner_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="User not found")

    task_service = TaskService(db)
    return task_service.create_task(TaskType.TWO_STAGE_PROCESSING, current_user, assigned_user, task_create.description)


@router.post("/create")
async def create_task_form(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    input_path: str = Form(...),
    stage: str = Form(...),
    owner_id: int = Form(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    _ = Depends(check_group_leader)
):
    """
    Создание новой задачи через форму.
    Принимает поля формы и перенаправляет на /tasks после успешного создания.
    Output path генерируется автоматически в формате output/task_id/stage1 или output/task_id/stage2
    """
    task_create = TaskCreate(
        title=title,
        description=description,
        input_path=input_path,
        stage=int(stage),
        owner_id=owner_id,
    )

    assigned_user = db.query(User).filter(User.id == task_create.owner_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="User not found")

    task_service = TaskService(db)
    task = task_service.create_task(current_user, task_create)
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)


@router.delete("/{task_id}")
async def delete_task(
    request: Request,
    task_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    _ = Depends(check_group_leader)
):
    """
    Удаление задачи.
    Доступно только начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task_service.delete_task(task_id)
    return {"message": "Task deleted successfully"}



@router.post("/{task_id}/complete", response_model=TaskSchema)
async def complete_task(
    request: Request,
    task_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Завершение обработки задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return task_service.complete_task(task_id)


@router.post("/{task_id}/validate", response_model=TaskSchema)
async def validate_task(
    request: Request,
    task_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Валидация результатов задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return task_service.validate_task(task_id)


@router.post("/{task_id}/cancel")
async def cancel_task(
    request: Request,
    task_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
) -> TaskSchema:

    """
    Отмена задачи.
    Доступно владельцу задачи или суперпользователю.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return task_service.cancel_task(task_id, current_user)


@router.post("/{task_id}/pause")
async def pause_task(
        request: Request,
        task_id: int,
        current_user = Depends(get_current_user),
        db = Depends(get_db)
) -> TaskSchema:
    """
    Приостановка обработки задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return task_service.pause_task(task_id, current_user)


@router.post("/{task_id}/resume")
async def resume_task(
        request: Request,
        task_id: int,
        current_user = Depends(get_current_user),
        db = Depends(get_db)
) -> TaskSchema:
    """
    Возобновление приостановленной задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return task_service.resume_task(task_id, current_user)


# Region Processing Settings Handlers
@router.get("/settings/{task_id}")
async def get_processing_settings(
    request: Request,
    task_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Отображение страницы настроек обработки
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Default settings
    default_settings = {
        "feature_detector": "SIFT",
        "matcher": "FLANN",
        "match_threshold": 0.7,
        "duplicate_threshold": 0.8,
        "duplicate_quality": "BRISQUE",
        "clusterfeatureDetector": "SIFT",
        "clustermatcher": "FLANN",
        "cluster_threshold": 0.5,
        "clustermatchThreshold": 0.7
    }

    # Get saved settings from task
    settings = default_settings
    if task:
        # Map database fields to frontend settings
        db_to_frontend = {
            'feature_extractor_stage1': 'feature_detector',
            'feature_extractor_stage2': 'clusterfeatureDetector',
            'matcher_stage1': 'matcher',
            'matcher_stage2': 'clustermatcher',
            'match_threshold_stage1': 'match_threshold',
            'duplicate_threshold_stage1': 'duplicate_threshold',
            'duplicate_threshold_stage2': 'clustermatchThreshold',
            'quality_algorithm': 'duplicate_quality'
        }
        
        # Apply values from database fields if they exist
        for db_field, frontend_field in db_to_frontend.items():
            db_value = getattr(task, db_field, None)
            if db_value is not None and frontend_field in settings:
                settings[frontend_field] = db_value

    return templates.TemplateResponse(
        request=request,
        name="processing_settings.html",
        context={
            "request": request,
            "current_user": current_user,
            "task": task,
            "settings": settings
        }
    )

class ProcessingSettings(BaseModel):
    feature_detector: str = "SIFT"
    matcher: str = "FLANN"
    match_threshold: float = 0.7
    duplicate_threshold: float = 0.8
    duplicate_quality: str = "BRISQUE"
    clusterfeatureDetector: str = "SIFT"
    clustermatcher: str = "FLANN"
    cluster_threshold: float = 0.5
    clustermatchThreshold: float = 0.7

@router.post("/settings/{task_id}")
async def save_processing_settings(
    request: Request,
    task_id: int,
    settings: ProcessingSettings,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Сохранение настроек обработки
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Map frontend settings to database fields
    frontend_to_db = {
        'feature_detector': 'feature_extractor_stage1',
        'matcher': 'matcher_stage1',
        'match_threshold': 'match_threshold_stage1',
        'duplicate_threshold': 'duplicate_threshold_stage1',
        'duplicate_quality': 'quality_algorithm',
        'clusterfeatureDetector': 'feature_extractor_stage2',
        'clustermatcher': 'matcher_stage2',
        'cluster_threshold': 'cluster_threshold',
        'clustermatchThreshold': 'duplicate_threshold_stage2'
    }
    
    # Apply settings to task model fields
    for frontend_field, db_field in frontend_to_db.items():
        if hasattr(task, db_field):
            setattr(task, db_field, getattr(settings, frontend_field))
    
    db.commit()
    db.refresh(task)
    
    return {"message": "Настройки успешно сохранены"}

