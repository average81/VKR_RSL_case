from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"

class TaskType(int, Enum):
    DUPLICATES_PROCESSING = 1,
    IMAGES_GROUPING = 2

class Role(str, Enum):
    ADMIN = "admin"
    GROUP_LEADER = "group_leader"
    USER = "user"