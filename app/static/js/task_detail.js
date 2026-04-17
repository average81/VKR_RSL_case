// Получаем данные из глобального объекта
const taskId = window.taskData.taskId;

// Функция для получения или создания графика
function getOrCreateChart() {
    const canvas = document.getElementById('progressChart');
    if (!canvas) {
        return null;
    }
    
    // Если график уже существует, возвращаем его
    if (canvas.chart) {
        return canvas.chart;
    }
    
    // Создаем новый график
    const ctx = canvas.getContext('2d');
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Обработано изображений',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
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
    });
    
    // Сохраняем ссылку на график в элементе canvas
    canvas.chart = chart;
    return chart;
}

// Запуск обработки задачи
async function startProcessing(taskId) {
    if (!confirm('Начать обработку задачи?')) return;
    
    try {
        const response = await fetch(`/images/${taskId}/process`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('Обработка начата!');
            location.reload();
        } else {
            const data = await response.json();
            showNotification('Ошибка: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Ошибка сети: ' + error.message, 'danger');
    }
}

// Приостановка обработки задачи
async function pauseProcessing(taskId) {
    if (!confirm('Приостановить обработку задачи?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/pause`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('Обработка приостановлена!');
            location.reload();
        } else {
            const data = await response.json();
            showNotification('Ошибка: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Ошибка сети: ' + error.message, 'danger');
    }
}

// Подтверждение выполнения задачи
async function validateTask(taskId) {
    if (!confirm('Подтвердить выполнение задачи?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/validate`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('Задача подтверждена!');
            location.reload();
        } else {
            const data = await response.json();
            showNotification('Ошибка: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Ошибка сети: ' + error.message, 'danger');
    }
}

// Отмена задачи
async function cancelTask(taskId) {
    if (!confirm('Отменить задачу? Все результаты будут удалены.')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/cancel`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('Задача отменена!');
            window.location.href = '/tasks';
        } else {
            const data = await response.json();
            showNotification('Ошибка: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Ошибка сети: ' + error.message, 'danger');
    }
}

// Удаление задачи
async function deleteTask(taskId) {
    if (!confirm('Удалить задачу? Это действие нельзя отменить.')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Задача удалена!');
            window.location.href = '/tasks';
        } else {
            const data = await response.json();
            showNotification('Ошибка: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Ошибка сети: ' + error.message, 'danger');
    }
}

// Просмотр логов
function viewLogs(taskId) {
    window.open(`/tasks/${taskId}/logs`, '_blank');
}

// Скачивание результатов
function downloadResults(taskId) {
    window.open(`/tasks/${taskId}/download`, '_blank');
}

// Просмотр дубликатов
function viewDuplicates() {
    window.location.href = `/validation/stage1/${taskId}`;
}

// Просмотр выпусков
function viewIssues() {
    window.location.href = `/validation/stage2/${taskId}`;
}

// Обновление результатов
async function refreshResults() {
    try {
        const response = await fetch(`/api/tasks/${taskId}/status`);
        
        if (response.ok) {
            const data = await response.json();
            
            // Обновление статистики
            document.querySelector('.card-title').textContent = data.progress;
            
            if (data.stage === 1) {
                document.querySelectorAll('.text-primary')[0].textContent = data.stats.duplicate_groups || 0;
                document.querySelectorAll('.text-warning')[0].textContent = data.stats.duplicate_images || 0;
                document.querySelectorAll('.text-success')[0].textContent = data.stats.unique_images || 0;
            } else if (data.stage === 2) {
                document.querySelectorAll('.text-primary')[0].textContent = data.stats.issues || 0;
                document.querySelectorAll('.text-info')[0].textContent = data.stats.images_in_issues || 0;
                document.querySelectorAll('.text-danger')[0].textContent = data.stats.unassigned_images || 0;
            }
            
            // Обновление прогресс-бара
            const progress = data.total_images > 0 ? data.progress / data.total_images * 100 : 0;
            const progressBar = document.querySelector('.progress-bar');
            progressBar.style.width = progress + '%';
            progressBar.textContent = Math.round(progress) + '%';
            
            // Обновление графика
            updateChart(data.progress_history);
            
            showNotification('Результаты обновлены!');
        }
    } catch (error) {
        showNotification('Ошибка обновления: ' + error.message, 'danger');
    }
}

// Обновление графика
function updateChart(history) {
    // Получаем или создаем график
    const chart = getOrCreateChart();
    if (!chart) return;
    
    const container = document.getElementById('progressChartContainer');
    
    // Проверяем наличие данных
    if (!history || history.length === 0) {
        // Обновляем данные графика с пустыми значениями
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        chart.update();
        
        // Показываем сообщение о том, что данные появятся после начала обработки
        const messageElement = document.getElementById('chartMessage');
        if (messageElement) {
            messageElement.textContent = 'Данные о динамике обработки появятся после начала обработки изображений';
            messageElement.className = 'text-muted fst-italic small';
        }
        return;
    }
    
    // Ограничиваем историю последними 20 записями для предотвращения бесконечного роста
    const recentHistory = history.slice(-20);
    
    const labels = recentHistory.map(item => new Date(item.timestamp).toLocaleTimeString());
    const data = recentHistory.map(item => item.progress);
    
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.update();
    
    // Скрываем сообщение, если есть данные
    const messageElement = document.getElementById('chartMessage');
    if (messageElement) {
        messageElement.textContent = '';
    }
}



// Показ уведомления
function showNotification(message, type = 'success') {
    // Создаем элемент уведомления
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    alert.style.zIndex = '1000';
    alert.role = 'alert';

    // Создаем содержимое с кнопкой закрытия
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('aria-label', 'Close');

    // Добавляем обработчик закрытия
    closeButton.addEventListener('click', () => {
        alert.remove();
    });

    // Формируем содержимое
    alert.innerHTML = `<div class='d-flex align-items-center'>${message}</div>`;
    alert.appendChild(closeButton);
    
    document.body.appendChild(alert);
    
    // Удаляем через 5 секунд
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем график с начальными данными
    updateChart(window.taskData.progressHistory);
});