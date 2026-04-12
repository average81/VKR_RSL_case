/*
 * Client-side JavaScript for VKR_RSL_case web interface
 * Implements functionality for task management, image processing and validation
 */

// Global variables
let currentTaskId = null;
let progressInterval = null;

// Initialize page on load
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
});

/**
 * Initialize page based on its type
 */
function initializePage() {
    const body = document.body;

    if (body.id === 'login-page') {
        setupLoginPage();
    } else if (body.id === 'tasks-manager-page') {
        setupTasksManagerPage();
    } else if (body.id === 'tasks-employee-page') {
        setupTasksEmployeePage();
    } else if (body.id === 'task-process-page') {
        setupTaskProcessPage();
    } else if (body.id === 'validate-stage1-page') {
        setupValidateStage1Page();
    } else if (body.id === 'validate-stage2-page') {
        setupValidateStage2Page();
    } else if (body.id === 'settings-page') {
        setupSettingsPage();
    }
}

/**
 * Setup login page functionality
 */
function setupLoginPage() {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            login(username, password);
        });
    }
}

/**
 * Setup tasks manager page functionality
 */
function setupTasksManagerPage() {
    loadTasks();

    const createTaskBtn = document.getElementById('create-task-btn');
    if (createTaskBtn) {
        createTaskBtn.addEventListener('click', function() {
            showCreateTaskModal();
        });
    }
}

/**
 * Setup tasks employee page functionality
 */
function setupTasksEmployeePage() {
    loadTasks();

    // Auto-refresh tasks every 30 seconds
    setInterval(loadTasks, 30000);
}

/**
 * Setup task processing page functionality
 */
function setupTaskProcessPage() {
    const urlParams = new URLSearchParams(window.location.search);
    currentTaskId = urlParams.get('task_id');

    if (currentTaskId) {
        // Check if task is processing and update progress
        updateProgress(currentTaskId);
    }

    const startBtn = document.getElementById('start-processing-btn');
    if (startBtn) {
        startBtn.addEventListener('click', function() {
            startTaskProcessing(currentTaskId);
        });
    }
}

/**
 * Setup stage 1 validation page functionality
 */
function setupValidateStage1Page() {
    const urlParams = new URLSearchParams(window.location.search);
    currentTaskId = urlParams.get('task_id');

    if (currentTaskId) {
        loadImages(currentTaskId);
        loadDuplicateGroups(currentTaskId);
    }

    const validateAllBtn = document.getElementById('validate-all-btn');
    if (validateAllBtn) {
        validateAllBtn.addEventListener('click', function() {
            validateAllImages(currentTaskId, 'confirmed');
        });
    }
}

/**
 * Setup stage 2 validation page functionality
 */
function setupValidateStage2Page() {
    const urlParams = new URLSearchParams(window.location.search);
    currentTaskId = urlParams.get('task_id');

    if (currentTaskId) {
        loadImageClusters(currentTaskId);
    }

    const validateAllBtn = document.getElementById('validate-all-btn');
    if (validateAllBtn) {
        validateAllBtn.addEventListener('click', function() {
            validateAllImages(currentTaskId, 'confirmed');
        });
    }
}

/**
 * Setup settings page functionality
 */
function setupSettingsPage() {
    loadAlgorithmSettings();

    const saveSettingsBtn = document.getElementById('save-settings-btn');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', function() {
            saveAlgorithmSettings();
        });
    }
}

/**
 * Update processing progress for a task
 */
async function updateProgress(taskId) {
    try {
        const response = await fetch(`/images/progress/${taskId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const progressData = await response.json();

        // Update progress elements
        document.getElementById('processed-count').textContent = progressData.processed;
        document.getElementById('duplicates-count').textContent = progressData.duplicates_found;
        document.getElementById('clusters-count').textContent = progressData.clusters_found;

        // Update progress bar
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.width = `${progressData.progress_percent}%`;
        progressBar.setAttribute('aria-valuenow', progressData.progress_percent);

        // Update progress text
        document.getElementById('progress-text').textContent =
            `${progressData.progress_percent}% Complete`;

        // Continue updating if task is still processing
        if (progressData.status === 'processing') {
            setTimeout(() => updateProgress(taskId), 2000);
        } else {
            // Stop progress updates
            if (progressInterval) {
                clearInterval(progressInterval);
                progressInterval = null;
            }
        }

    } catch (error) {
        console.error('Error updating progress:', error);
        showError('Failed to update progress. Please try again.');

        // Retry after 5 seconds
        setTimeout(() => updateProgress(taskId), 5000);
    }
}

/**
 * Validate a single image
 */
async function validateImage(imageId, result) {
    try {
        const response = await fetch(`/images/${imageId}/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({result: result})
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const validatedImage = await response.json();

        // Update UI
        const imageElement = document.getElementById(`image-${imageId}`);
        if (imageElement) {
            imageElement.classList.add('validated');
            const validateBtn = imageElement.querySelector('.validate-btn');
            if (validateBtn) {
                validateBtn.disabled = true;
                validateBtn.textContent = 'Validated';
            }
        }

        showSuccess('Image validated successfully');

    } catch (error) {
        console.error('Error validating image:', error);
        showError('Failed to validate image. Please try again.');
    }
}

/**
 * Validate all images in a task
 */
async function validateAllImages(taskId, result) {
    try {
        const response = await fetch(`/images/task/${taskId}/validate-all`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({result: result})
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const resultData = await response.json();

        // Update all image elements
        const validateButtons = document.querySelectorAll('.validate-btn');
        validateButtons.forEach(btn => {
            btn.disabled = true;
            btn.textContent = 'Validated';
        });

        const imageItems = document.querySelectorAll('.image-item');
        imageItems.forEach(item => {
            item.classList.add('validated');
        });

        showSuccess('All images validated successfully');

    } catch (error) {
        console.error('Error validating all images:', error);
        showError('Failed to validate all images. Please try again.');
    }
}

/**
 * Move an image from duplicates group
 */
async function moveImageFromDuplicates(imageId) {
    if (!confirm('Are you sure you want to move this image from duplicates group?')) {
        return;
    }

    try {
        const response = await fetch(`/images/${imageId}/move-duplicate`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const movedImage = await response.json();

        // Remove from duplicates group UI
        const imageElement = document.getElementById(`image-${imageId}`);
        if (imageElement) {
            imageElement.remove();
        }

        showSuccess('Image moved from duplicates successfully');

    } catch (error) {
        console.error('Error moving image from duplicates:', error);
        showError('Failed to move image from duplicates. Please try again.');
    }
}

/**
 * Start task processing
 */
async function startTaskProcessing(taskId) {
    const startBtn = document.getElementById('start-processing-btn');
    const originalText = startBtn.textContent;

    // Show loading state
    startBtn.disabled = true;
    startBtn.textContent = 'Processing...';

    try {
        // Collect form data
        const formData = {
            first_image: document.getElementById('first-image').value,
            last_image: document.getElementById('last-image').value,
            stage: document.querySelector('input[name="stage"]:checked').value,
            validate_results: document.getElementById('validate-results').checked,
            output_path: document.getElementById('output-path').value
        };

        const response = await fetch(`/tasks/${taskId}/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const updatedTask = await response.json();

        // Update UI
        document.getElementById('task-status').textContent = 'Processing';
        document.getElementById('task-status').className = 'badge bg-warning';

        // Start progress updates
        updateProgress(taskId);

        showSuccess('Task processing started successfully');

    } catch (error) {
        console.error('Error starting task processing:', error);
        showError('Failed to start task processing. Please try again.');

        // Restore button state
        startBtn.disabled = false;
        startBtn.textContent = originalText;
    }
}

/**
 * Complete task processing
 */
async function completeTask(taskId) {
    if (!confirm('Are you sure you want to mark this task as completed?')) {
        return;
    }

    try {
        const response = await fetch(`/tasks/${taskId}/complete`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const updatedTask = await response.json();

        // Update UI
        document.getElementById('task-status').textContent = 'Completed';
        document.getElementById('task-status').className = 'badge bg-success';

        const completeBtn = document.getElementById('complete-task-btn');
        if (completeBtn) {
            completeBtn.disabled = true;
            completeBtn.textContent = 'Completed';
        }

        showSuccess('Task marked as completed');

    } catch (error) {
        console.error('Error completing task:', error);
        showError('Failed to complete task. Please try again.');
    }
}

/**
 * Validate task results
 */
async function validateTask(taskId) {
    if (!confirm('Are you sure you want to validate this task?')) {
        return;
    }

    try {
        const response = await fetch(`/tasks/${taskId}/validate`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const updatedTask = await response.json();

        // Update UI
        document.getElementById('task-status').textContent = 'Validated';
        document.getElementById('task-status').className = 'badge bg-success';

        const validateBtn = document.getElementById('validate-task-btn');
        if (validateBtn) {
            validateBtn.disabled = true;
            validateBtn.textContent = 'Validated';
        }

        showSuccess('Task validated successfully');

    } catch (error) {
        console.error('Error validating task:', error);
        showError('Failed to validate task. Please try again.');
    }
}

/**
 * Create a new task
 */
async function createTask() {
    try {
        // Collect form data
        const formData = {
            name: document.getElementById('task-name').value,
            description: document.getElementById('task-description').value,
            input_path: document.getElementById('input-path').value,
            output_path: document.getElementById('output-path').value
        };

        const response = await fetch('/tasks/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const newTask = await response.json();

        // Add new task to table
        addTaskToTable(newTask);

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('createTaskModal'));
        modal.hide();

        // Clear form
        document.getElementById('create-task-form').reset();

        showSuccess('Task created successfully');

    } catch (error) {
        console.error('Error creating task:', error);
        showError('Failed to create task. Please try again.');
    }
}

/**
 * Delete a task
 */
async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        // Remove task from table
        const row = document.getElementById(`task-row-${taskId}`);
        if (row) {
            row.remove();
        }

        showSuccess('Task deleted successfully');

    } catch (error) {
        console.error('Error deleting task:', error);
        showError('Failed to delete task. Please try again.');
    }
}

/**
 * Load tasks for current user
 */
async function loadTasks() {
    try {
        const response = await fetch('/tasks/');

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const tasks = await response.json();

        // Clear existing table rows
        const tbody = document.querySelector('#tasks-table tbody');
        if (tbody) {
            tbody.innerHTML = '';

            // Add tasks to table
            tasks.forEach(task => {
                addTaskToTable(task);
            });
        }

    } catch (error) {
        console.error('Error loading tasks:', error);
        showError('Failed to load tasks. Please refresh the page.');
    }
}

/**
 * Add a task to the tasks table
 */
function addTaskToTable(task) {
    const tbody = document.querySelector('#tasks-table tbody');
    if (!tbody) return;

    // Determine status badge class
    let statusClass = 'bg-secondary';
    switch (task.status) {
        case 'pending':
            statusClass = 'bg-secondary';
            break;
        case 'processing':
            statusClass = 'bg-warning';
            break;
        case 'completed':
            statusClass = 'bg-info';
            break;
        case 'validated':
            statusClass = 'bg-success';
            break;
    }

    // Determine stage text
    const stageText = task.stage === 1 ? 'Stage 1: Find Duplicates' : 'Stage 2: Cluster by Issues';

    // Create table row
    const row = document.createElement('tr');
    row.id = `task-row-${task.id}`;
    row.innerHTML = `
        <td>${task.id}</td>
        <td>${task.name}</td>
        <td>${task.description || '-'}</td>
        <td><span class="badge ${statusClass}">${task.status}</span></td>
        <td>${stageText}</td>
        <td>${task.input_path}</td>
        <td>${task.output_path}</td>
        <td>${new Date(task.created_at).toLocaleString()}</td>
        <td>
            <div class="btn-group" role="group">
                <button type="button" class="btn btn-sm btn-primary" onclick="openTaskDetails(${task.id})">Details</button>
                ${task.status === 'pending' ? `<button type="button" class="btn btn-sm btn-success" onclick="startTaskProcessing(${task.id})">Start</button>` : ''}
                ${task.status === 'processing' ? `<button type="button" class="btn btn-sm btn-info" onclick="completeTask(${task.id})">Complete</button>` : ''}
                ${task.status === 'completed' ? `<button type="button" class="btn btn-sm btn-success" onclick="validateTask(${task.id})">Validate</button>` : ''}
                <button type="button" class="btn btn-sm btn-danger" onclick="deleteTask(${task.id})">Delete</button>
            </div>
        </td>
    `;

    tbody.appendChild(row);
}

/**
 * Open task details page
 */
function openTaskDetails(taskId) {
    window.location.href = `/task-details?task_id=${taskId}`;
}

/**
 * Show create task modal
 */
function showCreateTaskModal() {
    const modal = new bootstrap.Modal(document.getElementById('createTaskModal'));
    modal.show();
}

/**
 * Load images for a task
 */
async function loadImageClusters(taskId) {
    try {
        const response = await fetch(`/images/task/${taskId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const images = await response.json();

        // Group images by cluster (main_double)
        const clusters = {};
        images.forEach(image => {
            const clusterName = image.main_double || 'Unknown';
            if (!clusters[clusterName]) {
                clusters[clusterName] = [];
            }
            clusters[clusterName].push(image);
        });

        // Display clusters
        const clustersContainer = document.getElementById('clusters-container');
        if (clustersContainer) {
            clustersContainer.innerHTML = '';

            Object.keys(clusters).forEach(clusterName => {
                const cluster = clusters[clusterName];
                const clusterDiv = document.createElement('div');
                clusterDiv.className = 'cluster mb-4';
                clusterDiv.innerHTML = `
                    <div class="cluster-header bg-light p-3 rounded-top">
                        <h5>${clusterName} <span class="badge bg-secondary">${cluster.length} images</span></h5>
                    </div>
                    <div class="cluster-images p-3 border border-top-0 rounded-bottom">
                        <div class="row">
                            ${cluster.map(image => `
                                <div class="col-md-3 mb-3">
                                    <div class="card h-100">
                                        <img src="/static/images/${image.filename}" class="card-img-top" alt="${image.filename}" style="height: 200px; object-fit: cover;">
                                        <div class="card-body">
                                            <h6 class="card-title">${image.filename}</h6>
                                            <p class="card-text">
                                                <small class="text-muted">Group: ${image.duplicate_group || '-'}</small><br>
                                                <small class="text-muted">Validated: ${image.is_validated ? 'Yes' : 'No'}</small>
                                            </p>
                                            <button class="btn btn-sm btn-primary validate-btn" onclick="validateImage(${image.id}, 'confirmed')" ${image.is_validated ? 'disabled' : ''}>
                                                ${image.is_validated ? 'Validated' : 'Validate'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
                clustersContainer.appendChild(clusterDiv);
            });
        }

    } catch (error) {
        console.error('Error loading image clusters:', error);
        showError('Failed to load image clusters. Please refresh the page.');
    }
}

/**
 * Load images for a task
 */
async function loadImages(taskId) {
    try {
        const response = await fetch(`/images/task/${taskId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const images = await response.json();

        // Display images
        const imagesContainer = document.getElementById('images-container');
        if (imagesContainer) {
            imagesContainer.innerHTML = '';

            images.forEach(image => {
                const imageDiv = document.createElement('div');
                imageDiv.className = 'image-item mb-3';
                imageDiv.id = `image-${image.id}`;
                imageDiv.innerHTML = `
                    <div class="card">
                        <div class="row g-0">
                            <div class="col-md-4">
                                <img src="/static/images/${image.filename}" class="img-fluid rounded-start" alt="${image.filename}" style="height: 200px; object-fit: cover;">
                            </div>
                            <div class="col-md-8">
                                <div class="card-body">
                                    <h5 class="card-title">${image.filename}</h5>
                                    <p class="card-text">
                                        <strong>Status:</strong> ${image.is_duplicate ? 'Duplicate' : 'Original'}<br>
                                        ${image.duplicate_group !== null ? `<strong>Group:</strong> ${image.duplicate_group}<br>` : ''}
                                        <strong>Validated:</strong> ${image.is_validated ? 'Yes' : 'No'}
                                    </p>
                                    <div class="btn-group" role="group">
                                        <button type="button" class="btn btn-sm btn-primary validate-btn" onclick="validateImage(${image.id}, 'confirmed')" ${image.is_validated ? 'disabled' : ''}>
                                            ${image.is_validated ? 'Validated' : 'Validate'}
                                        </button>
                                        ${image.is_duplicate ? `<button type="button" class="btn btn-sm btn-warning" onclick="moveImageFromDuplicates(${image.id})">Move from D