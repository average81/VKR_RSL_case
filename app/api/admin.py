from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def check_superuser(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только суперпользователи могут выполнять это действие"
        )
    return current_user


@router.get("/", response_class=HTMLResponse)
def get_admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_superuser)
):
    users = db.query(User).all()
    return templates.TemplateResponse(
        name="admin.html",
        context={
            "users": users,
            "current_user": current_user
        },
        request=request
    )


@router.post("/users/{user_id}/promote")
def promote_user(
    user_id: int,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if role == "group_leader":
        user.is_group_leader = True
    elif role == "admin":
        user.is_superuser = True
    else:
        raise HTTPException(status_code=400, detail="Недопустимая роль")
    
    db.commit()
    db.refresh(user)
    return {"status": "success", "message": f"Пользователь повышен до {role}"}


@router.post("/users/{user_id}/demote")
def demote_user(
    user_id: int,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if role == "group_leader":
        user.is_group_leader = False
    elif role == "admin":
        user.is_superuser = False
    else:
        raise HTTPException(status_code=400, detail="Недопустимая роль")
    
    db.commit()
    return {"status": "success", "message": f"Права {role} сняты"}


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Нельзя удалить самого себя
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    
    db.delete(user)
    db.commit()
    return {"status": "success", "message": "Пользователь удален"}