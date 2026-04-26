// Variables provided by the HTML template: taskId, groupId, currentIssueId, currentGroupImages, taskOutputPath

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
        const url = issueId ? 
            `/processing/stage2/${taskId}/issue/${issueId}?group_id=${groupId}` :
            `/processing/stage2/${taskId}?group_id=${groupId}`;
        const response = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        if (response.ok) {
            const content = await response.text();
            document.getElementById('issueContent').innerHTML = content;
            // После загрузки содержимого обновляем счётчик
            if (currentIssueId) {
                updateIssueBadge(currentIssueId);
            }
            
            // Добавляем кнопку "Подтвердить" к заголовку выпуска, если содержимое загружено
            const issueHeader = document.querySelector('#issueContent .card-header .d-flex');
            if (issueHeader && issueId) {
                // Проверяем, есть ли уже группа кнопок с кнопкой подтверждения
                let buttonGroup = issueHeader.querySelector('.btn-group');
                if (!buttonGroup) {
                    // Создаем группу кнопок
                    buttonGroup = document.createElement('div');
                    buttonGroup.className = 'btn-group';
                    buttonGroup.role = 'group';
                    
                    // Кнопка удаления (сохраняем существующую или создаем новую)
                    let deleteButton = issueHeader.querySelector('.btn-outline-danger') || document.querySelector(`[data-issue-id="${issueId}"]`).nextElementSibling;
                    if (deleteButton) {
                        deleteButton.classList.add('btn-sm');
                    } else {
                        deleteButton = document.createElement('button');
                        deleteButton.className = 'btn btn-sm btn-outline-danger';
                        deleteButton.innerHTML = '<i class="bi bi-trash"></i> Удалить';
                        deleteButton.onclick = () => deleteIssue(issueId);
                    }
                    
                    // Кнопка подтверждения
                    const confirmButton = document.createElement('button');
                    confirmButton.className = 'btn btn-sm btn-primary';
                    confirmButton.textContent = 'Подтвердить';
                    confirmButton.onclick = confirmGroupVerification;
                    
                    // Добавляем кнопки в группу
                    buttonGroup.appendChild(deleteButton);
                    buttonGroup.appendChild(confirmButton);
                    
                    // Добавляем группу кнопок в заголовок
                    issueHeader.appendChild(buttonGroup);
                } else {
                    // Проверяем, есть ли уже кнопка подтверждения
                    const confirmButton = buttonGroup.querySelector('.btn-primary');
                    if (!confirmButton) {
                        // Добавляем кнопку подтверждения в существующую группу
                        const newConfirmButton = document.createElement('button');
                        newConfirmButton.className = 'btn btn-sm btn-primary';
                        newConfirmButton.textContent = 'Подтвердить';
                        newConfirmButton.onclick = confirmGroupVerification;
                        buttonGroup.appendChild(newConfirmButton);
                    }
                }
            }
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
            
            // Обновляем счётчик нераспределенных изображений
            updateUnsortedCounter();
            
            // Обновляем содержимое выпуска
            if (issueId == currentIssueId) {
                loadIssueContent(issueId);
            } else {
                // Если выпуск не текущий, обновляем счётчик напрямую
                updateIssueBadge(issueId);
            }
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
    
    // Получить имя файла из данных изображения, а не из DOM-элемента
    const image = unsortedImages.find(img => img.id == imageId);
    const filename = image ? image.filename : `image_${imageId}`;

    try {
        const response = await fetch(`/processing/stage2/${taskId}/issue/${issueId}/remove`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_id: parseInt(imageId),
                filename: filename
            })
        });
        if (response.ok) {
            // Получаем новый путь из ответа сервера ДО любых обновлений
            const data = await response.json();
            // Используем путь из ответа сервера, заменяя обратные слеши на прямые
            const unsortedImagePath = data.new_path.replace(/\\/g, '/');
            
            // Удаляем карточку из DOM текущего выпуска до обновления счётчика
            const imageCard = document.querySelector(`[data-image-id="${imageId}"]`);
            if (imageCard) {
                imageCard.closest('.col-6, .col-md-4, .col-lg-3').remove();
            }

            // Перезагружаем содержимое выпуска, что автоматически обновит счётчик
            loadIssueContent(issueId);
            // Добавляем изображение обратно в группу сопоставления
            const matchingImages = document.getElementById('unsortedImages');
            
            // Создаем элемент изображения с корректным путем
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3';
            
            col.innerHTML = `
                <div class="card h-100 draggable-image" draggable="true" data-image-id="${imageId}">
                    <img src="/${unsortedImagePath}" class="card-img-top" alt="Изображение" style="height: 200px; object-fit: contain; background: #f8f9fa;">
                    <div class="card-body p-2">
                        <small class="text-muted">${filename}</small>
                        <button class="btn btn-sm btn-outline-primary w-100 mt-1" 
                                onclick="moveToIssue(${imageId})">
                            Перенести
                        </button>
                    </div>
                </div>
            `;
            matchingImages.appendChild(col);
            
            // Перестраиваем drag and drop
            initDragAndDrop();
            
            // Обновляем счётчик нераспределенных изображений
            updateUnsortedCounter();
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
                    <strong>${data.name} - Выпуск ${data.number}</strong>
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
    // Находим элемент выпуска по ID
    const issueElement = document.querySelector(`[data-issue-id="${issueId}"]`);
    if (!issueElement) return;

    // Находим элементы счётчика и текста
    const badge = issueElement.querySelector('.badge');
    const imageCountText = issueElement.querySelector('.text-muted');

    // Получаем текущее количество изображений в выпуске
    // Считаем только карточки изображений по их уникальному контексту
    const issueContent = document.getElementById('issueContent');
    const imageCards = issueContent.querySelectorAll('.row.g-2 .card');
    let imageCount = imageCards.length;

    // Обновляем счётчик
    if (badge) {
        badge.textContent = imageCount;
    }

    // Обновляем текстовое описание
    if (imageCountText) {
        imageCountText.textContent = `${imageCount} изображений`;
    }
}


// Обновление счетчика нераспределенных изображений
function updateUnsortedCounter() {
    // Находим контейнер нераспределенных изображений
    const unsortedContainer = document.getElementById('unsortedImages');
    if (!unsortedContainer) return;
    
    // Получаем количество изображений в контейнере
    const imageCount = unsortedContainer.querySelectorAll('.draggable-image').length;
    
    // Находим текстовый элемент с описанием
    const textElement = document.querySelector('.card-body p.text-muted');
    if (textElement) {
        textElement.textContent = `Обнаружено ${imageCount} изображений, которые необходимо распределить по выпускам.`;
    }
}

// Навигация между группами
function navigateGroup(direction) {
    let url = `/processing/stage2/${taskId}`;
    if (currentIssueId) {
        url += `/issue/${currentIssueId}`;
    }
    url += `?group_id=${direction}`;
    window.location.href = url;
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
        let url = `/processing/stage2/${taskId}/group/${groupId}`;
        if (currentIssueId) {
            url += `?issue_id=${currentIssueId}`;
        }
        const response = await fetch(url, {
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
        let url = `/processing/stage2/${taskId}/complete`;
        if (currentIssueId) {
            url += `?issue_id=${currentIssueId}`;
        }
        const response = await fetch(url, {
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

// Подтверждение проверки группы
async function confirmGroupVerification() {
    if (!confirm('Подтвердить проверку текущей группы?')) return;
    
    try {
        let url = `/processing/stage2/${taskId}/group/confirm`;
        if (currentIssueId) {
            url += `?issue_id=${currentIssueId}`;
        }
        const response = await fetch(url, {
            method: 'POST'
        });

        if (response.ok) {
            alert('Проверка группы подтверждена!');
            // Navigate to next group
            navigateGroup('next');
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Завершение задачи
async function completeTask() {
    if (!confirm('Завершить выполнение задачи?')) return;

    try {
        const response = await fetch(`/tasks/${taskId}/user_complete`, {
            method: 'POST'
        });

        if (response.ok) {
            alert('Задача успешно завершена!');
            window.location.href = `/tasks/${taskId}`;
        } else {
            const data = await response.json();
            alert('Ошибка: ' + data.detail);
        }
    } catch (error) {
        alert('Ошибка сети: ' + error.message);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initDragAndDrop();
});

/**
 * Открывает модальное окно для выбора группы при перемещении изображения
 * @param {number} imageId - ID изображения, которое нужно переместить
 */
function moveToIssue(imageId) {
    // Сохраняем ID изображения в глобальной переменной
    window.currentMovingImageId = imageId;
    
    // Очищаем предыдущий список
    const issueList = document.getElementById('issueList');
    issueList.innerHTML = '';
    
    // Получаем список выпусков из уже загруженных данных или через API
    // Используем уже загруженные данные из шаблона, если доступны
    if (typeof issues !== 'undefined' && issues.length > 0) {
        // Фильтруем выпуски, исключая 'unsorted'
        const filteredIssues = issues.filter(issue => issue.name !== 'unsorted');
        
        if (filteredIssues.length > 0) {
            filteredIssues.forEach(issue => {
                const button = document.createElement('button');
                button.className = 'list-group-item list-group-item-action';
                button.type = 'button';
                
                // Определяем количество изображений в выпуске
                const imageCount = issue.images ? issue.images.length : 0;
                
                button.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${issue.name}</strong>
                            ${issue.number ? `<div class="small text-muted">Выпуск ${issue.number}</div>` : ''}
                        </div>
                        <span class="badge bg-secondary rounded-pill">${imageCount}</span>
                    </div>
                `;
                button.onclick = () => moveImageToIssue(imageId, issue.id);
                issueList.appendChild(button);
            });
        } else {
            const item = document.createElement('div');
            item.className = 'list-group-item text-center text-muted';
            item.textContent = 'Нет созданных групп';
            issueList.appendChild(item);
        }
    } else {
        // Если данные не доступны, загружаем через API
        fetch(`/processing/stage2/${taskId}/issues`)
            .then(response => response.json())
            .then(data => {
                if (data.issues && data.issues.length > 0) {
                    data.issues.forEach(issue => {
                        if (issue.name === 'unsorted') return;
                        
                        const button = document.createElement('button');
                        button.className = 'list-group-item list-group-item-action';
                        button.type = 'button';
                        
                        button.innerHTML = `
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${issue.name}</strong>
                                    ${issue.number ? `<div class="small text-muted">Выпуск ${issue.number}</div>` : ''}
                                </div>
                                <span class="badge bg-secondary rounded-pill">${issue.images_count || 0}</span>
                            </div>
                        `;
                        button.onclick = () => moveImageToIssue(imageId, issue.id);
                        issueList.appendChild(button);
                    });
                } else {
                    const item = document.createElement('div');
                    item.className = 'list-group-item text-center text-muted';
                    item.textContent = 'Нет созданных групп';
                    issueList.appendChild(item);
                }
            })
            .catch(error => {
                console.error('Ошибка при загрузке списка выпусков:', error);
                const item = document.createElement('div');
                item.className = 'list-group-item text-center text-danger';
                item.textContent = 'Ошибка загрузки групп';
                issueList.appendChild(item);
            });
    }

    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('moveImageModal'));
    modal.show();
}

/**
 * Перемещает изображение в выбранную группу
 * @param {number} imageId - ID изображения
 * @param {number} issueId - ID группы
 */
function moveImageToIssue(imageId, issueId) {
    // Используем существующий механизм добавления изображения в выпуск
    addToIssue(imageId, issueId);
    
    // Закрываем модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('moveImageModal'));
    if (modal) {
        modal.hide();
    }
}

/**
 * Создает новую группу для изображения
 */
function createNewIssueForImage() {
    // Сначала закрываем текущее модальное окно
    const modal = bootstrap.Modal.getInstance(document.getElementById('moveImageModal'));
    if (modal) {
        modal.hide();
    }
    
    // Показываем модальное окно создания выпуска
    const createModal = new bootstrap.Modal(document.getElementById('createIssueModal'));
    createModal.show();
    
    // Сохраняем ID изображения для последующего перемещения после создания выпуска
    window.imageForNewIssue = window.currentMovingImageId;
}

// Модифицируем функцию createIssue, чтобы она могла обрабатывать создание выпуска для конкретного изображения
const originalCreateIssue = createIssue;
window.createIssue = function() {
    const issueName = document.getElementById('issueName').value.trim();
    
    if (!issueName) {
        alert('Введите название выпуска');
        return;
    }
    
    // Подготавливаем данные для запроса
    const requestData = {
        name: issueName
    };
    
    // Если есть изображение для перемещения, добавляем его в запрос
    if (window.imageForNewIssue) {
        requestData.image_id = window.imageForNewIssue;
    }
    
    fetch(`/processing/stage2/${taskId}/issue`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Добавляем новый выпуск в список
            const listGroup = document.querySelector('.list-group');
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center issue-item';
            // ID выпуска теперь в data.issue.id
            item.dataset.issueId = data.issue.id;
            item.onclick = () => selectIssue(data.issue.id);
            item.innerHTML = `
                <div>
                    <strong>${data.issue.name} - Выпуск ${data.issue.number}</strong>
                    <div class="small text-muted">${data.issue.images_count} изображений</div>
                </div>
                <span class="badge bg-secondary rounded-pill">${data.issue.images_count}</span>
            `;
            listGroup.appendChild(item);
            
            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('createIssueModal'));
            modal.hide();
            
            // Очищаем поле ввода
            document.getElementById('issueName').value = '';
            
            // Очищаем переменную с изображением
            if (window.imageForNewIssue) {
                delete window.imageForNewIssue;
            }
            
            // Выбираем новый выпуск
            selectIssue(data.issue.id);
            
            // Обновляем счётчик нераспределенных изображений, если было перемещено изображение
            if (window.imageForNewIssue) {
                updateUnsortedCounter();
                delete window.imageForNewIssue;
            }
        } else {
            alert('Ошибка при создании выпуска: ' + data.detail);
        }
    })
    .catch(error => {
        console.error('Ошибка при создании выпуска:', error);
        alert('Произошла ошибка при создании выпуска');
    });
}