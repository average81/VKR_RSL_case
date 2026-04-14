from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

# Импортируем утилиты для сообщений и настройки
from app.utils.messages import get_flashed_messages
from app.settings import settings

# Импортируем зависимости для создания таблиц
from app.database import engine, Base


# Создаем таблицы (только для разработки, не для продакшена!)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VKR RSL Case")

# Добавляем SessionMiddleware для работы с сессиями
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=3600)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Настраиваем шаблоны Jinja2
templates = Jinja2Templates(directory="app/templates")
# Добавляем get_flashed_messages в глобальные переменные шаблонов
templates.env.globals["get_flashed_messages"] = get_flashed_messages

# Подключаем API роутеры
from app.api import auth, tasks, images, grouping, processing, admin

app.include_router(auth.router, tags=["auth"])
app.include_router(tasks.router, tags=["tasks"])
app.include_router(admin.router, tags=["admin"])
#app.include_router(images.router, prefix="/images", tags=["images"])
#app.include_router(grouping.router, prefix="/grouping", tags=["grouping"])
#app.include_router(processing.router, prefix="/processing", tags=["processing"])

@app.get("/")
async def root(request: Request):
    # Проверяем наличие токена в cookie
    token = request.cookies.get("access_token")
    if token:
        # Если токен есть, перенаправляем на страницу задач
        return RedirectResponse(url="/tasks")
    # Если токена нет, перенаправляем на страницу входа
    return RedirectResponse(url="/auth/login")
