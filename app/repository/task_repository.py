from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.task import Task

class TaskRepository:
    """
    Repository class for handling task database operations.
    
    This repository implements data access operations for tasks,
    abstracting the database interactions from the business logic.
    """

    def __init__(self, db_session: Session):
        """
        Initialize TaskRepository with database session.
        
        Args:
            db_session (Session): SQLAlchemy database session
        """
        self.db_session = db_session

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """
        Retrieve a task by its ID.
        
        Args:
            task_id (int): ID of the task to retrieve
            
        Returns:
            Optional[Task]: Task object if found, None otherwise
        """
        return self.db_session.query(Task).filter(Task.id == task_id).first()

    def create_task(self, task: Task) -> Task:
        """
        Create a new task in the database.
        
        Args:
            task (Task): Task object to create
            
        Returns:
            Task: Created task object with generated ID
        """
        self.db_session.add(task)
        self.db_session.commit()
        self.db_session.refresh(task)
        return task

    def update_task(self, task: Task) -> Task:
        """
        Update an existing task in the database.
        
        Args:
            task (Task): Task object with updated data
            
        Returns:
            Task: Updated task object
        """
        self.db_session.commit()
        self.db_session.refresh(task)
        return task

    def get_tasks_by_status(self, status: str) -> List[Task]:
        """
        Get all tasks with a specific status.
        
        Args:
            status (str): Status to filter by
            
        Returns:
            List[Task]: List of tasks with the specified status
        """
        return self.db_session.query(Task).filter(Task.status == status).all()

    def get_user_accessible_tasks(self, user_id: int, status: str = None) -> List[Task]:
        """
        Get tasks accessible to a specific user.
        
        Args:
            user_id (int): ID of the user
            status (str, optional): Filter by status
            
        Returns:
            List[Task]: List of tasks accessible to the user
        """
        query = self.db_session.query(Task).filter(Task.assigned_to == user_id)
        if status:
            query = query.filter(Task.status == status)
        return query.all()

    def get_tasks_by_user_id(self, user_id: int) -> List[Task]:
        """
        Get all tasks assigned to a specific user.
        
        Args:
            user_id (int): ID of the user
            
        Returns:
            List[Task]: List of tasks assigned to the user
        """
        return self.db_session.query(Task).filter(Task.owner_id == user_id).all()

    def get_tasks_by_validator_id(self, validator_id: int) -> List[Task]:
        """
        Get all tasks created by a specific validator (group leader).
        
        Args:
            validator_id (int): ID of the validator
            
        Returns:
            List[Task]: List of tasks created by the validator
        """
        return self.db_session.query(Task).filter(Task.validator_id == validator_id).all()

    def get_all_tasks(self) -> List[Task]:
        """
        Get all tasks from the database.
        
        Returns:
            List[Task]: List of all tasks
        """
        return self.db_session.query(Task).all()
