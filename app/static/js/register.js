// Обработчик отправки формы регистрации
async function registerUser(event) {
    event.preventDefault(); // Предотвращаем стандартную отправку формы
    
    // Собираем данные из формы
    const formData = {
        username: document.getElementById('username').value,
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        is_superuser: document.getElementById('is_superuser').checked
    };
    
    // Валидация обязательных полей
    if (!formData.username || !formData.email || !formData.password) {
        alert('Пожалуйста, заполните все обязательные поля');
        return;
    }
    
    try {
        // Отправляем данные на сервер
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        if (response.ok) {
            // Успешная регистрация
            const data = await response.json();
            // Перенаправляем на страницу входа с сообщением об успехе
            window.location.href = '/auth/login';
        } else {
            // Ошибка при регистрации
            const errorData = await response.json();
            alert(`Ошибка регистрации: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Ошибка при отправке запроса:', error);
        alert('Произошла ошибка при отправке запроса. Пожалуйста, попробуйте снова.');
    }
}

// Добавляем обработчик события при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', registerUser);
    }
});