// Variables provided by the HTML template: taskId, groupId, currentIssueId, currentGroupImages

// Инициализация drag and drop
function initDragAndDrop() {
    // Элементы, которые можно перетаскивать
    const draggableElements = document.querySelectorAll('.draggable-image');
    draggableElements.forEach(element => {
        element.addEventListener('dragstart', dragStart);
    });

    // Целевые области (выпуски)
    const issueItems = document.querySelectorAll('.issue-item');
    issueItems.forEach(item => {
        item.addEventListener('dragover', dragOver);
        item.addEventListener('drop', drop);
    });

    // Область содержимого выпуска
    const issueContent = document.getElementById('issueContent');
    issueContent.addEventListener('dragover', dragOver);
    issueContent.addEventListener('drop', drop);
}

function dragStart(e) {
    e.dataTransfer.setData('text/plain', e.target.closest('.draggable-image').dataset.imageId);
    e.target.closest('.draggable-image').style.opacity = '0.4';
}

function dragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

function drop(e) {
    e.preventDefault();
    
    const imageId = e.dataTransfer.getData('text/plain');
    const draggedElement = document.querySelector(`[data-image-id="${imageId}"]`).closest('.draggable-image');
    draggedElement.style.opacity = '1';

    // Определяем, куда бросили
    let targetIssueId = null;
    
    if (e.target.closest('.issue-item')) {
        targetIssueId = e.target.closest('.issue-item').dataset.issueId;
    } else if (e.target.closest('[data-issue-id]')) {
        targetIssueId = e.target.closest('[data-issue-id]').dataset.issueId;
    }

    if (targetIssueId) {
        addToIssue(imageId, targetIssueId);
    }
}

// Выбор выпуска
function selectIssue(issueId) {
    document.querySelectorAll('.issue-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-issue-id="${issueId}"]`).classList.add('active');
    
    currentIssueId = issueId;
    loadIssueContent(issueId);
}

// Загрузка содержимого выпуска
async function loadIssueContent(issueId) {
    try {
        const response = await fetch(`/processing/stage2/${taskId}/issue/${issueId}`);
        if (response.ok) {
            const content = await response.text();
            document.getElementById('issueContent').innerHTML = content;
        }
    } catch (error) {
        console.error('Error loading issue content:', error);
    }
}

// Добавление изображения в выпуск
async function addToIssue(imageId, issueId) {
    try {
        const response = await fetch(`/processing/stage2/${taskId}/issue/${issueId}/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_id: parseInt(imageId)
            })
        });

        if (response.ok) {
            // Удаляем изображение из группы сопоставления
            document.querySelector(`[data-image-id="${imageId}"]`).closest('.col-6').remove();
            
            // Обновляем содержимое выпуска
            if (issueId == currentIssueId) {
                loadIssueContent(issueId);
            }
            
            // Обновляем счетчик выпуска
            updateIssueBadge(issueId);
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Удаление изображения из выпуска
async function removeFromIssue(imageId, issueId) {
    if (!confirm('Удалить изображение из выпуска?')) return;
    
    try {
        const response = await fetch(`/processing/stage2/${taskId}/issue/${issueId}/remove`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_id: parseInt(imageId)
            })
        });

        if (response.ok) {
            // Добавляем изображение обратно в группу сопоставления
            const matchingImages = document.getElementById('matchingImages');
            const image = currentGroupImages.find(img => img.id == imageId);
            
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3';
            col.innerHTML = `
                <div class="card h-100 draggable-image" draggable="true" data-image-id="${image.id}">
                    <img src="${image.path}" class="card-img-top" alt="Изображение" style="height: 200px; object-fit: contain; background: #f8f9fa;">
                    <div class="card-body p-2">
                        <small class="text-muted">${image.filename}</small>
                    </div>
                </div>
            `;
            matchingImages.appendChild(col);
            
            // Обновляем содержимое выпуска
            if (issueId == currentIssueId) {
                loadIssueContent(issueId);
            }
            
            // Обновляем счетчик выпуска
            updateIssueBadge(issueId);
            
            // Перестраиваем drag and drop
            initDragAndDrop();
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Создание нового выпуска
async function createIssue() {
    const issueName = document.getElementById('issueName').value.trim();
    if (!issueName) {
        alert('Введите название выпуска');
        return;
    }

    try {
        const response = await fetch(`/processing/stage2/${taskId}/issue`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: issueName
            })
        });

        if (response.ok) {
            const data = await response.json();
            
            // Добавляем новый выпуск в список
            const listGroup = document.querySelector('.list-group');
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center issue-item';
            item.dataset.issueId = data.id;
            item.onclick = () => selectIssue(data.id);
            item.innerHTML = `
                <div>
                    <strong>${data.name}</strong>
                    <div class="small text-muted">0 изображений</div>
                </div>
                <span class="badge bg-secondary rounded-pill">0</span>
            `;
            listGroup.appendChild(item);
            
            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('createIssueModal'));
            modal.hide();
            
            // Очищаем поле ввода
            document.getElementById('issueName').value = '';
            
            // Выбираем новый выпуск
            selectIssue(data.id);
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Удаление выпуска
async function deleteIssue(issueId) {
    if (!confirm('Удалить выпуск? Все изображения будут возвращены в группу сопоставления.')) return;
    
    try {
        const response = await fetch(`/processing/stage2/${taskId}/issue/${issueId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Удаляем из списка
            document.querySelector(`[data-issue-id="${issueId}"]`).remove();
            
            // Очищаем содержимое, если это был текущий выпуск
            if (issueId == currentIssueId) {
                document.getElementById('issueContent').innerHTML = `
                    <div class="text-center text-muted py-5">
                        <i class="bi bi-folder2-open" style="font-size: 3rem;"></i>
                        <p class="mt-3">Выберите выпуск для просмотра содержимого</p>
                    </div>
                `;
                currentIssueId = null;
            }
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Обновление счетчика выпуска
function updateIssueBadge(issueId) {
    // Этот метод будет реализован на бэкенде
    // Пока что обновляем вручную при необходимости
}

// Навигация между группами
function navigateGroup(direction) {
    window.location.href = `/processing/stage2/${taskId}?group_id=${direction}`;
}

// Отмена обработки
function cancelProcessing() {
    if (confirm('Отменить обработку? Все изменения будут потеряны.')) {
        window.location.href = `/tasks/${taskId}`;
    }
}

// Сохранение текущей группы
async function saveGroup() {
    try {
        const response = await fetch(`/processing/stage2/${taskId}/group/${groupId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                action: 'save'
            })
        });

        if (response.ok) {
            navigateGroup('next');
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Завершение этапа
async function completeProcessing() {
    if (!confirm('Завершить второй этап обработки?')) return;

    try {
        const response = await fetch(`/processing/stage2/${taskId}/complete`, {
            method: 'POST'
        });

        if (response.ok) {
            alert('Второй этап обработки завершен!');
            window.location.href = `/tasks/${taskId}`;
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Обработка чекбокса "Подтвердить все"
document.getElementById('confirm_all').addEventListener('change', function() {
    // Реализация будет зависеть от конкретных требований
    console.log('Confirm all toggled:', this.checked);
});

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initDragAndDrop();
});