# Создание датасета из существующих изображений с добавлением гауссова размытия и шумов
# Создание дубликатов со своими параметрами размытия и шумов с некоторой вероятностью

# Импорт библиотек
import os
import cv2
import numpy as np
import random
import logging
import argparse

logging.basicConfig(level=logging.INFO)

#Функция размытия изображения
def blur_image(img, blur_prob = 0.2):
    if img is not None:
        # Размытие
        kernel_size = 1
        while True:
            if random.random() >= blur_prob:
                break
            kernel_size += 2
    return img

#Функция добавления шумов
def noise_image(img, noise_prob = 0.2):
    if img is not None:
        # Добавление шумов
        noise_d = 1
        while True:
            if random.random() >= noise_prob:
                break
            noise_d += 1
        noise = np.random.normal(- noise_d // 2, noise_d // 2, img.shape)
        img = cv2.add(img, noise, dtype=cv2.CV_8U)
    return img

#Функция поворота
def rotation_image(img, rotation_prob = 0.2):
    if img is not None:
        if random.random() >= rotation_prob:
            # Поворот до 5 градусов, более не разумно
            angle = random.randint(-5, 5)
            rows, cols = img.shape[:2]
            M = cv2.getRotationMatrix2D((cols / 2, rows / 2), angle, 1)
            #вычисление нового размера изображения после поворота
            w = cols * abs(np.cos(np.deg2rad(angle))) + rows * abs(np.sin(np.deg2rad(angle)))
            h = rows * abs(np.cos(np.deg2rad(angle))) + cols * abs(np.sin(np.deg2rad(angle)))
            M[0, 2] += (w - cols) / 2
            M[1, 2] += (h - rows) / 2
            #матрица нового изображения
            if len(img.shape) == 3:
                img = cv2.warpAffine(img, M, (int(w), int(h)))
            else:
                img = cv2.warpAffine(img, M, (int(w), int(h)), borderValue=255)
    return img

#Функция нормирования разрешения
def resize_image(img, max_size = (6000, 4000), min_size = (3000, 2000)):
    if img is not None:
        # Нормализация разрешения
        fx = max_size[0] / img.shape[0]
        fy = max_size[1] / img.shape[1]
        f = min(fx, fy)
        if img.shape[0] < min_size[0] or img.shape[1] < min_size[1]:
            img = cv2.resize(img, dsize = None, fx=f, fy=f)
        elif img.shape[0] > 6000 or img.shape[1] > 4000:
            img = cv2.resize(img, dsize = None, fx=f, fy=f)
    return img

#Функция добавления дефектов (пятен, зарапин)
def defects_image(img, defects_prob = 0.2, balance = 0.5, max_alpha = 0.1):
    if img is not None:
        while True:
            # Добавление дефектов
            x1 = random.randint(0, img.shape[0])
            y1 = random.randint(0, img.shape[1])
            if random.random() >= balance:
                #Добавляем пятно
                size = (int(random.uniform(0.05 * img.shape[0], 0.2 * img.shape[0])),int(random.uniform(0.05 * img.shape[1], 0.2 * img.shape[1])))
                angle = random.uniform(-np.pi / 2, np.pi / 2)
                #Рисуем пятно
                alpha = random.uniform(0, max_alpha)
                img2 = np.ones_like(img) * 127
                img2 = cv2.ellipse(img2, (x1, y1), size, angle, 0, 360, (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), -1)
                #Размытие пятна
                img2 = cv2.GaussianBlur(img2, (5, 5), 0)
                #смешиваем 2 изображения с полупрозрачностью
                img = cv2.addWeighted(img, 1 - alpha, img2, alpha, 0)


            else:
                #Добавляем царапины
                length = random.randint(10, 200)
                angle = random.uniform(-np.pi / 2, np.pi / 2)
                dx = int(length * np.cos(angle))
                dy = int(length * np.sin(angle))
                thick = length = random.randint(1, 5)
                points = [(x1 + i*dx//length, y1 + i*dy//length) for i in range(length)]
                #Рисуем царапины
                img = cv2.polylines(img, [np.array(points)], False, (255, 255, 255), thick) #царапины могут быть только белые


            if random.random() > defects_prob:
                break
    return img

def dataset_prepare(dataset_path, dataset_save_path = "prep_dataset/", blur_prob = 0.2, noise_prob = 0.2):
    #Создаем pipeline обработки изображения
    img_pipeline = []
    double_prob = 0.2
    if not os.path.exists(dataset_save_path):
        os.makedirs(dataset_save_path)
    for filename in os.listdir(dataset_path):
        img = cv2.imread(os.path.join(dataset_path, filename))
        if img is not None:
            doubles = 1
            while True:
                #Нормирование разрешения
                img = resize_image(img)
                img2 = blur_image(img, blur_prob)
                img2 = noise_image(img2, noise_prob)
                img2 = rotation_image(img2)
                img2 = defects_image(img2)
                cv2.imwrite(os.path.join(dataset_save_path, f"{filename[:-4]}_{doubles}.jpg"), img2)

                if random.random() >= double_prob:
                    break
                doubles += 1
            logging.info(f"Processed {filename}, {doubles - 1} duplicates")

if __name__ == "__main__":
    #парсинг параметров
    parser = argparse.ArgumentParser(description='Dataset preparation')
    parser.add_argument('--dataset_path', type=str, default="dataset/", help='Path to dataset')
    parser.add_argument('--dataset_save_path', type=str, default="prep_dataset/", help='Path to save prepared dataset')
    parser.add_argument('--blur_prob', type=float, default=0.2, help='Probability of blur')
    parser.add_argument('--noise_prob', type=float, default=0.2, help='Probability of noise')
    args = parser.parse_args()
    dataset_prepare(args.dataset_path, args.dataset_save_path, args.blur_prob, args.noise_prob)