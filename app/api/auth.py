from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from starlette.responses import RedirectResponse
import os

from app import database, models
from app.database import get_db
from app.models.user import UserBase, UserSchema, UserCreate
from app.models.task import Task
from app.models.image import Image
from app.models import User
from app.settings import settings
from app.main import templates
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Dict, Optional

# Опциональная зависимость для получения пользователя без ошибки 401
security = HTTPBearer(auto_error=False)

async def get_current_user_optional(
        request: Request,
        response: Response,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            user = get_user(db, username=username)
            if user is None:
                # Удаляем cookie, если пользователь не найден
                response.delete_cookie(key="access_token")
            return user
        except JWTError:
            # Удаляем cookie при ошибке декодирования токена
            response.delete_cookie(key="access_token")
            return None
    return None

router = APIRouter(prefix="/auth")

cpwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def verify_password(plain_password, hashed_password):
    return cpwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    print(password,len(password))
    return cpwd_context.hash(password)

def get_user(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

@router.get("/me", response_model=UserSchema)
def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)):
    # Получаем токен из cookie
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Убираем префикс "Bearer " если он есть
    if token.startswith("Bearer "):
        token = token[7:]
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = UserBase(username=username)
    except JWTError:
        # Если токен невалиден, удаляем cookie и возвращаем ошибку
        response.delete_cookie(key="access_token")
        raise credentials_exception
    
    user = get_user(db, username=token_data.username)
    if user is None:
        # Если пользователь не найден в базе, удаляем cookie и возвращаем ошибку
        response.delete_cookie(key="access_token")
        raise credentials_exception
    return user

def get_current_active_user(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_superuser(request: Request, current_user: models.User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return current_user


def check_group_leader(request: Request, current_user: models.User = Depends(get_current_active_user)):
    if not hasattr(current_user, 'is_group_leader') or not current_user.is_group_leader:
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return current_user


def check_task_access(request: Request, current_user: models.User, task: models.Task) -> bool:
    """
    Проверяет права доступа к задаче.
    
    Args:
        request: Объект запроса
        current_user: Текущий пользователь
        task: Задача для проверки доступа
    
    Returns:
        True если доступ разрешен, False в противном случае
    """
    # Начальник группы имеет доступ ко всем задачам
    if hasattr(current_user, 'is_group_leader') and current_user.is_group_leader:
        return True
    
    # Сотрудник имеет доступ только к своим задачам
    return task.owner_id == current_user.id

@router.get("/login")
def get_login_form(
        request: Request,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user_optional)  # Может быть None
):
    # Извлекаем flashed messages
    flashes = request.session.pop("_flashes", [])
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "current_user": current_user,
            "flashes": flashes
        }
    )

@router.post("/login")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        request.session["_flashes"] = [("error", "Неверное имя пользователя или пароль")]
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "current_user": None,
                "flashes": [("error", "Неверное имя пользователя или пароль")]
            }
        )
    
    # Получаем все задачи пользователя
    from app.services.task_service import TaskService
    task_service = TaskService(db)
    user_tasks = task_service.get_user_tasks(user.id, user)
    
    # Переводим все запущенные задачи в статус "ожидание"
    for task in user_tasks:
        if task.status == "in_progress":
            try:
                task_service.update_task_status(task.id, "pending", user)
                print(f"Задача {task.id} переведена в статус 'ожидание'")
            except Exception as e:
                print(f"Ошибка при обновлении статуса задачи {task.id}: {str(e)}")
    
    access_token_expires = timedelta(minutes=600)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Перенаправляем на главную страницу, которая сама перенаправит на задачи
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        max_age=600*60, 
        expires=600*60,
        secure=False,
        samesite="lax"
    )
    return response

@router.get("/register")
def get_register_form(
        request: Request,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user_optional)  # Может быть None
):
    """
    Возвращает форму регистрации. Передаёт информацию о текущем пользователе в шаблон.
    Если пользователь не авторизован — current_user будет None.
    """
    # Извлекаем flashed messages
    flashes = request.session.pop("_flashes", [])
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "request": request,
            "current_user": current_user,
            "flashes": flashes
        }
    )

@router.get("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Обработчик выхода из системы.
    При выходе приостанавливает все запущенные задачи пользователя и удаляет cookie с токеном доступа.
    """
    current_user = get_current_user(request, response, db)
    if current_user:
        # Получаем все запущенные задачи пользователя
        from app.services.task_service import TaskService
        task_service = TaskService(db)
        user_tasks = task_service.get_user_tasks(current_user.id, current_user)
        
        # Приостанавливаем все задачи в статусе "in_progress"
        for task in user_tasks:
            if task.status == "in_progress":
                try:
                    task_service.pause_task(task.id, current_user)
                except Exception as e:
                    # Логируем ошибку, но не прерываем процесс выхода
                    print(f"Error pausing task {task.id}: {str(e)}")
    
    # Удаляем cookie и перенаправляем
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response


@router.post("/register", response_model=UserSchema)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Проверяем, есть ли уже суперпользователи в системе
    existing_superuser = db.query(models.User).filter(models.User.is_superuser == True).first()
    if user.is_superuser and existing_superuser:
        raise HTTPException(
            status_code=400,
            detail="Cannot create superuser: another superuser already exists"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=user.is_superuser
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/profile", response_class=HTMLResponse)
def get_user_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Получение профиля пользователя с статистикой по задачам.
    """
    # Получаем информацию о пользователе
    user = current_user
    
    # Статистика по назначенным задачам
    task_stats = db.query(
        Task.status,
        Task.stage,
        func.count(Task.id)
    ).filter(
        Task.owner_id == user.id
    ).group_by(
        Task.status, Task.stage
    ).all()
    
    # Инициализируем статистику
    stats = {
        'pending': 0,
        'in_progress': 0,
        'completed': 0,
        'validated': 0,
        'stage1': 0,
        'stage2': 0,
        'total': 0
    }
    
    # Заполняем статистику по статусам и этапам
    for status, stage, count in task_stats:
        if status in stats:
            stats[status] += count
        if stage == 1:
            stats['stage1'] += count
        elif stage == 2:
            stats['stage2'] += count
        stats['total'] += count
    
    # Статистика для начальника группы (задачи, назначенные им)
    leader_stats: Optional[Dict] = None
    if user.is_group_leader:
        leader_task_stats = db.query(
            Task.status,
            func.count(Task.id)
        ).filter(
            Task.validator_id == user.id  # Используем validator_id как создателя задачи
        ).group_by(
            Task.status
        ).all()
        
        leader_stats = {
            'pending': 0,
            'in_progress': 0,
            'completed': 0,
            'validated': 0,
            'total': 0
        }
        
        for status, count in leader_task_stats:
            if status in leader_stats:
                leader_stats[status] += count
            leader_stats['total'] += count
    
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "request": request,
            "user": user,
            "current_user": user,
            "stats": stats,
            "leader_stats": leader_stats
        }
    )