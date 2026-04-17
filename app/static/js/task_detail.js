document.addEventListener('DOMContentLoaded', function() {
    // Инициализация Chart.js
    if (window.taskData && window.taskData.progressHistory) {
        const ctx = document.getElementById('progressChart').getContext('2d');
        const progressHistory = window.taskData.progressHistory;
        
        // Проверяем, есть ли данные для графика
        if (progressHistory.length > 0) {
            // Отображаем график и скрываем сообщение
            document.getElementById('chartMessage').style.display = 'none';
            
            const labels = progressHistory.map(item => {
                const date = new Date(item.timestamp);
                return date.toLocaleTimeString();
            });
            
            const data = {
                labels: labels,
                datasets: [{
                    label: 'Обработано изображений',
                    data: progressHistory.map(item => item.processed_images),
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1,
                    fill: false
                }]
            };
            
            const config = {
                type: 'line',
                data: data,
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        }
                    }
                }
            };
            
            new Chart(ctx, config);
        } else {
            // Оставляем сообщение о том, что данные будут после начала обработки
            document.getElementById('chartMessage').style.display = 'block';
        }
    }
});

// Функция для паузы обработки
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

// Функция для возобновления обработки
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

// Функции из оригинального файла
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

async function cancelTask(taskId) {
    if (!confirm('Отменить задачу?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/cancel`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Задача отменена!');
            location.reload();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

async function deleteTask(taskId) {
    if (!confirm('Удалить задачу?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert('Задача удалена!');
            window.location.href = '/tasks';
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

async function viewLogs(taskId) {
    window.open(`/tasks/${taskId}/logs`, '_blank');
}

async function downloadResults(taskId) {
    window.open(`/tasks/${taskId}/download`, '_blank');
}

async function refreshResults() {
    location.reload();
}

async function viewDuplicates() {
    alert('Функция просмотра дубликатов временно недоступна');
}

async function viewIssues() {
    alert('Функция просмотра выпусков временно недоступна');
}