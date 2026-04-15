from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.task import Task, TaskCreate
from app.models.user import User
from app.repository.task_repository import TaskRepository
from app.repository.user_repository import UserRepository
from app.exceptions import TaskNotFoundException, PermissionDeniedException, ValidationException
from app.models.enums import TaskStatus, TaskType, Role
from utils.utils import open_dataset
import os

class TaskService:
    """
    Service class for handling task lifecycle business logic.
    
    This service implements task management operations including creation,
    assignment, status updates, and progress tracking. It follows the
    repository pattern and uses dependency injection for the database session.
    
    Attributes:
        task_repo (TaskRepository): Repository instance for task database operations
        user_repo (UserRepository): Repository instance for user database operations
    """

    def __init__(self, db_session: Session):
        """
        Initialize TaskService with database session.
        
        Args:
            db_session (Session): SQLAlchemy database session
        """
        self.task_repo = TaskRepository(db_session)
        self.user_repo = UserRepository(db_session)

    def create_task(self,
                   created_by: User,
                    task_data: TaskCreate) -> Task:
        """
        Create a new task.
        
        Args:
            created_by (User): User creating the task
            assigned_to (Optional[User]): User to assign the task to
            description (Optional[str]): Task description
            
        Returns:
            Task: Created task object
            
        Raises:
            PermissionDeniedException: If creator doesn't have sufficient privileges
        """
        # Validate permissions - only admins and group leaders can create tasks
        if hasattr(created_by, 'role') and created_by.is_group_leader:
            raise PermissionDeniedException("Only admins and group leaders can create tasks")
        
        # Create task
        task = Task(
            title=task_data.name,
            description=task_data.description,
            input_path=task_data.input_path,
            output_path=task_data.output_path,
            stage=task_data.stage,
            owner_id=task_data.owner_id,
            status="pending",
            validator_id=created_by.id,
            progress = 0,
            total_images = 0,
        )
        
        # Count total images in input directory
        if os.path.exists(task.input_path):
            try:
                images, _ = open_dataset(task.input_path)
                task.total_images = len(images)
            except Exception as e:
                # If there's an error counting images, set to 0
                task.total_images = 0
        
        return self.task_repo.create_task(task)

    def assign_task(self, task_id: int, assigned_to_id: int, assigned_by: User) -> Task:
        """
        Assign a task to a user.
        
        Args:
            task_id (int): ID of the task to assign
            assigned_to_id (int): ID of the user to assign the task to
            assigned_by (User): User assigning the task
            
        Returns:
            Task: Updated task object
            
        Raises:
            TaskNotFoundException: If task doesn't exist
            PermissionDeniedException: If assigner doesn't have sufficient privileges
        """
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task with id {task_id} not found")
        
        # Check permissions
        if (hasattr(assigned_by, 'role') and assigned_by.role not in [Role.ADMIN, Role.GROUP_LEADER]) or \
           (not hasattr(assigned_by, 'role') and not assigned_by.is_superuser):
            # Regular users can only assign tasks they own
            if task.created_by != assigned_by.id:
                raise PermissionDeniedException("Insufficient permissions to assign this task")
        
        # Verify assigned user exists
        assigned_to = self.user_repo.get_user_by_id(assigned_to_id)
        if not assigned_to:
            raise ValidationException(f"User with id {assigned_to_id} not found")
        
        task.assigned_to = assigned_to_id
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = datetime.utcnow()
        
        return self.task_repo.update_task(task)

    def update_task_status(self, task_id: int, new_status: TaskStatus, updated_by: User) -> Task:
        """
        Update a task's status.
        
        Args:
            task_id (int): ID of the task to update
            new_status (TaskStatus): New status for the task
            updated_by (User): User updating the task status
            
        Returns:
            Task: Updated task object
            
        Raises:
            TaskNotFoundException: If task doesn't exist
            PermissionDeniedException: If updater doesn't have sufficient privileges
            ValidationException: If status transition is invalid
        """
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task with id {task_id} not found")
        
        # Check if user is allowed to update this task
        if not self._can_user_modify_task(task, updated_by):
            raise PermissionDeniedException("Insufficient permissions to update this task")
        
        # Validate status transition
        if not self._is_valid_status_transition(task.status, new_status):
            raise ValidationException(f"Invalid status transition from {task.status} to {new_status}")
        
        # Update task
        task.status = new_status
        
        # Set additional timestamps based on status
        if new_status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.utcnow()
        elif new_status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
            
        return self.task_repo.update_task(task)

    def _can_user_modify_task(self, task: Task, user: User) -> bool:
        """
        Check if a user can modify a task.
        
        Args:
            task (Task): Task to check
            user (User): User to check permissions for
            
        Returns:
            bool: True if user can modify the task, False otherwise
        """
        if (hasattr(user, 'role') and user.role == Role.ADMIN) or \
           (not hasattr(user, 'role') and user.is_superuser):
            return True
        
        if (hasattr(user, 'role') and user.role == Role.GROUP_LEADER):
            # Group leaders can modify tasks they created or tasks assigned to their group members
            if task.created_by == user.id:
                return True
            
            if task.assigned_to:
                assigned_user = self.user_repo.get_user_by_id(task.assigned_to)
                if assigned_user and assigned_user.created_by == user.id:
                    return True
            
        elif hasattr(user, 'role') and user.role == Role.USER:  # Regular user
            # Regular users can only modify tasks assigned to them
            return task.assigned_to == user.id

        return False

    def _is_valid_status_transition(self, current_status: TaskStatus, new_status: TaskStatus) -> bool:
        """
        Validate if a status transition is allowed.
        
        Args:
            current_status (TaskStatus): Current task status
            new_status (TaskStatus): New task status
            
        Returns:
            bool: True if transition is valid, False otherwise
        """
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.ASSIGNED, TaskStatus.CANCELLED],
            TaskStatus.ASSIGNED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.ON_HOLD, TaskStatus.CANCELLED],
            TaskStatus.ON_HOLD: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.COMPLETED: [],
            TaskStatus.CANCELLED: []
        }
        
        return new_status in valid_transitions.get(current_status, [])

    def get_task_by_id(self, task_id: int, user: User) -> Optional[Task]:
        """
        Retrieve a task by its ID.
        
        Args:
            task_id (int): ID of the task to retrieve
            user (User): User requesting the task
            
        Returns:
            Optional[Task]: Task object if found and user has permission, None otherwise
        """
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            return None
        
        # Check permissions
        if not self._can_user_modify_task(task, user):
            return None
            
        return task

    def get_tasks_by_status(self, status: TaskStatus, user: User) -> List[Task]:
        """
        Get tasks by status.
        
        Args:
            status (TaskStatus): Status to filter by
            user (User): User requesting the tasks
            
        Returns:
            List[Task]: List of tasks with the specified status that the user has permission to view
        """
        if hasattr(user, 'role') and user.role == Role.ADMIN:
            return self.task_repo.get_tasks_by_status(status)
        
        # For non-admin users, get tasks they can access
        return self.task_repo.get_user_accessible_tasks(user.id, status)

    def get_user_tasks(self, user_id: int, user: User, status: str = None, stage: int = None, search_query: str = None) -> List[Task]:
        """
        Get tasks for a specific user with optional filtering.
        
        Args:
            user_id (int): ID of the user whose tasks to retrieve
            user (User): User requesting the tasks
            status (str, optional): Filter by task status
            stage (int, optional): Filter by processing stage
            search_query (str, optional): Filter by search query in title or description
            
        Returns:
            List[Task]: List of tasks for the specified user that match the filters and the requesting user has permission to view
        """
        target_user = self.user_repo.get_user_by_id(user_id)
        if not target_user:
            return []
        
        # Check permissions
        if hasattr(user, 'role') and user.role == Role.ADMIN:
            tasks = self.task_repo.get_tasks_by_user_id(user_id)
        elif hasattr(user, 'role') and user.role == Role.GROUP_LEADER:
            # Group leaders can see tasks for their group members
            if target_user.created_by == user.id:
                tasks = self.task_repo.get_tasks_by_user_id(user_id)
            else:
                return []
        else:
            # Regular users can only see their own tasks
            if user.id == user_id:
                tasks = self.task_repo.get_tasks_by_user_id(user_id)
            else:
                return []
        
        # Apply filters
        if status and status in ['pending', 'in_progress', 'completed', 'validated']:
            tasks = [task for task in tasks if task.status == status]

        stage_value = int(stage) if isinstance(stage, str) else stage
        tasks = [task for task in tasks if task.stage == stage_value]
        
        if search_query and len(search_query.strip()) > 0:
            search_query_lower = search_query.lower()
            tasks = [task for task in tasks if 
                   search_query_lower in task.title.lower() or
                   search_query_lower in task.description.lower() if task.description]
        return tasks

    def get_task_metrics(self, user: User) -> Dict[str, Any]:
        """
        Get task metrics and progress tracking data.
        
        Args:
            user (User): User requesting the metrics
            
        Returns:
            Dict[str, Any]: Dictionary containing task metrics
        """
        metrics = {
            "total_tasks": 0,
            "pending_tasks": 0,
            "assigned_tasks": 0,
            "in_progress_tasks": 0,
            "completed_tasks": 0,
            "on_hold_tasks": 0,
            "cancelled_tasks": 0,
            "completion_rate": 0.0,
            "average_completion_time": 0,
            "tasks_by_type": {}
        }
        
        # Get all tasks the user has permission to view
        all_tasks = self.task_repo.get_user_accessible_tasks(user.id) if user.role != Role.ADMIN else self.task_repo.get_all_tasks()
        
        metrics["total_tasks"] = len(all_tasks)
        
        completed_count = 0
        total_completion_time = timedelta()
        
        for task in all_tasks:
            if task.status == TaskStatus.PENDING:
                metrics["pending_tasks"] += 1
            elif task.status == TaskStatus.ASSIGNED:
                metrics["assigned_tasks"] += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                metrics["in_progress_tasks"] += 1
            elif task.status == TaskStatus.COMPLETED:
                metrics["completed_tasks"] += 1
                completed_count += 1
                if task.started_at and task.completed_at:
                    total_completion_time += task.completed_at - task.started_at
            elif task.status == TaskStatus.ON_HOLD:
                metrics["on_hold_tasks"] += 1
            elif task.status == TaskStatus.CANCELLED:
                metrics["cancelled_tasks"] += 1
            
            # Count tasks by type
            task_type = task.task_type.value
            metrics["tasks_by_type"][task_type] = metrics["tasks_by_type"].get(task_type, 0) + 1
        
        # Calculate completion rate
        if metrics["total_tasks"] > 0:
            metrics["completion_rate"] = (completed_count / metrics["total_tasks"]) * 100
        
        # Calculate average completion time in hours
        if completed_count > 0:
            avg_time = total_completion_time / completed_count
            metrics["average_completion_time"] = avg_time.total_seconds() / 3600  # Convert to hours
        
        return metrics

    def start_two_stage_processing(self, created_by: User) -> Task:
        """
        Start the two-stage processing workflow (duplicate detection, issue clustering).
        
        Args:
            created_by (User): User starting the processing
            
        Returns:
            Task: The created processing task
            
        Raises:
            PermissionDeniedException: If user doesn't have sufficient privileges
        """
        # Only admins and group leaders can start processing
        if (hasattr(created_by, 'role') and created_by.role not in [Role.ADMIN, Role.GROUP_LEADER]) or \
           (not hasattr(created_by, 'role') and not created_by.is_superuser):
            raise PermissionDeniedException("Only admins and group leaders can start processing")
        
        return self.create_task(
            task_type=TaskType.TWO_STAGE_PROCESSING,
            created_by=created_by,
            description="Two-stage processing: duplicate detection followed by issue clustering"
        )

    def validate_task_completion(self, task_id: int, validator: User) -> bool:
        """
        Validate that a task has been properly completed.
        
        Args:
            task_id (int): ID of the task to validate
            validator (User): User validating the task completion
            
        Returns:
            bool: True if validation passes, False otherwise
            
        Raises:
            TaskNotFoundException: If task doesn't exist
            PermissionDeniedException: If validator doesn't have sufficient privileges
        """
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task with id {task_id} not found")
        
        # Only admins and group leaders can validate task completion
        if (hasattr(validator, 'role') and validator.role not in [Role.ADMIN, Role.GROUP_LEADER]) or \
           (not hasattr(validator, 'role') and not validator.is_superuser):
            raise PermissionDeniedException("Only admins and group leaders can validate task completion")
        
        # For two-stage processing tasks, validate that both stages completed successfully
        if task.task_type == TaskType.TWO_STAGE_PROCESSING:
            # This would integrate with the processing scripts
            # For now, we'll assume validation passes if the task is completed
            return task.status == TaskStatus.COMPLETED
        
        # For other task types, basic validation
        return task.status == TaskStatus.COMPLETED
