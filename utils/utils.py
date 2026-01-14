import yaml
import cv2
import xml.etree.ElementTree as ET
import os
import pandas as pd
from sklearn.metrics import roc_curve

#Открытие файла настроек в  yaml
def open_yaml(file):
    with open(file, 'r') as f:
        return yaml.safe_load(f)

#Сохранение yaml
def save_yaml(file, data):
    with open(file, 'w') as f:
        yaml.dump(data, f)

def xml_to_dict(xml_path):
    """Читает XML-файл в формате Pascal VOC и возвращает словарь."""
    if not os.path.exists(xml_path):
        raise FileNotFoundError(f"Файл не найден: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    data = {"annotation": {}}
    annotation = data["annotation"]

    # Основные поля
    annotation["folder"] = root.find("folder").text if root.find("folder") is not None else ""
    annotation["filename"] = root.find("filename").text if root.find("filename") is not None else ""
    annotation["path"] = root.find("path").text if root.find("path") is not None else ""  # может отсутствовать

    # Размеры
    size_elem = root.find("size")
    if size_elem is not None:
        annotation["size"] = {
            "width": int(size_elem.find("width").text) if size_elem.find("width") is not None else 0,
            "height": int(size_elem.find("height").text) if size_elem.find("height") is not None else 0,
            "depth": int(size_elem.find("depth").text) if size_elem.find("depth") is not None else 0,
        }
    else:
        annotation["size"] = {"width": 0, "height": 0, "depth": 0}

    # Объекты
    annotation["objects"] = []
    for obj in root.findall("object"):
        obj_data = {
            "name": obj.find("name").text if obj.find("name") is not None else "",
        }

        # Bounding box
        bndbox = obj.find("bndbox")
        if bndbox is not None:
            bndbox_data = {
                "xmin": int(bndbox.find("xmin").text) if bndbox.find("xmin") is not None else 0,
                "ymin": int(bndbox.find("ymin").text) if bndbox.find("ymin") is not None else 0,
                "xmax": int(bndbox.find("xmax").text) if bndbox.find("xmax") is not None else 0,
                "ymax": int(bndbox.find("ymax").text) if bndbox.find("ymax") is not None else 0,
            }
            obj_data["bndbox"] = bndbox_data


        polygon_elem = obj.find("polygon")
        if polygon_elem is not None:
            points = []
            if polygon_elem.text:
                for pair in polygon_elem.text.split(";"):
                    try:
                        x, y = map(int, pair.split(","))
                        points.append([x, y])
                    except:
                        continue
            obj_data["polygon"] = points

        annotation["objects"].append(obj_data)

    return data

#Ф-я открытия датасета и возвращения списка изображений и разметки
def open_dataset(path):
    images = []
    defects = []
    #Список файлов в папке
    for file in os.listdir(path):
        #Если файл является изображением
        if file.endswith(('.jpg', '.png', '.jpeg')):
            #Добавление изображения в список
            images.append(file)
            #Добавление разметки в список
            name = file.split('.')[0]
            defects.append(xml_to_dict(os.path.join(path, name + '.xml')))
    return images, defects

def get_roc_auc_curve_data(df: pd.DataFrame, prob_col: str = 'score', true_label_col: str = 'true_dupl'):
    """
    Возвращает данные для построения ROC AUC кривой.

    :param df: pandas DataFrame с вероятностями и истинными метками
    :param prob_col: название столбца с вероятностью того, что изображение - дубликат предыдущего
    :param true_label_col: название столбца с истинными метками дубликатов(0 или 1)
    :return: кортеж (fpr, tpr, thresholds), где:
             fpr - false positive rate
             tpr - true positive rate
             thresholds - пороги вероятностей
    """
    # Проверка наличия колонок
    if prob_col not in df.columns:
        raise ValueError(f"Столбец '{prob_col}' не найден в DataFrame")
    if true_label_col not in df.columns:
        raise ValueError(f"Столбец '{true_label_col}' не найден в DataFrame")

    # Извлечение значений
    y_true = df[true_label_col].values
    y_score = df[prob_col].values

    # Проверка значений
    if set(y_true) - {0, 1}:
        raise ValueError("Истинные метки должны быть 0 или 1")

    # Вычисление ROC кривой
    fpr, tpr, thresholds = roc_curve(y_true, y_score, drop_intermediate=True)

    return fpr, tpr, thresholds