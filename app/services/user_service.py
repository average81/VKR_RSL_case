from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from models.user import User, Role
from utils.security import hash_password, verify_password
from repository.user_repository import UserRepository
from exceptions import UserNotFoundException, AuthenticationException, PermissionDeniedException

class UserService:
    """
    Service class for handling user-related business logic.
    
    This service implements user management operations including authentication,
    user creation, role-based access control, and user statistics. It follows the
    repository pattern and uses dependency injection for the database session.
    
    Attributes:
        user_repo (UserRepository): Repository instance for database operations
    """

    def __init__(self, db_session: Session):
        """
        Initialize UserService with database session.
        
        Args:
            db_session (Session): SQLAlchemy database session
        """
        self.user_repo = UserRepository(db_session)

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username and password.
        
        Args:
            username (str): User's username
            password (str): User's password
            
        Returns:
            Optional[User]: Authenticated user object if successful, None otherwise
            
        Raises:
            AuthenticationException: If authentication fails
        """
        try:
            user = self.user_repo.get_user_by_username(username)
            if not user:
                raise AuthenticationException("Invalid username or password")
            
            if not verify_password(password, user.hashed_password):
                raise AuthenticationException("Invalid username or password")
            
            # Update last login time
            user.last_login = datetime.utcnow()
            self.user_repo.update_user(user)
            
            return user
            
        except Exception as e:
            if isinstance(e, AuthenticationException):
                raise
            raise AuthenticationException(f"Authentication failed: {str(e)}")

    def create_user(self, username: str, password: str, role: Role, created_by: User) -> User:
        """
        Create a new user. Only group leaders and admins can create users.
        
        Args:
            username (str): New user's username
            password (str): New user's password
            role (Role): Role to assign to the new user
            created_by (User): User who is creating this new user
            
        Returns:
            User: Created user object
            
        Raises:
            PermissionDeniedException: If the creator doesn't have sufficient privileges
            ValueError: If username already exists
        """
        # Check if creator has sufficient privileges
        if created_by.role not in [Role.ADMIN, Role.GROUP_LEADER]:
            raise PermissionDeniedException("Only admins and group leaders can create users")
        
        # Check if username already exists
        existing_user = self.user_repo.get_user_by_username(username)
        if existing_user:
            raise ValueError(f"Username '{username}' already exists")
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Create user
        user = User(
            username=username,
            hashed_password=hashed_password,
            role=role,
            created_by=created_by.id
        )
        
        return self.user_repo.create_user(user)

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Retrieve a user by their ID.
        
        Args:
            user_id (int): ID of the user to retrieve
            
        Returns:
            Optional[User]: User object if found, None otherwise
        """
        return self.user_repo.get_user_by_id(user_id)

    def update_user_role(self, user_id: int, new_role: Role, updated_by: User) -> User:
        """
        Update a user's role. Only admins can change roles.
        
        Args:
            user_id (int): ID of the user to update
            new_role (Role): New role to assign
            updated_by (User): User who is making the update
            
        Returns:
            User: Updated user object
            
        Raises:
            PermissionDeniedException: If updater is not an admin
            UserNotFoundException: If user to update doesn't exist
        """
        # Only admins can change roles
        if updated_by.role != Role.ADMIN:
            raise PermissionDeniedException("Only admins can change user roles")
        
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException(f"User with id {user_id} not found")
        
        user.role = new_role
        return self.user_repo.update_user(user)

    def get_all_users(self, current_user: User) -> List[User]:
        """
        Get all users. Regular users can only see themselves, 
        group leaders can see their group, admins can see everyone.
        
        Args:
            current_user (User): User requesting the data
            
        Returns:
            List[User]: List of users based on current user's permissions
        """
        if current_user.role == Role.ADMIN:
            return self.user_repo.get_all_users()
        elif current_user.role == Role.GROUP_LEADER:
            return self.user_repo.get_users_by_created_by(current_user.id)
        else:
            # Regular users can only see themselves
            user = self.user_repo.get_user_by_id(current_user.id)
            return [user] if user else []

    def get_user_statistics(self, user_id: int, current_user: User) -> Dict[str, Any]:
        """
        Get statistics for a specific user.
        
        Args:
            user_id (int): ID of the user to get statistics for
            current_user (User): User requesting the statistics
            
        Returns:
            Dict[str, Any]: Dictionary containing user statistics
            
        Raises:
            PermissionDeniedException: If current user doesn't have permission to view these statistics
        """
        # Check permissions
        target_user = self.user_repo.get_user_by_id(user_id)
        if not target_user:
            raise UserNotFoundException(f"User with id {user_id} not found")
        
        if (current_user.role == Role.USER and current_user.id != user_id) or \
           (current_user.role == Role.GROUP_LEADER and target_user.created_by != current_user.id):
            raise PermissionDeniedException("Insufficient permissions to view these statistics")
        
        # Get statistics from task service (this would be injected in a real implementation)
        # For now, we'll return placeholder data
        stats = {
            "user_id": user_id,
            "username": target_user.username,
            "role": target_user.role.value,
            "tasks_completed": 0,
            "tasks_in_progress": 0,
            "average_completion_time": 0,
            "last_active": target_user.last_login,
            "date_joined": target_user.created_at
        }
        
        return stats