document.addEventListener('DOMContentLoaded', function() {
    // Инициализация Chart.js
    if (window.taskData && window.taskData.progressHistory) {
        const ctx = document.getElementById('progressChart').getContext('2d');
        const progressHistory = window.taskData.progressHistory;
        
        // Переменная для хранения экземпляра Chart
        let chart = null;
        
        function updateChart(data) {
            // Проверяем, есть ли данные для графика
            if (data.length > 0) {
                // Отображаем график и скрываем сообщение
                document.getElementById('chartMessage').style.display = 'none';
                
                const labels = data.map(item => {
                    const date = new Date(item.timestamp);
                    return date.toLocaleTimeString();
                });
                
                const chartData = {
                    labels: labels,
                    datasets: [{
                        label: 'Обработано изображений',
                        data: data.map(item => item.processed_images),
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1,
                        fill: false
                    }]
                };
                
                if (chart) {
                    // Обновляем существующий график
                    chart.data = chartData;
                    chart.update();
                } else {
                    // Создаем новый график
                    const config = {
                        type: 'line',
                        data: chartData,
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
                    chart = new Chart(ctx, config);
                }
            } else {
                // Оставляем сообщение о том, что данные будут после начала обработки
                document.getElementById('chartMessage').style.display = 'block';
            }
        }
        
        

        
        // Инициализация графика только если есть данные
        if (window.taskData.progressHistory.length > 0) {
            updateChart(progressHistory);
        } else {
            // Показываем сообщение о том, что данные появятся после начала обработки
            document.getElementById('chartMessage').style.display = 'block';
        }
        
        // Функция для обновления прогресса и графика
        async function refreshProgress() {
            try {
                const response = await fetch(`/images/progress/${window.taskData.taskId}`);
                if (response.ok) {
                    const data = await response.json();
                    
                    // Обновляем отображение прогресса
                    const progressBar = document.querySelector('[aria-valuenow]');
                    if (progressBar) {
                        progressBar.style.width = `${data.progress_percent}%`;
                        progressBar.setAttribute('aria-valuenow', data.progress_percent);
                        progressBar.textContent = `${data.progress_percent}%`;
                    }

                    // Обновляем текстовые значения
                    const progressCards = document.querySelectorAll('.card-title');
                    if (progressCards.length >= 3) {
                        progressCards[1].textContent = data.processed;
                        progressCards[2].textContent = `${data.progress_percent}%`;
                    }
                    // Обновляем статистику дубликатов (если элементы существуют)
                    const duplicateGroups = document.getElementById('duplicateGroups');
                    if (duplicateGroups) {
                        duplicateGroups.textContent = data.clusters_found;
                    }

                    const duplicateImages = document.getElementById('duplicateImages');
                    if (duplicateImages) {
                        duplicateImages.textContent = data.duplicates_found;
                    }

                    // Обновляем уникальные изображения (если элемент существует)
                    const uniqueImages = document.getElementById('uniqueImages');
                    if (uniqueImages) {
                        uniqueImages.textContent = data.total - data.duplicates_found;
                    }
                    
                    // Обновляем график, если есть данные о прогрессе
                    if (data.timestamp && data.processed) {
                        if (!window.taskData.progressHistory) window.taskData.progressHistory = [];
                        window.taskData.progressHistory.push({
                            timestamp: new Date().toISOString(),
                            processed_images: data.processed
                        });
                        
                        // Ограничиваем количество точек для производительности
                        if (window.taskData.progressHistory.length > 100) {
                            window.taskData.progressHistory = window.taskData.progressHistory.slice(-100);
                        }
                        
                        updateChart(window.taskData.progressHistory);
                    }
                    
                    // Продолжаем обновлять, если обработка еще не завершена
                    if (data.progress_percent < 100) {
                        setTimeout(refreshProgress, 2000);
                    }
                }
            } catch (error) {
                console.error('Error refreshing progress:', error);
                // Продолжаем попытки даже при ошибках
                setTimeout(refreshProgress, 2000);
            }
        }
        // Запускаем автообновление прогресса только если window.taskData доступен
        if (window.taskData && window.taskData.taskId) {
            setTimeout(refreshProgress, 2000);
        }

    }
    

});

// Функция для обновления графика
function updateChart(data) {
    // Проверяем, есть ли данные для графика
    if (data.length > 0) {
        // Отображаем график и скрываем сообщение
        const chartMessage = document.getElementById('chartMessage');
        if (chartMessage) {
            chartMessage.style.display = 'none';
        }
        
        const labels = data.map(item => {
            const date = new Date(item.timestamp);
            return date.toLocaleTimeString();
        });
        
        const chartData = {
            labels: labels,
            datasets: [{
                label: 'Обработано изображений',
                data: data.map(item => item.processed_images),
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false
            }]
        };
        
        if (window.chart) {
            // Обновляем существующий график
            window.chart.data = chartData;
            window.chart.update();
        } else {
            // Создаем новый график
            const ctx = document.getElementById('progressChart');
            if (ctx) {
                const config = {
                    type: 'line',
                    data: chartData,
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
                window.chart = new Chart(ctx, config);
            }
        }
    } else {
        // Оставляем сообщение о том, что данные будут после начала обработки
        const chartMessage = document.getElementById('chartMessage');
        if (chartMessage) {
            chartMessage.style.display = 'block';
        }
    }
}

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