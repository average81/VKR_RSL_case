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
    
    task_service = TaskService(db)
    tasks = task_service.get_user_tasks(current_user.id, current_user)
    
    # Extract query parameters from request
    status_filter = request.query_params.get('status', '')
    stage_filter = request.query_params.get('stage', '')
    search_query = request.query_params.get('q', '')
    page = int(request.query_params.get('page', 1))
    
    users = db.query(User).all()
    
    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={
            "request": request,
            "current_user": current_user,
            "tasks": tasks,
            "users": users,
            "page": page,
            "total_pages": 1,
            "status": status_filter,
            "stage": stage_filter,
            "q": search_query,
            "can_create_task": can_create_task
        }
    )


@router.get("/{task_id}", response_model=TaskSchema)
async def get_task(request: Request, task_id: int, current_user = Depends(get_current_user), db = Depends(get_db)):
    """
    Получение задачи по ID.
    Проверяет существование задачи и права доступа.
    """
    task_service = TaskService(db)
    task = task_service.get_task_by_id(task_id, current_user)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    if not check_task_access(request, current_user, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return task


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
        name=title,
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