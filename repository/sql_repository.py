#repository/sql_repository.py

from abc import ABC, abstractmethod
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base

#Базовый класс
Base = declarative_base()

#Создаем движок для работы с базой данных
def create_sqlengine(path: str):

    engine = create_engine('sqlite:///' + path)
    #Создаем таблицы базы данных
    Base.metadata.create_all(engine)
    return engine

#Класс данных для базы в ОЗУ
class Processed_table(ABC):
    def __init__(self, timestamp: datetime, user: str, filename: str, path: str, duplicates: int, main_double: str, enhanced_path: str):
        self.timestamp = timestamp
        self.user = user
        self.filename = filename
        self.path = path
        self.duplicates = duplicates
        self.main_double = main_double
        self.enhanced_path = enhanced_path

#Класс данных для SQL базы в БД
class Processed_sql(Base):
    __tablename__ = 'processed_images'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    user = Column(String)
    filename = Column(String)
    path = Column(String)
    duplicates = Column(Integer)
    main_double = Column(String)
    enhanced_path = Column(String)
    def __repr__(self):
        return ("<Processed_table(id='%s', timestamp='%s', user='%s', filename='%s', path='%s', duplicates='%s', "
                "main_double='%s', enhanced_path='%s')>") % (self.id, self.timestamp, self.user, self.filename,
                                                             self.path, self.duplicates, self.main_double, self.enhanced_path)



class ProcessedRepository(ABC):
    @abstractmethod
    def add_proc_image(self, processed_image: Processed_table):
        pass

    @abstractmethod
    def get_proc_images(self):
        pass

class SQLProcessedRepository(ProcessedRepository):
    def __init__(self, engine):
        #Создаем сессию для работы с базой данных
        self.session = sessionmaker(bind=engine)()

    def add_proc_image(self, processed_image: Processed_table):
        new_proc_image = Processed_sql(timestamp=processed_image.timestamp, user=processed_image.user,
                                      filename=processed_image.filename, path=processed_image.path,
                                      duplicates=processed_image.duplicates, main_double=processed_image.main_double,
                                      enhanced_path=processed_image.enhanced_path)
        self.session.add(new_proc_image)
        try:
            self.session.commit()
            return new_proc_image.id
        except Exception as e:
            self.session.rollback()
            print(e)
        return None

    def get_proc_images(self):
        proc_images = self.session.query(Processed_sql).all()
        return [{"id": x.id, "timestamp": x.timestamp, "user": x.user, "filename": x.filename, "path": x.path,
                 "duplicates": x.duplicates, "main_double": x.main_double, "enhanced_path":  x.enhanced_path} for x in proc_images]

    def del_proc_images(self, start:int, end:int):
        first = self.session.query(func.min(Processed_sql.id)).scalar()
        last = self.session.query(func.max(Processed_sql.id)).scalar()
        if last == None or first == None:
            return False
        if start > last or end < first:
            return False
        self.session.query(Processed_sql).filter(Processed_sql.id >= start,
                                                 Processed_sql.id <= end).delete(synchronize_session=False)
        self.session.commit()
        return True
    def update_proc_image(self, image_id: int, updates: dict) -> bool:
        """
        Обновляет запись в таблице processed_images по id.
        :param image_id: ID записи
        :param updates: Словарь с полями и новыми значениями, например:
                        {"filename": "new_name.jpg", "duplicates": 5}
        :return: True, если обновлено, иначе False
        """


        try:
            query = self.session.query(Processed_sql).filter(Processed_sql.id == image_id)
            if query.count() == 0:
                print(f"Запись с ID {image_id} не найдена.")
                return False  # Нет записи с таким ID
            query.update(updates, synchronize_session=False)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Ошибка при обновлении записи {image_id}: {e}")
            return False
