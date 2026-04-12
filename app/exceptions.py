class TaskNotFoundException(Exception):
    """
    Исключение, возникающее при попытке доступа к несуществующей задаче.
    """
    pass

class PermissionDeniedException(Exception):
    """
    Исключение, возникающее при отсутствии прав доступа к операции.
    """
    pass

class ValidationException(Exception):
    """
    Исключение, возникающее при валидации данных.
    """
    pass