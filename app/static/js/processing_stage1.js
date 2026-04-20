// JavaScript для обработки страницы processing_stage1.html

/**
 * Основной объект для управления обработкой на этапе 1
 */
const ProcessingStage1 = {
    taskId: null,
    groupId: null,
    
    /**
     * Инициализация страницы обработки
     */
    init: function() {
        // Получаем данные из глобального объекта или атрибутов элементов
        this.taskId = parseInt(document.getElementById('processing-stage1').dataset.taskId);
        this.groupId = document.getElementById('processing-stage1').dataset.groupId;
        
        // Получаем список всех group_id из data-атрибута
        this.groupIds = document.getElementById('processing-stage1').dataset.groupIds
            ? document.getElementById('processing-stage1').dataset.groupIds.split(',')
            : [];
            
        // Настраиваем обработчики событий
        this.setupEventListeners();
    },
    
    /**
     * Настраиваем обработчики событий для элементов страницы
     */
    setupEventListeners: function() {
        // Обработчики для кнопок навигации
        document.getElementById('prev-group-btn')?.addEventListener('click', () => this.navigateGroup('prev'));
        document.getElementById('next-group-btn')?.addEventListener('click', () => this.navigateGroup('next'));
        
        // Обработчик для кнопки сохранения и перехода к следующей группе
        document.getElementById('save-and-next-btn')?.addEventListener('click', () => this.saveGroup());
        
        // Обработчик для кнопки завершения этапа
        document.getElementById('complete-stage-btn')?.addEventListener('click', () => this.completeStage());

        // Обработчик для чекбокса "Подтвердить все"
        document.getElementById('confirm-all')?.addEventListener('change', (e) => this.toggleAllImages(e.target.checked));
        
        // Обработчики для чекбоксов изображений
        document.querySelectorAll('input[type="checkbox"][data-image-id]').forEach(checkbox => {
            checkbox.addEventListener('change', () => this.updateConfirmAllCheckbox());
        });
    },
    
    /**
     * Навигация между группами дубликатов
     * @param {string} direction - 'prev' или 'next'
     */
    navigateGroup: function(direction) {
        // Используем предварительно загруженный список groupIds
        const currentIndex = this.groupIds.indexOf(this.groupId);
        
        let newIndex;
        if (direction === 'next') {
            newIndex = Math.min(currentIndex + 1, this.groupIds.length - 1);
        } else if (direction === 'prev') {
            newIndex = Math.max(currentIndex - 1, 0);
        }
        
        // Проверяем, что индекс изменился и находится в допустимом диапазоне
        if (newIndex !== -1 && newIndex !== currentIndex) {
            window.location.href = `/processing/stage1/${this.taskId}?group_id=${this.groupIds[newIndex]}`;
        }
    },
    
    /**
     * Сохранение текущей группы дубликатов
     */
    saveGroup: async function() {
        const selectedImages = [];
        document.querySelectorAll('input[type="checkbox"][data-image-id]:checked').forEach(checkbox => {
            selectedImages.push(parseInt(checkbox.dataset.imageId));
        });

        // Получаем текущий group_id из DOM
        const container = document.getElementById('processing-stage1');
        const currentGroupId = container.dataset.groupId;
        
        if (!currentGroupId) {
            alert('Ошибка: Не удалось получить ID группы');
            return;
        }
        
        // Логируем данные запроса
        console.log('Sending request with:', {
            taskId: this.taskId,
            groupId: currentGroupId,
            image_ids: selectedImages,
            action: 'save'
        });

        try {
            const response = await fetch(`/processing/stage1/${this.taskId}/group/${currentGroupId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image_ids: selectedImages,
                    action: 'save'
                })
            });

            if (response.ok) {
                this.navigateGroup('next');
            } else {
                const data = await response.json();
                alert('Ошибка: ' + data.detail);
            }
        } catch (error) {
            alert('Ошибка сети: ' + error.message);
        }
    },

    /**
     * Завершение первого этапа обработки
     */
    completeStage: function() {
        window.location.href = `/tasks/${this.taskId}`;
    },
    
    /**
     * Включение/отключение всех чекбоксов изображений
     * @param {boolean} checked - состояние чекбокса "Подтвердить все"
     */
    toggleAllImages: function(checked) {
        document.querySelectorAll('input[type="checkbox"][data-image-id]').forEach(checkbox => {
            checkbox.checked = checked;
        });
    },
    
    /**
     * Обновление состояния чекбокса "Подтвердить все" в зависимости от состояния чекбоксов изображений
     */
    updateConfirmAllCheckbox: function() {
        const allCheckboxes = document.querySelectorAll('input[type="checkbox"][data-image-id]');
        const allChecked = Array.from(allCheckboxes).every(checkbox => checkbox.checked);
        document.getElementById('confirm-all').checked = allChecked;
    }
};

// Инициализация объекта при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('processing-stage1')) {
        ProcessingStage1.init();
    }
});