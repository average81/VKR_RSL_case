from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from starlette.responses import RedirectResponse
from typing import List

from app.api.auth import get_current_user, check_group_leader, check_task_access
from app.models.task import Task, TaskCreate, TaskSchema
from app.models.enums import TaskType
from app.models.user import User
from app.services.task_service import TaskService
from app.database import get_db
from app.main import templates

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/")
async def get_tasks(request: Request, current_user = Depends(get_current_user), db = Depends(get_db)):
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
async def get_task(request: Request, task_id: int, current_user = Depends(get_current_user), db = Depends(get_db)):
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
    stats = {}  # Здесь должна быть логика получения статистики
    recent_events = []  # Здесь должна быть логика получения событий
    progress_history = []  # Здесь должна быть логика получения истории прогресса
    
    # Если задача не активна, не запускаем автоматическое обновление
    if task.status not in ['in_progress', 'pending']:
        progress_history = []
        recent_events = []
    else:
        # Сохраняем только последние 20 точек для графика
        progress_history = progress_history[-20:]
    
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
            "recent_events": recent_events,
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
    output_path: str = Form(...),
    stage: str = Form(...),
    owner_id: int = Form(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    _ = Depends(check_group_leader)
):
    """
    Создание новой задачи через форму.
    Принимает поля формы и перенаправляет на /tasks после успешного создания.
    """
    task_create = TaskCreate(
        title=title,
        description=description,
        input_path=input_path,
        output_path=output_path,
        stage=int(stage),
        owner_id=owner_id,
        output_path_stage2=output_path,
    )
    
    assigned_user = db.query(User).filter(User.id == task_create.owner_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task_service = TaskService(db)
    task = task_service.create_task(current_user, task_create)
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)


@router.put("/{task_id}", response_model=TaskSchema)
async def update_task(
    request: Request,
    task_id: int,
    task_update: TaskCreate,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    _ = Depends(check_group_leader)
):
    """
    Обновление задачи.
    Доступно только начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    return task_service.update_task(task_id, task_update)


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


@router.post("/{task_id}/start", response_model=TaskSchema)
async def start_task_processing(
    request: Request,
    task_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Запуск обработки задачи.
    Доступно сотруднику (если задача назначена ему) или начальнику группы.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return task_service.start_task(task_id)


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

