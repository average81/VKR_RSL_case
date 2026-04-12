import subprocess
import sys
import logging
import json
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models import Task
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def update_task_status(task_id: int, status: str, db: Session = None):
    """Обновляет статус задачи в базе данных"""
    try:
        if db is None:
            db = SessionLocal()
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status
            task.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(task)
        
        if db is None:  # Если сессия была создана внутри функции
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса задачи {task_id}: {str(e)}")
        if db is None:
            db.close()
        raise

def process_images_task(task_id: int, first_image: str, last_image: str, output_dir: str, settings: dict) -> dict:
    """Запускает обработку изображений через CLI-скрипт как фоновую задачу"""
    result = {
        "success": False,
        "message": "",
        "stats": {},
        "output_files": []
    }
    
    try:
        # Обновляем статус задачи
        update_task_status(task_id, "processing")
        
        # Подготавливаем аргументы для CLI-скрипта
        cmd = [
            sys.executable, "process_images_cli.py",
            first_image,
            "--output_dir", output_dir
        ]
        
        # Добавляем дополнительные параметры из настроек
        if settings.get("verbose", False):
            cmd.append("--verbose")
        if settings.get("metrics", False):
            cmd.append("--metrics")
        
        # Добавляем путь к конфигурации
        config_path = settings.get("config_path", "config.yml")
        cmd.extend(["--config_path", config_path])
        
        logger.info(f"Запуск обработки изображений для задачи {task_id}")
        logger.info(f"Команда: {' '.join(cmd)}")
        
        # Запускаем CLI-скрипт
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="C:/Users/above/IdeaProjects/VKR_RSL_case"
        )
        
        # Читаем вывод в реальном времени
        for line in process.stdout:
            logger.info(f"[process_images] {line.strip()}")
            
        for line in process.stderr:
            logger.error(f"[process_images] {line.strip()}")
        
        # Ждем завершения процесса
        return_code = process.wait()
        
        if return_code == 0:
            result["success"] = True
            result["message"] = "Обработка изображений успешно завершена"
            
            # Собираем информацию о результатах
            result["output_files"].append(f"{output_dir}/metrics.csv")
            result["output_files"].append(f"{output_dir}/duplicates")
            
            # Обновляем статус задачи
            update_task_status(task_id, "completed")
            
        else:
            result["message"] = f"Ошибка при обработке изображений: код возврата {return_code}"
            update_task_status(task_id, "failed")
            
    except Exception as e:
        result["message"] = f"Исключение при обработке изображений: {str(e)}"
        logger.error(f"Ошибка в process_images_task: {str(e)}")
        update_task_status(task_id, "failed")
        
    return result

def group_by_logo_task(task_id: int, input_dir: str, output_dir: str, config_file: str) -> dict:
    """Запускает группировку по логотипам через CLI-скрипт как фоновую задачу"""
    result = {
        "success": False,
        "message": "",
        "stats": {},
        "groups": [],
        "output_files": []
    }
    
    try:
        # Обновляем статус задачи
        update_task_status(task_id, "processing")
        
        # Подготавливаем аргументы для CLI-скрипта
        cmd = [
            sys.executable, "logo_grouping_cli.py",
            input_dir,
            output_dir,
            "logo_grouping"  # Папка с логотипами
        ]
        
        # Добавляем путь к конфигурации
        if config_file:
            cmd.extend(["--config_path", config_file])
        else:
            cmd.extend(["--config_path", "config_logo.yml"])
        
        # Всегда включаем метрики для сбора статистики
        cmd.append("--metrics")
        
        logger.info(f"Запуск группировки по логотипам для задачи {task_id}")
        logger.info(f"Команда: {' '.join(cmd)}")
        
        # Запускаем CLI-скрипт
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="C:/Users/above/IdeaProjects/VKR_RSL_case"
        )
        
        # Читаем вывод в реальном времени
        for line in process.stdout:
            logger.info(f"[logo_grouping] {line.strip()}")
            
        for line in process.stderr:
            logger.error(f"[logo_grouping] {line.strip()}")
        
        # Ждем завершения процесса
        return_code = process.wait()
        
        if return_code == 0:
            result["success"] = True
            result["message"] = "Группировка по логотипам успешно завершена"
            
            # Собираем информацию о результатах
            metrics_file = f"{output_dir}/metrics.csv"
            result["output_files"].append(metrics_file)
            
            # Анализируем метрики для сбора статистики
            try:
                import pandas as pd
                if pd is not None:
                    df = pd.read_csv(metrics_file)
                    
                    # Статистика по группам
                    if 'название логотипа' in df.columns:
                        groups_stats = df['название логотипа'].value_counts().to_dict()
                        result["stats"] = groups_stats
                        
                    # Список созданных групп
                    result["groups"] = list(set(
                        [f.split('_')[0] for f in os.listdir(output_dir) 
                         if os.path.isdir(os.path.join(output_dir, f))]
                    ))
                    
            except Exception as e:
                logger.warning(f"Не удалось проанализировать метрики: {str(e)}")
                
            # Обновляем статус задачи
            update_task_status(task_id, "completed")
            
        else:
            result["message"] = f"Ошибка при группировке по логотипам: код возврата {return_code}"
            update_task_status(task_id, "failed")
            
    except Exception as e:
        result["message"] = f"Исключение при группировке по логотипам: {str(e)}"
        logger.error(f"Ошибка в group_by_logo_task: {str(e)}")
        update_task_status(task_id, "failed")
        
    return result