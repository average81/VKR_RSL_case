from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import shutil
from sqlalchemy.orm import Session
from models.image import Image, ImageStatus, DefectType
from models.user import User, Role
from repository.image_repository import ImageRepository
from exceptions import ImageNotFoundException, ValidationException, PermissionDeniedException
from utils.image_validator import ImageValidator

class ImageService:
    """
    Service class for handling image processing business logic.
    
    This service implements image management operations including validation,
    duplicate group management, quality assessment, and defect detection.
    It follows the repository pattern and uses dependency injection for the database session.
    
    Attributes:
        image_repo (ImageRepository): Repository instance for image database operations
        validator (ImageValidator): Utility for validating image properties
    """

    def __init__(self, db_session: Session):
        """
        Initialize ImageService with database session.
        
        Args:
            db_session (Session): SQLAlchemy database session
        """
        self.image_repo = ImageRepository(db_session)
        self.validator = ImageValidator()

    def validate_image(self, image_path: str, uploaded_by: User) -> Tuple[bool, List[str]]:
        """
        Validate an image according to business rules.
        
        Args:
            image_path (str): Path to the image file
            uploaded_by (User): User who uploaded the image
            
        Returns:
            Tuple[bool, List[str]]: Tuple of (is_valid, list_of_errors)
        """
        return self.validator.validate_image(image_path)

    def create_image_record(self, 
                           filename: str, 
                           path: str, 
                           uploaded_by: User, 
                           status: ImageStatus = ImageStatus.UPLOADED) -> Image:
        """
        Create a new image record in the database.
        
        Args:
            filename (str): Name of the image file
            path (str): Path to the image file
            uploaded_by (User): User who uploaded the image
            status (ImageStatus): Initial status of the image
            
        Returns:
            Image: Created image object
            
        Raises:
            ValidationException: If validation fails
        """
        # Validate input
        if not filename or not path:
            raise ValidationException("Filename and path are required")
        
        # Create image record
        image = Image(
            filename=filename,
            path=path,
            status=status,
            uploaded_by=uploaded_by.id,
            uploaded_at=datetime.utcnow()
        )
        
        return self.image_repo.create_image(image)

    def get_image_by_id(self, image_id: int, user: User) -> Optional[Image]:
        """
        Retrieve an image by its ID.
        
        Args:
            image_id (int): ID of the image to retrieve
            user (User): User requesting the image
            
        Returns:
            Optional[Image]: Image object if found and user has permission, None otherwise
        """
        image = self.image_repo.get_image_by_id(image_id)
        if not image:
            return None
        
        # Check permissions - users can only access images they uploaded or that are in completed tasks
        if user.role == Role.ADMIN:
            return image
        
        if image.uploaded_by == user.id:
            return image
        
        # For non-admin users, check if the image is part of a completed task they can access
        task = self.image_repo.get_task_for_image(image_id)
        if task and task.status == TaskStatus.COMPLETED:
            task_service = TaskService(self.image_repo.db_session)
            return image if task_service._can_user_modify_task(task, user) else None
        
        return None

    def update_image_status(self, image_id: int, new_status: ImageStatus, updated_by: User) -> Image:
        """
        Update an image's status.
        
        Args:
            image_id (int): ID of the image to update
            new_status (ImageStatus): New status for the image
            updated_by (User): User updating the image status
            
        Returns:
            Image: Updated image object
            
        Raises:
            ImageNotFoundException: If image doesn't exist
            PermissionDeniedException: If updater doesn't have sufficient privileges
            ValidationException: If status transition is invalid
        """
        image = self.image_repo.get_image_by_id(image_id)
        if not image:
            raise ImageNotFoundException(f"Image with id {image_id} not found")
        
        # Check permissions
        if not self._can_user_modify_image(image, updated_by):
            raise PermissionDeniedException("Insufficient permissions to update this image")
        
        # Validate status transition
        if not self._is_valid_status_transition(image.status, new_status):
            raise ValidationException(f"Invalid status transition from {image.status} to {new_status}")
        
        image.status = new_status
        
        # Set processing timestamps
        if new_status == ImageStatus.PROCESSING:
            image.processed_at = datetime.utcnow()
        elif new_status == ImageStatus.COMPLETED:
            image.completed_at = datetime.utcnow()
        
        return self.image_repo.update_image(image)

    def _can_user_modify_image(self, image: Image, user: User) -> bool:
        """
        Check if a user can modify an image.
        
        Args:
            image (Image): Image to check
            user (User): User to check permissions for
            
        Returns:
            bool: True if user can modify the image, False otherwise
        """
        if user.role == Role.ADMIN:
            return True
        
        # Users can modify images they uploaded
        if image.uploaded_by == user.id:
            return True
        
        # Group leaders can modify images uploaded by their group members
        if user.role == Role.GROUP_LEADER:
            uploaded_by = self.image_repo.get_user_by_id(image.uploaded_by)
            if uploaded_by and uploaded_by.created_by == user.id:
                return True
        
        return False

    def _is_valid_status_transition(self, current_status: ImageStatus, new_status: ImageStatus) -> bool:
        """
        Validate if a status transition is allowed.
        
        Args:
            current_status (ImageStatus): Current image status
            new_status (ImageStatus): New image status
            
        Returns:
            bool: True if transition is valid, False otherwise
        """
        valid_transitions = {
            ImageStatus.UPLOADED: [ImageStatus.VALIDATING, ImageStatus.INVALID],
            ImageStatus.VALIDATING: [ImageStatus.VALID, ImageStatus.INVALID, ImageStatus.DUPLICATE],
            ImageStatus.VALID: [ImageStatus.PROCESSING, ImageStatus.DUPLICATE],
            ImageStatus.INVALID: [ImageStatus.RESTORED],
            ImageStatus.DUPLICATE: [ImageStatus.PROCESSING],
            ImageStatus.PROCESSING: [ImageStatus.COMPLETED, ImageStatus.FAILED],
            ImageStatus.COMPLETED: [],
            ImageStatus.FAILED: [ImageStatus.PROCESSING, ImageStatus.RESTORED],
            ImageStatus.RESTORED: [ImageStatus.VALIDATING]
        }
        
        return new_status in valid_transitions.get(current_status, [])

    def create_duplicate_group(self, image_ids: List[int], created_by: User) -> List[Image]:
        """
        Create a duplicate group from a list of image IDs.
        
        Args:
            image_ids (List[int]): List of image IDs to group as duplicates
            created_by (User): User creating the duplicate group
            
        Returns:
            List[Image]: List of updated image objects
            
        Raises:
            PermissionDeniedException: If creator doesn't have sufficient privileges
            ValidationException: If validation fails
        """
        # Only admins and group leaders can create duplicate groups
        if created_by.role not in [Role.ADMIN, Role.GROUP_LEADER]:
            raise PermissionDeniedException("Only admins and group leaders can create duplicate groups")
        
        if len(image_ids) < 2:
            raise ValidationException("At least two images are required to create a duplicate group")
        
        updated_images = []
        for image_id in image_ids:
            image = self.image_repo.get_image_by_id(image_id)
            if not image:
                raise ValidationException(f"Image with id {image_id} not found")
            
            # Check permissions
            if not self._can_user_modify_image(image, created_by):
                raise PermissionDeniedException(f"Insufficient permissions to modify image {image_id}")
            
            # Update status
            image.status = ImageStatus.DUPLICATE
            image.duplicate_group_id = min(image_ids)  # Use smallest ID as group ID
            updated_images.append(self.image_repo.update_image(image))
        
        return updated_images

    def assess_image_quality(self, image_id: int, quality_score: int, assessed_by: User) -> Image:
        """
        Assess the quality of an image.
        
        Args:
            image_id (int): ID of the image to assess
            quality_score (int): Quality score (1-10)
            assessed_by (User): User assessing the image quality
            
        Returns:
            Image: Updated image object
            
        Raises:
            ImageNotFoundException: If image doesn't exist
            PermissionDeniedException: If assessor doesn't have sufficient privileges
            ValidationException: If quality score is invalid
        """
        if quality_score < 1 or quality_score > 10:
            raise ValidationException("Quality score must be between 1 and 10")
        
        image = self.image_repo.get_image_by_id(image_id)
        if not image:
            raise ImageNotFoundException(f"Image with id {image_id} not found")
        
        # Check permissions
        if not self._can_user_modify_image(image, assessed_by):
            raise PermissionDeniedException("Insufficient permissions to assess this image")
        
        image.quality_score = quality_score
        image.quality_assessed_by = assessed_by.id
        image.quality_assessed_at = datetime.utcnow()
        
        return self.image_repo.update_image(image)

    def move_image(self, image_id: int, destination_path: str, moved_by: User) -> Image:
        """
        Move an image file to a new location and update the database record.
        
        Args:
            image_id (int): ID of the image to move
            destination_path (str): New path for the image file
            moved_by (User): User moving the image
            
        Returns:
            Image: Updated image object
            
        Raises:
            ImageNotFoundException: If image doesn't exist
            PermissionDeniedException: If mover doesn't have sufficient privileges
            ValidationException: If move operation fails
        """
        image = self.image_repo.get_image_by_id(image_id)
        if not image:
            raise ImageNotFoundException(f"Image with id {image_id} not found")
        
        # Check permissions
        if not self._can_user_modify_image(image, moved_by):
            raise PermissionDeniedException("Insufficient permissions to move this image")
        
        try:
            # Create destination directory if it doesn't exist
            dest_dir = Path(destination_path).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Move the file
            shutil.move(image.path, destination_path)
            
            # Update database record
            old_path = image.path
            image.path = destination_path
            
            updated_image = self.image_repo.update_image(image)
            
            # Log the move operation
            self.image_repo.create_image_log(
                image_id=image_id,
                action="MOVE",
                details=f"Moved from {old_path} to {destination_path}",
                performed_by=moved_by.id
            )
            
            return updated_image
            
        except Exception as e:
            raise ValidationException(f"Failed to move image: {str(e)}")

    def detect_defects(self, image_id: int, defects: List[DefectType], detected_by: User) -> Image:
        """
        Detect defects in an image.
        
        Args:
            image_id (int): ID of the image to analyze
            defects (List[DefectType]): List of detected defects
            detected_by (User): User detecting the defects
            
        Returns:
            Image: Updated image object
            
        Raises:
            ImageNotFoundException: If image doesn't exist
            PermissionDeniedException: If detector doesn't have sufficient privileges
        """
        image = self.image_repo.get_image_by_id(image_id)
        if not image:
            raise ImageNotFoundException(f"Image with id {image_id} not found")
        
        # Check permissions
        if not self._can_user_modify_image(image, detected_by):
            raise PermissionDeniedException("Insufficient permissions to detect defects in this image")
        
        image.defects = defects
        image.defect_detected_by = detected_by.id
        image.defect_detected_at = datetime.utcnow()
        
        return self.image_repo.update_image(image)

    def restore_image(self, image_id: int, restored_by: User) -> Image:
        """
        Restore an invalid image to allow reprocessing.
        
        Args:
            image_id (int): ID of the image to restore
            restored_by (User): User restoring the image
            
        Returns:
            Image: Updated image object
            
        Raises:
            ImageNotFoundException: If image doesn't exist
            PermissionDeniedException: If restorer doesn't have sufficient privileges
        """
        image = self.image_repo.get_image_by_id(image_id)
        if not image:
            raise ImageNotFoundException(f"Image with id {image_id} not found")
        
        # Check permissions - only admins and group leaders can restore images
        if restored_by.role not in [Role.ADMIN, Role.GROUP_LEADER]:
            raise PermissionDeniedException("Only admins and group leaders can restore images")
        
        image.status = ImageStatus.RESTORED
        image.restored_by = restored_by.id
        image.restored_at = datetime.utcnow()
        
        return self.image_repo.update_image(image)

    def get_image_statistics(self, user: User) -> Dict[str, Any]:
        """
        Get image processing statistics.
        
        Args:
            user (User): User requesting the statistics
            
        Returns:
            Dict[str, Any]: Dictionary containing image statistics
        """
        stats = {
            "total_images": 0,
            "by_status": {},
            "by_quality": {},
            "defect_distribution": {},
            "processing_times": {},
            "duplicate_groups": 0
        }
        
        # Get all images the user has permission to view
        images = []
        if user.role == Role.ADMIN:
            images = self.image_repo.get_all_images()
        elif user.role == Role.GROUP_LEADER:
            # Group leaders can see images uploaded by their group members
            group_member_ids = [user.id] + [u.id for u in self.image_repo.get_users_by_created_by(user.id)]
            images = self.image_repo.get_images_by_uploaded_by(group_member_ids)
        else:
            # Regular users can only see their own images
            images = self.image_repo.get_images_by_uploaded_by([user.id])
        
        stats["total_images"] = len(images)
        
        # Count by status
        for image in images:
            status = image.status.value
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        # Count by quality score
        for image in images:
            if image.quality_score:
                score_range = f"{((image.quality_score - 1) // 3) * 3 + 1}-{((image.quality_score - 1) // 3) * 3 + 3}"
                stats["by_quality"][score_range] = stats["by_quality"].get(score_range, 0) + 1
        
        # Defect distribution
        for image in images:
            if image.defects:
                for defect in image.defects:
                    defect_name = defect.value
                    stats["defect_distribution"][defect_name] = stats["defect_distribution"].get(defect_name, 0) + 1
        
        # Count duplicate groups (unique group IDs)
        duplicate_group_ids = set()
        for image in images:
            if image.duplicate_group_id:
                duplicate_group_ids.add(image.duplicate_group_id)
        stats["duplicate_groups"] = len(duplicate_group_ids)
        
        return stats