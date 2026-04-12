from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
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

# Опциональная зависимость для получения пользователя без ошибки 401
security = HTTPBearer(auto_error=False)

async def get_current_user_optional(
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
            return user
        except JWTError:
            return None
    return None

router = APIRouter(prefix="/auth")

cpwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_superuser(current_user: models.User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return current_user


def check_group_leader(current_user: models.User = Depends(get_current_active_user)):
    if not current_user.is_group_leader:
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return current_user


def check_task_access(current_user: models.User, task: models.Task) -> bool:
    """
    Проверяет права доступа к задаче.
    
    Args:
        current_user: Текущий пользователь
        task: Задача для проверки доступа
    
    Returns:
        True если доступ разрешен, False в противном случае
    """
    # Начальник группы имеет доступ ко всем задачам
    if current_user.is_group_leader:
        return True
    
    # Сотрудник имеет доступ только к своим задачам
    return task.user_id == current_user.id

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

@router.post("/login", response_model=models.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

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

@router.post("/register", response_model=UserSchema)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
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