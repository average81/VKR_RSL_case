from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending" # Ожидает старта
    IN_PROGRESS = "in_progress" # В процессе выполнения
    COMPLETED = "completed" # Завершено
    STOPPED = "stopped" #Прервано
    PAUSED = "paused"   #Поставлено на паузу
    ON_USER_REVIEW = 'on_user_review'   #Ожидает проверки пользователем
    ON_VALIDATION = 'validation_in_process' #На валидации начальником группы

class TaskType(int, Enum):
    DUPLICATES_PROCESSING = 1,
    IMAGES_GROUPING = 2

class Role(str, Enum):
    ADMIN = "admin"
    GROUP_LEADER = "group_leader"
    USER = "user"