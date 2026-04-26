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

async function saveGlobalSettings() {
    // Находим форму и кнопку по ID и классам
    const form = document.getElementById('taskSettingsForm');
    const submitBtn = document.querySelector('#taskSettingsModal .btn-primary');
    
    if (!submitBtn) {
        console.error('Кнопка сохранения не найдена');
        return;
    }
    
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Сохранение...';
    submitBtn.disabled = true;
    
    try {
        const formData = new FormData(form);
        
        const response = await fetch('/tasks/settings', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(data.message);
            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('taskSettingsModal'));
            if (modal) {
                modal.hide();
            }
        } else {
            alert('Ошибка: ' + (data.detail || 'Неизвестная ошибка'));
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    } finally {
        // Восстанавливаем состояние кнопки
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
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

// Инициализация загрузки настроек по умолчанию при открытии модального окна
$(document).ready(function() {
    $('#taskSettingsModal').on('shown.bs.modal', async function() {
        try {
            const response = await fetch('/tasks/default_settings');
            
            if (response.ok) {
                const settings = await response.json();
                
                // Заполняем поля формы значениями по умолчанию
                $('#featureExtractorStage1').val(settings.feature_extractor_stage1 || 'SIFT');
                $('#matcherStage1').val(settings.matcher_stage1 || 'FLANN');
                $('#qualityAlgorithm').val(settings.quality_algorithm || 'BRISQUE');
                $('#matchThresholdStage1').val(settings.match_threshold_stage1 !== null ? settings.match_threshold_stage1 : 0.75);
                $('#duplicateThresholdStage1').val(settings.duplicate_threshold_stage1 !== null ? settings.duplicate_threshold_stage1 : 0.9);
                
                $('#featureExtractorStage2').val(settings.feature_extractor_stage2 || 'SIFT');
                $('#matcherStage2').val(settings.matcher_stage2 || 'FLANN');
                $('#duplicateThresholdStage2').val(settings.duplicate_threshold_stage2 !== null ? settings.duplicate_threshold_stage2 : 0.8);
                $('#logosPath').val(settings.logos_path || '');
            } else {
                console.error('Failed to load default settings');
            }
        } catch (error) {
            console.error('Error loading default settings:', error);
        }
    });
});

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