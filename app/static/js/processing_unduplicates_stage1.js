// JavaScript для обработки страницы processing_unduplicates_stage1.html

/**
 * Основной объект для управления обработкой одиночных изображений
 */
const ProcessingUnduplicatesStage1 = {
    taskId: null,
    imageId: null,
    
    /**
     * Инициализация страницы обработки
     */
    init: function() {
        // Получаем данные из глобального объекта или атрибутов элементов
        this.taskId = parseInt(document.getElementById('processing-unduplicates-stage1').dataset.taskId);
        this.imageId = document.getElementById('processing-unduplicates-stage1').dataset.imageId;
        
        // Получаем список всех image_id из data-атрибута
        this.imageIds = document.getElementById('processing-unduplicates-stage1').dataset.imageIds
            ? document.getElementById('processing-unduplicates-stage1').dataset.imageIds.split(',')
            : [];
            
        // Настраиваем обработчики событий
        this.setupEventListeners();
    },
    
    /**
     * Настраиваем обработчики событий для элементов страницы
     */
    setupEventListeners: function() {
        // Обработчики для кнопок навигации
        document.getElementById('prev-image-btn')?.addEventListener('click', () => this.navigateImage('prev'));
        document.getElementById('next-image-btn')?.addEventListener('click', () => this.navigateImage('next'));
        
        // Обработчик для кнопки сохранения и перехода к следующему изображению
        document.getElementById('save-and-next-btn')?.addEventListener('click', () => this.saveImage());
        
        // Обработчик для кнопки завершения этапа
        document.getElementById('complete-stage-btn')?.addEventListener('click', () => this.completeStage());

        // Обработчик для чекбокса подтверждения изображения
        document.getElementById('confirm-image')?.addEventListener('change', (e) => this.handleImageConfirmChange(e.target));
    },
    
    /**
     * Навигация между одиночными изображениями
     * @param {string} direction - 'prev' или 'next'
     */
    navigateImage: function(direction) {
        // Используем предварительно загруженный список imageIds
        const currentIndex = this.imageIds.indexOf(this.imageId);
        
        let newIndex;
        if (direction === 'next') {
            newIndex = Math.min(currentIndex + 1, this.imageIds.length - 1);
        } else if (direction === 'prev') {
            newIndex = Math.max(currentIndex - 1, 0);
        }
        
        // Проверяем, что индекс изменился и находится в допустимом диапазоне
        if (newIndex !== -1 && newIndex !== currentIndex) {
            window.location.href = `/processing/unduplicates/stage1/${this.taskId}?image_id=${this.imageIds[newIndex]}`;
        }
    },
    
    /**
     * Сохранение текущего изображения
     */
    saveImage: async function() {
        // Получаем текущий image_id из DOM
        const container = document.getElementById('processing-unduplicates-stage1');
        const currentImageId = container.dataset.imageId;
        const isConfirmed = document.getElementById('confirm-image').checked;
        
        if (!currentImageId) {
            alert('Ошибка: Не удалось получить ID изображения');
            return;
        }
        
        // Логируем данные запроса
        console.log('Sending request with:', {
            taskId: this.taskId,
            imageId: currentImageId,
            confirmed: isConfirmed,
            action: 'save'
        });

        try {
            // Отправляем POST запрос для сохранения статуса текущего изображения
            const response = await fetch(`/processing/unduplicates/stage1/${this.taskId}/image/${currentImageId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    confirmed: isConfirmed,
                    action: 'save'
                })
            });

            if (!response.ok) {
                const data = await response.json();
                alert('Ошибка при сохранении изображения: ' + data.detail);
                return;
            }

            // Переходим к следующему изображению
            this.navigateImage('next');
            
        } catch (error) {
            alert('Ошибка сети: ' + error.message);
        }
    },

    /**
     * Завершение первого этапа обработки одиночных изображений
     */
    completeStage: function() {
        window.location.href = `/tasks/${this.taskId}`;
    },
    
    /**
     * Обработчик изменения состояния чекбокса подтверждения изображения
     * @param {HTMLInputElement} checkbox - элемент чекбокса
     */
    handleImageConfirmChange: function(checkbox) {
        console.log(`Изображение ${this.imageId} подтверждено: ${checkbox.checked}`);
    }
};

// Инициализация объекта при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('processing-unduplicates-stage1')) {
        ProcessingUnduplicatesStage1.init();
    }
});