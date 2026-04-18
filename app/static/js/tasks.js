async function startProcessing(taskId) {
    if (!confirm('Начать обработку задачи?')) return;
    
    try {
        const response = await fetch(`/images/${taskId}/process`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Обработка начата!');
            location.reload();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

async function validateTask(taskId) {
    if (!confirm('Подтвердить выполнение задачи?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/validate`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Задача подтверждена!');
            location.reload();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

async function pauseProcessing(taskId) {
    if (!confirm('Приостановить обработку задачи?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/pause`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Обработка приостановлена!');
            location.reload();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

async function resumeProcessing(taskId) {
    if (!confirm('Возобновить обработку задачи?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/resume`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Обработка возобновлена!');
            location.reload();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Функция для обновления прогресса одной задачи
async function updateTaskProgress(taskId) {
    try {
        const response = await fetch(`/images/progress/${taskId}`);
        if (response.ok) {
            const data = await response.json();
            
            // Находим элементы задачи по ID
            const taskCard = document.querySelector(`.task-card[data-task-id='${taskId}']`);
            if (!taskCard) return;
            
            // Обновляем прогресс-бар
            const progressBar = taskCard.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${data.progress_percent}%`;
            }
            
            // Обновляем текст прогресса
            const progressContainer = taskCard.querySelector('.mb-3 .d-flex.justify-content-between');
            if (progressContainer) {
                const progressText = progressContainer.querySelector('small:last-child');
                if (progressText) {
                    progressText.textContent = `${data.processed} / ${data.total}`;
                }
            }
            
            // Если обработка завершена, обновляем статус
            if (data.progress_percent >= 100) {
                const statusBadge = taskCard.querySelector('.badge');
                if (statusBadge) {
                    statusBadge.className = 'badge bg-primary';
                    statusBadge.textContent = 'Завершено';
                }
            }
        }
    } catch (error) {
        console.error(`Error updating progress for task ${taskId}:`, error);
    }
}

// Функция для инициализации автоматического обновления прогресса
function initProgressUpdates() {
    // Находим все карточки задач
    const taskCards = document.querySelectorAll('.task-card');
    
    taskCards.forEach(card => {
        // Получаем ID задачи из атрибута data или из ссылки
        const taskIdMatch = card.querySelector('a')?.href.match(/\/tasks\/(\d+)$/);
        if (!taskIdMatch) return;
        
        const taskId = parseInt(taskIdMatch[1]);
        
        // Добавляем data-атрибут с ID задачи
        card.setAttribute('data-task-id', taskId);
        
        // Проверяем статус задачи
        const statusBadge = card.querySelector('.badge');
        if (!statusBadge) return;
        
        const statusText = statusBadge.textContent.trim();
        
        // Если задача в процессе, запускаем обновление прогресса
        if (statusText === 'В процессе') {
            // Обновляем прогресс сразу
            updateTaskProgress(taskId);
            
            // Затем обновляем каждые 2 секунды
            setInterval(() => {
                updateTaskProgress(taskId);
            }, 2000);
        }
    });
}

// Запускаем инициализацию после загрузки страницы
document.addEventListener('DOMContentLoaded', initProgressUpdates);