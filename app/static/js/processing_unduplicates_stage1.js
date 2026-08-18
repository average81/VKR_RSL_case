// JavaScript для обработки страницы processing_unduplicates_stage1.html

/**
 * Основной объект для управления обработкой пар изображений
 */
const ProcessingUnduplicatesStage1 = {
    taskId: null,
    currentImageId: null,
    nextImageId: null,
    pairCount: 0,
    currentPairIndex: 0,
    sortBy: "order",
    
    /**
     * Инициализация страницы обработки
     */
    init: function() {
        // Получаем данные из глобального объекта или атрибутов элементов
        this.taskId = parseInt(document.getElementById('processing-unduplicates-stage1').dataset.taskId);
        this.currentImageId = document.getElementById('processing-unduplicates-stage1').dataset.currentImageId;
        this.nextImageId = document.getElementById('processing-unduplicates-stage1').dataset.nextImageId;
        this.pairCount = parseInt(document.getElementById('processing-unduplicates-stage1').dataset.pairCount) || 0;
        this.currentPairIndex = parseInt(document.getElementById('processing-unduplicates-stage1').dataset.currentPairIndex) || 0;
        this.sortBy = document.getElementById('processing-unduplicates-stage1').dataset.sortBy || "order";
        
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
        document.getElementById('save-and-next-btn')?.addEventListener('click', () => this.savePair());
        
        // Обработчик для кнопки завершения этапа
        document.getElementById('complete-stage-btn')?.addEventListener('click', () => this.completeStage());

        // Обработчики для чекбоксов подтверждения изображений
        document.getElementById('confirm-current-image')?.addEventListener('change', (e) => this.handleImageConfirmChange('current', e.target));
        document.getElementById('confirm-next-image')?.addEventListener('change', (e) => this.handleImageConfirmChange('next', e.target));
    },
    
    /**
     * Навигация между парами изображений
     * @param {string} direction - 'prev' или 'next'
     */
    navigateImage: function(direction) {
        // Используем пары (индексы пар)
        let newIndex;
        if (direction === 'next') {
            newIndex = Math.min(this.currentPairIndex + 1, this.pairCount - 1);
        } else if (direction === 'prev') {
            newIndex = Math.max(this.currentPairIndex - 1, 0);
        }
        
        // Проверяем, что индекс изменился и находится в допустимом диапазоне
        if (newIndex !== -1 && newIndex !== this.currentPairIndex) {
            window.location.href = `/processing/unduplicates/stage1/${this.taskId}?pair_index=${newIndex}&sort_by=${this.sortBy}`;
        }
    },
    
    /**
     * Обработка пары изображений
     */
    savePair: async function() {
        const container = document.getElementById('processing-unduplicates-stage1');
        const isCurrentConfirmed = document.getElementById('confirm-current-image')?.checked ?? true;
        const isNextConfirmed = document.getElementById('confirm-next-image')?.checked ?? true;
        
        if (!this.currentImageId) {
            alert('Ошибка: Не удалось получить ID текущего изображения');
            return;
        }
        
        // Определяем, является ли пара дубликатами
        const isDuplicate = !(isCurrentConfirmed && isNextConfirmed);

        // Формируем данные для отправки
        const data = {
            action: 'save_pair',
            current_image_id: this.currentImageId,
            next_image_id: this.nextImageId || null,
            current_image_confirmed: isCurrentConfirmed,
            next_image_confirmed: isNextConfirmed
        };

        // Если изображения не являются дубликатами, устанавливаем флаг
        if (!isDuplicate) {
            data.is_duplicate = false;
        } else {
            // Если это дубликаты, устанавливаем соответствующие флаги
            data.is_duplicate = true;

            // Используем data-атрибут для получения базового имени файла
            const currentImageElement = document.querySelector(`img[data-image-id="${this.currentImageId}"]`);
            const currentImageFilename = currentImageElement?.dataset.filenameBase;
            data.next_duplicate_group = `${currentImageFilename}`;
            // Для следующего изображения устанавливаем duplicate_group если оно не подтверждено
            if (!isNextConfirmed && this.nextImageId) {
                // Используем ту же группу, что и для текущего изображения
                const currentImageElement = document.querySelector(`img[data-image-id="${this.currentImageId}"]`);
                const currentImageFilename = currentImageElement?.dataset.filenameBase;

            }
        }

        try {
            // Отправляем POST запрос для сохранения статуса пары изображений
            const response = await fetch(`/processing/unduplicates/stage1/${this.taskId}/pair`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const result = await response.json();
                alert('Ошибка при сохранении пары изображений: ' + result.detail);
                return;
            }

            // Переходим к следующей паре изображений
            this.navigateImage('next');
            
        } catch (error) {
            alert('Ошибка сети: ' + error.message);
        }
    },

    /**
     * Завершение первого этапа обработки пар изображений
     */
    completeStage: function() {
        window.location.href = `/tasks/${this.taskId}`;
    },
    
    /**
     * Обработчик изменения состояния чекбокса подтверждения изображения
     * @param {string} imageType - 'current' или 'next'
     * @param {HTMLInputElement} checkbox - элемент чекбокса
     */
    handleImageConfirmChange: function(imageType, checkbox) {
        console.log(`Изображение ${imageType} подтверждено: ${checkbox.checked}`);
        
        // Если чекбокс снят, изображение считается дубликатом
        if (!checkbox.checked) {
            console.log(`Изображение ${imageType} помечено как дубликат`);
        }
    }
};

// Инициализация объекта при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('processing-unduplicates-stage1')) {
        ProcessingUnduplicatesStage1.init();
    }
});

/**
 * Обработчик изменения сортировки
 * @param {string} sortBy - 'order' или 'similarity'
 */
function changeSortUndup(sortBy) {
    const container = document.getElementById('processing-unduplicates-stage1');
    const taskId = container.dataset.taskId;
    const currentImageId = container.dataset.currentImageId;
    
    let url = `/processing/unduplicates/stage1/${taskId}?sort_by=${sortBy}`;
    if (currentImageId) {
        url += `&image_id=${currentImageId}`;
    }
    window.location.href = url;
}