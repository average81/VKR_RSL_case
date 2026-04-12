# Утилиты для работы с сообщениями

def flash_message(request, message: str, category: str = 'info'):
    """
    Добавляет сообщение в сессию для отображения во вьюхе.
    
    Args:
        request: Объект запроса
        message: Текст сообщения
        category: Категория сообщения (info, success, warning, danger)
    """
    if "messages" not in request.session:
        request.session["messages"] = []
    request.session["messages"].append({"text": message, "category": category})

def get_flashed_messages(request):
    """
    Получает и очищает сообщения из сессии.
    
    Args:
        request: Объект запроса
    
    Returns:
        Список сообщений
    """
    messages = request.session.pop("messages", [])
    return messages