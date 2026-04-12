from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    TWO_STAGE_PROCESSING = "two_stage_processing"

class Role(str, Enum):
    ADMIN = "admin"
    GROUP_LEADER = "group_leader"
    USER = "user"