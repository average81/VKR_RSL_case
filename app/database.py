from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# Используем существующую базу данных из проекта
SQLALCHEMY_DATABASE_URL = "sqlite:///./processed_images.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Миграция: добавление столбца similarity_score в существующую БД
def migrate_add_similarity_score():
    """Добавляет столбец similarity_score в таблицу images, если его нет"""
    import os
    if os.path.exists("./processed_images.db"):
        import sqlite3
        conn = sqlite3.connect("./processed_images.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(images)")
        columns = [row[1] for row in cursor.fetchall()]
        if "similarity_score" not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN similarity_score FLOAT")
            conn.commit()
            print("Добавлен столбец similarity_score в таблицу images")
        conn.close()

migrate_add_similarity_score()

# 🔽 Импортируем все модели, чтобы Base их знала
import app.models  #
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
