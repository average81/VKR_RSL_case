# Система обработки сканированных изображений периодических изданий

## Общее описание

Система предназначена для автоматизированной обработки сканированных страниц газет и журналов с целью:
- Удаления дубликатов страниц
- Группировки изображений по выпускам периодических изданий
- Восстановления поврежденных областей изображений
- Сохранения результатов в структурированном виде

Система работает автономно на рабочей станции без подключения к внешней сети, что обеспечивает защиту от кибер-угроз и ускоряет разворачивание.

## Архитектура приложения

Система состоит из трех основных компонентов:

### 1. Основной алгоритм обработки изображений
- **processor/duplicates_processor.py** - основной класс для обнаружения дубликатов
- **processor/feature_extractors.py** - реализация различных алгоритмов извлечения признаков (SIFT, ORB, KAZE, AKAZE)
- **processor/feature_matchers.py** - реализация алгоритмов сопоставления признаков (BF, FLANN, Symmetric)
- **processor/preprocess.py** - предварительная обработка изображений (удаление шума, выравнивание контраста)
- **processor/quality_processor.py** - оценка качества изображений и выбор наилучшего из дубликатов

### 2. Веб-интерфейс и управление задачами
- **app/** - веб-приложение на FastAPI с Jinja2 шаблонами
- **app/api/** - REST API для управления задачами, обработкой и валидацией
- **app/templates/** - HTML шаблоны для пользовательского интерфейса
- **app/services/** - бизнес-логика приложения

### 3. Хранение данных и логирование
- **processed_images.db** - SQLite база данных для хранения метаданных обработанных изображений
- **repository/sql_repository.py** - репозиторий для работы с базой данных
- **config.yml** и **config_logo.yml** - конфигурационные файлы

## API эндпоинты

### Управление задачами
- `POST /tasks/` - создание новой задачи
- `GET /tasks/` - получение списка задач
- `GET /tasks/{task_id}` - получение информации о задаче
- `PUT /tasks/{task_id}` - обновление задачи
- `DELETE /tasks/{task_id}` - удаление задачи

### Обработка изображений
- `POST /images/{task_id}/process` - запуск обработки изображений
- `GET /images/task/{task_id}` - получение изображений задачи
- `GET /images/progress/{task_id}` - получение прогресса обработки

### Кластеризация по выпускам
- `POST /grouping/{task_id}/start` - запуск кластеризации по выпускам

### Двухэтапная обработка
- `POST /processing/{task_id}/start` - запуск двухэтапной обработки
- `GET /processing/{task_id}/status` - получение статуса обработки
- `POST /processing/{task_id}/cancel` - отмена обработки

### Валидация результатов
- `POST /images/{image_id}/validate` - валидация изображения
- `POST /images/task/{task_id}/validate-all` - массовая валидация всех изображений
- `GET /images/duplicates/{task_id}` - получение групп дубликатов

## Процесс двухэтапной обработки

### Этап 1: Поиск дубликатов
1. Загрузка изображений из входной директории
2. Предварительная обработка (удаление шума, выравнивание контраста)
3. Извлечение ключевых точек и дескрипторов
4. Сравнение последовательных изображений
5. Группировка дубликатов
6. Выбор наилучшего изображения из каждой группы

### Этап 2: Кластеризация по выпускам
1. Загрузка изображений логотипов из папки logos
2. Извлечение признаков из логотипов
3. Сравнение каждого изображения с логотипами
4. Группировка изображений по схожести с логотипами
5. Создание папок для каждого выпуска

## Руководство по использованию

### Через CLI

Запуск обработки изображений:
```bash
python process_images_cli.py input_folder --output_dir output_folder --config_path config.yml
```

Запуск кластеризации по выпускам:
```bash
python logo_grouping_cli.py input_folder output_folder logos_folder --config_path config_logo.yml --metrics
```

### Через веб-интерфейс

1. Перейдите по адресу `http://localhost:8000`
2. Авторизуйтесь с вашими учетными данными
3. Создайте новую задачу в разделе "Задачи"
4. Назначьте задачу сотруднику
5. Сотрудник запускает обработку через веб-интерфейс
6. Проверьте и подтвердите результаты обработки

## Настройка и конфигурация

### config.yml
```yaml
# Путь к базе данных
db_path: "processed_images.db"

# Порог для сопоставления признаков
match_threshold: 0.75

# Порог для обнаружения дубликатов
duplicate_threshold: 0.7

# Алгоритм сопоставления (BF, FLANN, SM)
matcher: "BF"

# Алгоритм извлечения признаков (SIFT, ORB, KAZE, AKAZE)
feature_extractor: "KAZE"
```

### config_logo.yml
```yaml
# Путь к базе данных
db_path: "processed_images.db"

# Порог для сопоставления признаков
match_threshold: 0.75

# Порог для обнаружения схожести с логотипами
duplicate_threshold: 0.7

# Алгоритм сопоставления (BF, FLANN, SM)
matcher: "BF"

# Алгоритм извлечения признаков (SIFT, ORB, KAZE, AKAZE)
feature_extractor: "KAZE"
```

## Примеры использования

### Пример 1: Обработка с разными алгоритмами извлечения признаков

```bash
# Использование SIFT
python process_images_cli.py input_folder --config_path config_sift.yml

# config_sift.yml
feature_extractor: "SIFT"

# Использование ORB
python process_images_cli.py input_folder --config_path config_orb.yml

# config_orb.yml
feature_extractor: "ORB"
```

### Пример 2: Кластеризация с разными порогами схожести

```bash
# Строгая кластеризация (высокий порог)
python logo_grouping_cli.py input_folder output_folder logos_folder --config_path config_strict.yml

# config_strict.yml
duplicate_threshold: 0.85

# Слабая кластеризация (низкий порог)
python logo_grouping_cli.py input_folder output_folder logos_folder --config_path config_loose.yml

# config_loose.yml
duplicate_threshold: 0.5
```

## Требования

- Python 3.8+
- OpenCV
- NumPy
- SQLAlchemy
- FastAPI
- Jinja2
- PyYAML
- tqdm

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
uvicorn app.main:app --reload
```

Система будет доступна по адресу `http://localhost:8000`.