from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import os

from pydantic import BaseModel

# Импортируем templates из основного модуля приложения
from app.main import templates
from fastapi import Query

from app.database import get_db
from app.api.auth import get_current_active_user
from app.models import Task, Image, User
from app.models.enums import TaskStatus
from app.services.task_service import TaskService

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание роутера
router = APIRouter(prefix="/processing", tags=["processing"])


def validate_processing_access(task: Task, current_user: User) -> bool:
    """
    Проверяет права доступа к обработке задачи.
    
    Args:
        task: Задача для проверки доступа
        current_user: Текущий пользователь
    
    Returns:
        bool: True если доступ разрешен, False в противном случае
    """
    # Суперпользователь имеет доступ ко всем задачам
    if current_user.is_superuser:
        return True
    
    # Начальник группы имеет доступ к задачам, которые он создал
    if hasattr(current_user, 'is_group_leader') and current_user.is_group_leader:
        return task.validator_id == current_user.id
    
    # Владелец задачи имеет доступ к своей задаче
    return task.owner_id == current_user.id


def get_task_with_review(
    task_id: int,
    db: Session,
    current_user: User
) -> Task:
    """
    Получает задачу с проверкой доступа и валидацией этапа.
    
    Args:
        task_id: ID задачи
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Task: Задача
    
    Raises:
        HTTPException: При ошибках доступа или валидации
    """
    # Получение задачи
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )
    
    # Проверка доступа
    if not validate_processing_access(task, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к задаче"
        )
    
    # Проверка статуса задачи
    if task.status in ["completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Задача не должна быть в статусе или 'completed'"
        )
    
    # Проверка этапа
    if task.stage != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот обработчик предназначен только для этапа 1"
        )
    
    return task


def get_duplicate_groups_for_task(task_id: int, db: Session) -> Dict[str, List[Image]]:
    """
    Получает группы дубликатов для задачи.
    
    Args:
        task_id: ID задачи
        db: Сессия базы данных
    
    Returns:
        Словарь групп дубликатов, где ключи - имена групп (без расширения)
    """
    # Получаем все дубликаты задачи
    duplicate_images = db.query(Image).filter(
        Image.task_id == task_id,
        Image.is_duplicate == True
    ).all()
    
    # Группируем по duplicate_group
    duplicate_groups = {}
    for image in duplicate_images:
        # Базовое имя файла без расширения
        if image.duplicate_group:
            group_name = os.path.splitext(image.duplicate_group)[0]
        else:
            # Если нет duplicate_group, используем имя файла без расширения
            group_name = os.path.splitext(image.filename)[0]
            
        if group_name not in duplicate_groups:
            duplicate_groups[group_name] = []
        duplicate_groups[group_name].append(image)
    
    # Сортируем группы по имени
    return dict(sorted(duplicate_groups.items()))

@router.get("/stage1/{task_id}")
async def get_processing_stage1(
    request: Request,
    task_id: int,
    group_id: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Возвращает страницу для ручного подтверждения групп дубликатов.
    
    Args:
        request: Объект запроса
        task_id: ID задачи
        group_id: ID группы дубликатов (конкретный ID)
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Шаблон страницы processing_duplicates_stage1.html с данными для обработки
    """
    # Получаем задачу с проверкой доступа и валидацией
    task = get_task_with_review(task_id, db, current_user)
    
    # Получаем все группы дубликатов
    duplicate_groups = get_duplicate_groups_for_task(task_id, db)
    
    if not duplicate_groups:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группы дубликатов не найдены для задачи"
        )
    
    # Определяем текущую группу
    group_ids = list(duplicate_groups.keys())
    current_group_idx = 0
    
    # Обработка параметра group_id
    if group_id in duplicate_groups:
        current_group_idx = group_ids.index(group_id)
    
    current_group_id = group_ids[current_group_idx]
    current_group = duplicate_groups[current_group_id]
    
    # Формируем данные для шаблона
    template_data = {
        "task": task,
        "current_user": current_user,
        "current_group": {
            "id": current_group_id,
            "images": current_group,
        },
        "group_ids": group_ids,
        "progress": {
            "current": current_group_idx + 1,
            "total": len(group_ids)
        }
    }
    
    return templates.TemplateResponse(
        request=request,
        name="processing_duplicates_stage1.html",
        context=template_data
    )

# Модель для тела запроса
class SaveGroupRequest(BaseModel):
    image_ids: List[int] = []
    action: str = "save"

class SaveImageRequest(BaseModel):
    confirmed: bool = True
    action: str = "save"


class SavePairRequest(BaseModel):
    action: str = "save_pair"
    current_image_id: int
    next_image_id: Optional[int] = None
    current_image_confirmed: bool = True
    next_image_confirmed: bool = True
    is_duplicate: bool = False
    is_main_duplicate: Optional[bool] = None
    duplicate_group: Optional[str] = None
    next_duplicate_group: Optional[str] = None


def get_unduplicated_images_for_task(task_id: int, db: Session) -> List[Image]:
    """
    Получает список изображений, не находящихся в папке duplicates.
    
    Args:
        task_id: ID задачи
        db: Сессия базы данных
    
    Returns:
        Список изображений, не находящихся в папке duplicates
    """
    # Получаем все изображения задачи
    all_images = db.query(Image).filter(Image.task_id == task_id).all()
    
    # Фильтруем изображения, путь которых не содержит 'duplicates'
    unduplicated_images = [
        img for img in all_images 
        if 'duplicates' not in img.processed_path
    ]
    
    # Сортируем по ID для последовательной навигации
    return sorted(unduplicated_images, key=lambda x: x.id)

@router.get("/unduplicates/stage1/{task_id}")
async def get_processing_unduplicates_stage1(
    request: Request,
    task_id: int,
    image_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Возвращает страницу для ручной проверки изображений, не входящих в группы дубликатов.
    
    Args:
        request: Объект запроса
        task_id: ID задачи
        image_id: ID конкретного изображения для отображения
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Шаблон страницы processing_unduplicates_stage1.html с данными для обработки
    """
    # Получаем задачу с проверкой доступа и валидацией
    task = get_task_with_review(task_id, db, current_user)
    
    # Получаем все изображения, не входящие в группы дубликатов
    unduplicated_images = get_unduplicated_images_for_task(task_id, db)
    
    if not unduplicated_images:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Изображения, не входящие в группы дубликатов, не найдены для задачи"
        )
    
    # Определяем текущее изображение
    image_ids = [img.id for img in unduplicated_images]
    current_image_idx = 0
    
    # Обработка параметра image_id
    if image_id is not None:
        if image_id in image_ids:
            current_image_idx = image_ids.index(image_id)
        else:
            # Если изображение с указанным ID не найдено, берем следующее доступное
            for i, img_id in enumerate(image_ids):
                if img_id > image_id:
                    current_image_idx = i
                    break
    
    current_image = unduplicated_images[current_image_idx]
    
    # Определяем следующее изображение
    next_image = None
    if current_image_idx < len(unduplicated_images) - 1:
        next_image = unduplicated_images[current_image_idx + 1]
    
    # Формируем данные для шаблона
    template_data = {
        "task": task,
        "current_user": current_user,
        "current_image": {
            "id": current_image.id,
            "filename": current_image.filename,
            "processed_path": current_image.processed_path,
        },
        "next_image":{
            "id": next_image.id,
            "filename": next_image.filename,
            "processed_path": next_image.processed_path,
        } if next_image else None,
        "image_ids": image_ids,
        "progress": {
            "current": current_image_idx + 1,
            "total": len(image_ids)
        }
    }
    
    return templates.TemplateResponse(
        request=request,
        name="processing_unduplicates_stage1.html",
        context=template_data
    )

@router.post("/stage1/{task_id}/group/{group_id}")
async def save_group_selection(
    task_id: int,
    group_id: str,
    request: SaveGroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Сохраняет выбор пользователя по группе дубликатов.
    
    Args:
        task_id: ID задачи
        group_id: ID группы дубликатов
        image_ids: Список ID изображений, которые должны остаться в группе
        action: Действие (save)
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Сообщение об успешном сохранении
    """

    # Получаем задачу с проверкой доступа и валидацией
    task = get_task_with_review(task_id, db, current_user)
    
    # Получаем все изображения группы
    group_images = db.query(Image).filter(
        Image.task_id == task_id,
        Image.is_duplicate == True
    ).all()

    # Фильтруем по имени группы (без расширения)
    group_name = str(group_id)
    group_images = [
        img for img in group_images 
        if img.duplicate_group == group_name or img.filename.split('.')[0] == group_name

    ]

    if not group_images:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа дубликатов не найдена"
        )
    
    # Получаем изображения по ID
    selected_images = db.query(Image).filter(
        Image.id.in_(request.image_ids),
        Image.task_id == task_id
    ).all()
    
    # Проверяем, что все переданные ID существуют и относятся к задаче
    selected_ids = [img.id for img in selected_images]
    for img_id in request.image_ids:
        if img_id not in selected_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изображение с ID {img_id} не найдено или не принадлежит задаче"
            )
    
    # Проверяем, что все изображения из группы
    for img in selected_images:
        if img.duplicate_group != group_name and img.filename.split('.')[0] != group_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изображение с ID {img.id} не принадлежит к группе {group_id}"
            )
    
    # Обновляем флаг is_duplicate и validation_status для изображений группы
    for img in group_images:
        img.is_duplicate = img.id in request.image_ids
        img.validation_status = "user_validated"
        img.validated_by = current_user.id

    # Проверяем количество выбранных изображений
    if len(request.image_ids) == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Группа дубликатов не может содержать только одно изображение"
        )
    
    # Определяем изображение с наименьшим ID из оставленных дубликатов
    if request.image_ids:
        main_duplicate_id = min(request.image_ids)
        # Устанавливаем is_main_duplicate только для изображения с наименьшим ID
        for img in group_images:
            img.is_main_duplicate = (img.id == main_duplicate_id)

    db.commit()
    
    logger.info(f"Пользователь {current_user.username} сохранил выбор для группы {group_id} задачи {task_id}")
    
    return {"message": "Выбор успешно сохранен"}

@router.post("/stage1/{task_id}/ungroup/{group_id}")
async def update_ungrouped_status(
    task_id: int,
    group_id: str,
    request: SaveGroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Обновляет статус изображений, исключаемых из указанной группы дубликатов
    Перемещает их из папки группы дубликатов в папку task_id/stage1
    
    Args:
        task_id: ID задачи
        group_id: ID группы дубликатов
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Сообщение об успешном обновлении
    
    Raises:
        HTTPException: При ошибках доступа, валидации или при проблемах с перемещением файлов
    """
    
    # Получаем задачу с проверкой доступа и валидацией
    task = get_task_with_review(task_id, db, current_user)

    # Получаем путь к папке task_id/stage1 (на два уровня выше)
    # Предполагаем, что путь к группе имеет структуру: base_path/group_name
    # и нам нужно подняться на два уровня вверх
    if task.output_path:
        base_output_path = os.path.dirname(os.path.dirname(task.output_path))
        target_path = os.path.join(base_output_path, str(task_id), "stage1")
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не задан путь вывода для задачи"
        )
    
    # Создаем целевую папку, если она не существует
    if not os.path.exists(target_path):
        os.makedirs(target_path)
    
    # Получаем все дубликаты задачи
    duplicate_images = db.query(Image).filter(
        Image.task_id == task_id,
        Image.is_duplicate == True
    ).all()
    
    # Фильтруем изображения, которые принадлежат к указанной группе
    group_images = [
        img for img in duplicate_images 
        if img.duplicate_group == group_id or \
           (img.duplicate_group is None and img.filename.split('.')[0] == group_id)
    ]
    
    if not group_images:
        # Группа не найдена или уже обработана
        return {"message": f"Группа {group_id} не найдена или не содержит дубликатов"}

    # Получаем изображения по ID
    selected_images = db.query(Image).filter(
        Image.id.in_(request.image_ids),
        Image.task_id == task_id
    ).all()

    # Проверяем, что все переданные ID существуют и относятся к задаче
    selected_ids = [img.id for img in selected_images]
    for img_id in request.image_ids:
        if img_id not in selected_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изображение с ID {img_id} не найдено или не принадлежит задаче"
            )

    # Проверяем, что все изображения из группы
    for img in selected_images:
        if img.duplicate_group != group_id and img.filename.split('.')[0] != group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изображение с ID {img.id} не принадлежит к группе {group_id}"
            )
    
    # Обновляем каждое изображение группы
    for img in selected_images:
        # Проверяем, существует ли файл в текущем пути
        old_file_path = os.path.join(img.processed_path, img.filename)
        new_file_path = os.path.join(target_path, img.filename)
        
        if os.path.exists(old_file_path):
            # Перемещаем файл
            try:
                os.rename(old_file_path, new_file_path)
            except Exception as e:
                logger.error(f"Ошибка при перемещении файла {old_file_path}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Ошибка при перемещении файла {img.filename}: {str(e)}"
                )
        
        # Обновляем запись в базе данных
        img.is_duplicate = False
        img.is_main_duplicate = False
        img.processed_path = target_path
        img.duplicate_group = None
        img.validation_status = "updated"
        img.validated_by = current_user.id
    
    db.commit()
    
    logger.info(f"Обновлены изображения вне группы {group_id} для задачи {task_id}")
    
    return {"message": f"Изображения из группы {group_id} успешно перемещены и обновлены"}

@router.post("/unduplicates/stage1/{task_id}/pair")
async def save_unduplicate_pair(
    task_id: int,
    request: SavePairRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Сохраняет результат проверки пары изображений на дубликаты.
    
    Args:
        task_id: ID задачи
        request: Данные с фронтенда с подтверждениями изображений
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Сообщение об успешном сохранении
    """
    # Получаем задачу с проверкой доступа и валидацией
    task = get_task_with_review(task_id, db, current_user)
    
    # Получаем current_image_id из data-атрибута элемента
    # В реальном коде current_image_id должен передаваться в теле запроса или быть доступен другим способом
    # Сейчас извлекаем из данных, которые должны быть доступны в контексте
    
    # Предполагаем, что current_image_id передается в теле запроса или может быть получен из других данных
    current_image_id = request.current_image_id
    
    if not current_image_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан ID текущего изображения"
        )
    
    # Получаем текущее изображение
    current_image = db.query(Image).filter(
        Image.id == current_image_id,
        Image.task_id == task_id
    ).first()
    
    if not current_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Текущее изображение не найдено"
        )
    
    # Обновляем статус текущего изображения
    current_image.validation_status = "user_validated"
    current_image.validated_by = current_user.id
    
    # Обрабатываем флаг дубликата для текущего изображения
    if request.is_duplicate:
        current_image.is_duplicate = True
        current_image.is_main_duplicate = True
        
        # Определяем путь для новой группы дубликатов
        if task.output_path:
            base_output_path = os.path.dirname(os.path.dirname(task.output_path))
            duplicate_group_path = os.path.join(base_output_path, str(task_id), "stage1/duplicates", request.next_duplicate_group)
            
            # Создаем папку для новой группы дубликатов
            if not os.path.exists(duplicate_group_path):
                os.makedirs(duplicate_group_path)
            
            # Переносим файл в новую папку, если изображение не подтверждено
            if not request.current_image_confirmed:
                old_file_path = os.path.join(current_image.processed_path, current_image.filename)
                new_file_path = os.path.join(duplicate_group_path, current_image.filename)
                
                if os.path.exists(old_file_path):
                    try:
                        os.rename(old_file_path, new_file_path)
                    except Exception as e:
                        logger.error(f"Ошибка при перемещении файла {old_file_path}: {str(e)}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Ошибка при перемещении файла {current_image.filename}: {str(e)}"
                        )

                # Обновляем путь обработки текущего изображения
                current_image.processed_path = duplicate_group_path
                current_image.duplicate_group = request.next_duplicate_group
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не задан путь вывода для задачи"
            )
        

    
    # Обновляем следующее изображение, если оно существует
    if request.next_image_id:
        next_image = db.query(Image).filter(
            Image.id == request.next_image_id,
            Image.task_id == task_id
        ).first()

        if next_image:
            if request.is_duplicate:
                next_image.is_duplicate = True
                if request.next_duplicate_group:

                    
                    # Определяем путь для группы дубликатов
                    if task.output_path:
                        base_output_path = os.path.dirname(os.path.dirname(task.output_path))
                        next_duplicate_group_path = os.path.join(base_output_path, str(task_id), "stage1/duplicates", request.next_duplicate_group)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Не задан путь вывода для задачи"
                        )
                    
                    # Переносим файл в новую папку, если изображение не подтверждено
                    if not request.next_image_confirmed:
                        old_file_path = os.path.join(next_image.processed_path, next_image.filename)
                        new_file_path = os.path.join(next_duplicate_group_path, next_image.filename)
                        
                        if os.path.exists(old_file_path):
                            try:
                                os.rename(old_file_path, new_file_path)
                            except Exception as e:
                                logger.error(f"Ошибка при перемещении файла {old_file_path}: {str(e)}")
                                raise HTTPException(
                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail=f"Ошибка при перемещении файла {next_image.filename}: {str(e)}"
                                )
                        
                        # Обновляем путь обработки следующего изображения
                        next_image.processed_path = next_duplicate_group_path

                    # Проверяем следующие изображения на принадлежность к той же группе дубликатов
                    if next_image.duplicate_group:
                        following_images = db.query(Image).filter(
                            Image.task_id == task_id,
                            Image.id > next_image.id,
                            Image.duplicate_group == next_image.duplicate_group
                        ).order_by(Image.id).all()
                        
                        for following_img in following_images:
                            if following_img.is_duplicate:

                                
                                # Перемещаем файл, если он еще не в нужной папке
                                old_file_path = os.path.join(following_img.processed_path, following_img.filename)
                                new_file_path = os.path.join(next_duplicate_group_path, following_img.filename)
                                following_img.processed_path = next_duplicate_group_path
                                following_img.duplicate_group = request.next_duplicate_group
                                if old_file_path != new_file_path and os.path.exists(old_file_path):
                                    try:
                                        os.rename(old_file_path, new_file_path)
                                    except Exception as e:
                                        logger.error(f"Ошибка при перемещении файла {old_file_path}: {str(e)}")
                                        raise HTTPException(
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                            detail=f"Ошибка при перемещении файла {following_img.filename}: {str(e)}"
                                        )
                    next_image.duplicate_group = request.next_duplicate_group
            next_image.validation_status = "user_validated"
            next_image.validated_by = current_user.id
            if next_image.is_main_duplicate:
                # Переносим все изображения группы с именем next_image переносим в новую папку и назначаем им новое имя группы
                next_image.is_main_duplicate = False

    
    db.commit()
    
    logger.info(f"Пользователь {current_user.username} сохранил результат проверки пары изображений для задачи {task_id}")
    
    return {"message": "Пара изображений успешно сохранена"}


@router.get("/stage2/{task_id}")
@router.get("/stage2/{task_id}/issue/{issue_id}")
async def get_processing_stage2(
    request: Request,
    task_id: int,
    issue_id: str = None,
    group_id: str = None,
    is_ajax: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Возвращает страницу для второго этапа обработки задачи - кластеризации по выпускам.
    
    Args:
        request: Объект запроса
        task_id: ID задачи
        group_id: ID группы для сопоставления (если None - первая группа)
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Шаблон страницы processing_stage2.html с данными для обработки
    """
    # Получаем задачу с проверкой доступа
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )
    
    # Проверка доступа
    if not validate_processing_access(task, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к задаче"
        )
    
    # Проверка статуса задачи
    if task.status in ["completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Задача не должна быть в статусе 'completed'"
        )
    
    # Проверка этапа
    if task.stage != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот обработчик предназначен только для этапа 2"
        )
    
    # Получаем все нераспределенные изображения
    unsorted_images = db.query(Image).filter(
        Image.task_id == task_id,
        (Image.issue_name.is_(None)) | 
        (Image.issue_number.is_(None)) |
        (Image.issue_name == 'unsorted')
    ).all()
    
    # Формируем данные для нераспределенных изображений
    unsorted_group_data = {
        "id": "unsorted",
        "images": []
    }
    
    for img in unsorted_images:
        # Определяем путь к изображению
        if img.processed_path and img.filename:
            image_path = os.path.join(img.processed_path, img.filename)
            # Convert to web path by replacing backslashes
            image_path = image_path.replace('\\', '/')
        else:
            image_path = None
            
        unsorted_group_data["images"].append({
            "id": img.id,
            "filename": img.filename,
            "path": image_path
        })
    
    # Получаем все уникальные комбинации названий и номеров выпусков из таблицы images
    issue_combinations = db.query(Image.issue_name, Image.issue_number).filter(
        Image.task_id == task_id,
        Image.issue_name.isnot(None),
        Image.issue_number.isnot(None)
    ).distinct().all()
    
    # Формируем список выпусков
    issues = []
    for issue_name, issue_number in issue_combinations:
        if issue_name:  # Проверяем, что имя не пустое
            # Получаем все изображения для этой комбинации выпуска
            issue_images = db.query(Image).filter(
                Image.task_id == task_id,
                Image.issue_name == issue_name,
                Image.issue_number == issue_number
            ).all()
            
            # Форматируем данные изображений для выпуска
            formatted_images = []
            for img in issue_images:
                if img.processed_path and img.filename:
                    image_path = os.path.join(img.processed_path, img.filename)
                    image_path = image_path.replace('\\', '/')
                else:
                    image_path = None
                    
                formatted_images.append({
                    "id": img.id,
                    "filename": img.filename,
                    "path": image_path
                })
            
            # Создаем имя выпуска с номером
            issue_display_name = f"{issue_name}"
            
            issues.append({
                "id": f"{issue_name}_{issue_number}",
                "name": issue_display_name,
                "number": issue_number,
                "images": formatted_images
            })
    
    # Определяем текущий выпуск (если есть)
    current_issue = None
    target_issue_id = issue_id or group_id  # Приоритет у issue_id, если он передан
    if issues:
        # Используем первый выпуск как текущий
        current_issue = issues[0]
        
        # Если в URL передан issue_id или group_id, пытаемся найти соответствующий выпуск
        if target_issue_id and target_issue_id != 'prev' and target_issue_id != 'next':
            for issue in issues:
                if issue["id"] == target_issue_id:
                    current_issue = issue
                    break
    
    # Формируем данные для шаблона
    template_data = {
        "task": task,
        "current_user": current_user,
        "unsorted_group": unsorted_group_data,
        "issues": issues,
        "current_issue": current_issue
    }
    
    # Проверяем, является ли запрос AJAX-запросом для загрузки контента выпуска
    if issue_id and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Возвращаем только фрагмент содержимого выпуска
        return templates.TemplateResponse(
            request=request,
            name="fragments/issue_content.html",
            context=template_data
        )
    
    # Для обычного запроса возвращаем полную страницу
    return templates.TemplateResponse(
        request=request,
        name="processing_stage2.html",
        context=template_data
    )


# Модель для тела запроса удаления изображения
class RemoveImageRequest(BaseModel):
    image_id: int
    filename: str

@router.post("/stage2/{task_id}/issue/{issue_id}/remove")
async def remove_image_from_issue(
    task_id: int,
    issue_id: str,
    request: RemoveImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Удаляет изображение из выпуска и возвращает его в нераспределенные.
    
    Args:
        task_id: ID задачи
        issue_id: ID выпуска (в формате name_number)
        request: Данные с image_id и filename
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Сообщение об успешном удалении
    """
    # Проверяем существование задачи и доступ
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )
    
    # Проверка доступа
    if not validate_processing_access(task, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к задаче"
        )
    
    # Проверка статуса задачи
    if task.status in ["completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Задача не должна быть в статусе 'completed'"
        )
    
    # Проверка этапа
    if task.stage != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот обработчик предназначен только для этапа 2"
        )
    
    # Извлекаем название и номер выпуска из issue_id
    try:
        issue_name, issue_number_str = issue_id.rsplit('_', 1)
        issue_number = int(issue_number_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат ID выпуска"
        )
    
    # Находим изображение по ID
    image = db.query(Image).filter(
        Image.id == request.image_id,
        Image.task_id == task_id
    ).first()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Изображение не найдено"
        )
    
    # Проверяем, что изображение действительно принадлежит этому выпуску
    if image.issue_name != issue_name or image.issue_number != issue_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Изображение не принадлежит указанному выпуску"
        )
    
    # Формируем путь к папке unsorted
    if task.output_path:
        # Используем выходную папку задачи как основу
        task_output_dir = os.path.dirname(task.output_path)
        unsorted_path = os.path.join(task_output_dir, "stage2", "unsorted")
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не задан путь вывода для задачи"
        )
    
    # Создаем папку unsorted, если она не существует
    if not os.path.exists(unsorted_path):
        os.makedirs(unsorted_path)
        
    # Перемещаем файл изображения в папку unsorted
    old_file_path = os.path.join(image.processed_path, image.filename)
    new_file_path = os.path.join(unsorted_path, image.filename)
    
    if os.path.exists(old_file_path):
        try:
            os.rename(old_file_path, new_file_path)
        except Exception as e:
            logger.error(f"Ошибка при перемещении файла {old_file_path}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при перемещении файла {image.filename}: {str(e)}"
            )
    
    # Обновляем путь обработки изображения
    image.processed_path = unsorted_path
    
    # Обновляем данные изображения
    image.issue_name = "unsorted"
    image.issue_number = 0
    
    # Сохраняем изменения
    db.commit()
    db.refresh(image)
    
    logger.info(f"Пользователь {current_user.username} удалил изображение {request.filename} из выпуска {issue_name}_{issue_number} задачи {task_id}")
    
    return {
        "message": "Изображение успешно удалено из выпуска",
        "new_path": new_file_path
    }

@router.post("/stage1/{task_id}/complete")
async def complete_stage1(
    task_id: int,
    image_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Завершает первый этап обработки.
    
    Args:
        task_id: ID задачи
        image_ids: Список ID изображений, которые были подтверждены как дубликаты
        db: Сессия базы данных
        current_user: Текущий пользователь
    
    Returns:
        Сообщение об успешном завершении этапа
    """
    # Получаем задачу с проверкой доступа и валидацией
    task = get_task_with_review(task_id, db, current_user)
    
    # Получаем все изображения задачи
    images = db.query(Image).filter(Image.task_id == task_id).all()
    
    # Проверяем, что все изображения имеют validation_status == user_validated
    for img in images:
        if img.validation_status != "user_validated":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не все изображения прошли валидацию. Завершите проверку всех групп дубликатов."
            )
    
    # Обновляем статус задачи
    task_service = TaskService(db)
    try:
        # Обновляем этап
        task.stage = 2
        
        # Обновляем статус, если он был 'in_progress', ставим 'completed'
        if task.status == "in_progress":
            task_service.update_task_status(task_id, TaskStatus.COMPLETED, current_user)
        
        # Сохраняем изменения
        db.commit()
        db.refresh(task)
        
        logger.info(f"Пользователь {current_user.username} завершил этап 1 задачи {task_id}")
        
        return {"message": "Этап 1 успешно завершен", "next_stage": 2}
    
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при завершении этапа 1 задачи {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при завершении этапа обработки"
        )