from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.user import User

class UserRepository:
    """
    Repository class for handling user database operations.
    
    This repository implements data access operations for users,
    abstracting the database interactions from the business logic.
    """

    def __init__(self, db_session: Session):
        """
        Initialize UserRepository with database session.
        
        Args:
            db_session (Session): SQLAlchemy database session
        """
        self.db_session = db_session

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Retrieve a user by its ID.
        
        Args:
            user_id (int): ID of the user to retrieve
            
        Returns:
            Optional[User]: User object if found, None otherwise
        """
        return self.db_session.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Retrieve a user by its username.
        
        Args:
            username (str): Username of the user to retrieve
            
        Returns:
            Optional[User]: User object if found, None otherwise
        """
        return self.db_session.query(User).filter(User.username == username).first()

    def get_all_users(self) -> List[User]:
        """
        Get all users from the database.
        
        Returns:
            List[User]: List of all users
        """
        return self.db_session.query(User).all()
