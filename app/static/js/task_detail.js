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
                        data: data.map(item => item.progress),
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1,
                        fill: false
                    }]
                };
                
                if (chart) {
                    // Обновляем только данные, чтобы избежать дерганий
                    chart.data.labels = labels;
                    chart.data.datasets[0].data = data.map(item => item.progress);
                    chart.update('quiet'); // 'quiet' подавляет повторные анимации
                } else {
                    // Создаём новый график
                    const config = {
                        type: 'line',
                        data: chartData,
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            animation: {
                                duration: 300, // плавная анимация при изменении данных
                                easing: 'easeInOutCubic'
                            },
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
                    
                    // Обновляем график, используя данные о прогрессе
                    if (!window.taskData.progressHistory) window.taskData.progressHistory = [];
                    
                    // Получаем последнее значение progress
                    const lastProgress = window.taskData.progressHistory.length > 0 ? window.taskData.progressHistory[window.taskData.progressHistory.length - 1].progress : -1;
                    
                    // Добавляем новую точку только если количество обработанных изображений изменилось
                    if (data.processed !== lastProgress) {
                        window.taskData.progressHistory.push({
                            timestamp: new Date().toISOString(),
                            progress: data.processed
                        });
                        
                        // Ограничиваем количество точек для производительности
                        if (window.taskData.progressHistory.length > 100) {
                            window.taskData.progressHistory = window.taskData.progressHistory.slice(-100);
                        }
                        // Обновляем график с новыми данными
                        updateChart(window.taskData.progressHistory);
                    }
                    

                    
                    // Продолжаем обновлять, если обработка еще не завершена
                    if (data.progress_percent < 100) {
                        setTimeout(refreshProgress, 2000);
                    } else {
                        // При достижении 100% проверяем статус задачи перед обновлением страницы
                        if (window.taskData && window.taskData.status == 'in_progress') {
                            setTimeout(() => {
                                location.reload();
                            }, 1000);
                        }
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

// Открывает модальное окно для выбора папки логотипов для 2 этапа
async function openGroupingModal() {
    const taskId = window.taskData.taskId;
    const modalHtml = `
        <div class="modal fade" id="groupingModal" tabindex="-1" aria-labelledby="groupingModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="groupingModalLabel">Группировка по выпускам</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="logoFolder" class="form-label">Папка с логотипами</label>
                            <input type="text" class="form-control" id="logoFolder" placeholder="Введите путь к папке с логотипами">
                            <button type="button" class="btn btn-outline-secondary mt-2" onclick="selectLogoFolder()">Выбрать папку</button>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                        <button type="button" class="btn btn-primary" onclick="startGrouping(${taskId})">Запустить</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Добавляем модальное окно в DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Инициализируем модальное окно Bootstrap
    const modalElement = document.getElementById('groupingModal');
    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    // Обработчик закрытия модального окна
    modalElement.addEventListener('hidden.bs.modal', function () {
        modalElement.remove();
    });
}

// Функция для выбора папки (заглушка)
function selectLogoFolder() {
    alert('Функция выбора папки временно недоступна. Введите путь вручную.');
}

// Запускает процесс группировки по выпускам
async function startGrouping(taskId) {
    const logoFolderInput = document.getElementById('logoFolder');
    const logoFolderPath = logoFolderInput.value.trim();
    
    if (!logoFolderPath) {
        alert('Пожалуйста, укажите путь к папке с логотипами');
        return;
    }

    // Формируем URL и данные для запроса
    const response = await fetch(`/tasks/${taskId}/start_stage2`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            logo_folder: logoFolderPath
        })
    });

    if (response.ok) {
        alert('Группировка по выпускам начата!');
        // Закрываем модальное окно
        const modalElement = document.getElementById('groupingModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        modal.hide();
        // Обновляем страницу
        location.reload();
    } else {
        const data = await response.json();
        alert('Ошибка: ' + data.detail);
    }
}

async function viewIssues() {
    alert('Функция просмотра выпусков временно недоступна');
}

// Функция завершения задачи с проверкой статусов
async function completeTask(taskId) {
    if (!confirm('Вы уверены, что хотите завершить задачу? Будет проверено, что все изображения прошли валидацию.')) {
        return;
    }

    try {
        const response = await fetch(`/tasks/${taskId}/user_complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_ids: []  // Можно передать подтвержденные изображения, если нужно
            })
        });

        if (response.ok) {
            alert('Задача успешно завершена!');
            location.reload(); // Перезагружаем страницу для обновления статуса
        } else {
            const data = await response.json();
            if (response.status === 400 && data.detail.includes('Не все изображения прошли валидацию')) {
                const confirmOverride = confirm('Не все изображения прошли валидацию. Вы действительно хотите завершить задачу?');
                if (confirmOverride) {
                    // Повторная попытка с подтверждением
                    const overrideResponse = await fetch(`/processing/stage1/${taskId}/user_complete?force=true`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            image_ids: []
                        })
                    });
                    
                    if (overrideResponse.ok) {
                        alert('Задача завершена принудительно!');
                        location.reload();
                    } else {
                        const errorData = await overrideResponse.json();
                        alert(`Ошибка при завершении задачи: ${errorData.detail}`);
                    }
                }
            } else {
                const errorData = await response.json();
                alert(`Ошибка при завершении задачи: ${errorData.detail}`);
            }
        }
    } catch (error) {
        alert(`Ошибка при завершении задачи: ${error.message}`);
    }
}


// Функция для отправки задачи на доработку
async function sendToReprocessing(taskId) {
    if (!confirm('Вы действительно хотите отправить задачу на доработку?')) return;
    
    try {
        const response = await fetch(`/tasks/${taskId}/review`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Задача отправлена на доработку!');
            location.reload();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}