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

def image_prepare(img, blur_prob = 0.2, noise_prob = 0.2, rotation_prob = 0.2):
    if img is not None:
        # Размытие
        kernel_size = 1
        while True:
            if random.random() >= blur_prob:
                break
            kernel_size += 2

        img = cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)
        # Добавление шумов
        noise_d = 1
        while True:
            if random.random() >= noise_prob:
                break
            noise_d += 1
        noise = np.random.normal(- noise_d // 2, noise_d // 2, img.shape)
        img = cv2.add(img, noise, dtype=cv2.CV_8U)
        # Поворот
        if random.random() >= rotation_prob:
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

def dataset_prepare(dataset_path, dataset_save_path = "prep_dataset/", blur_prob = 0.2, noise_prob = 0.2):
    double_prob = 0.2
    if not os.path.exists(dataset_save_path):
        os.makedirs(dataset_save_path)
    for filename in os.listdir(dataset_path):
        img = cv2.imread(os.path.join(dataset_path, filename))
        if img is not None:
            doubles = 1
            img2 = image_prepare(img, blur_prob, noise_prob)
            cv2.imwrite(os.path.join(dataset_save_path, f"{filename[:-4]}.jpg"), img2)
            while True:
                if random.random() >= double_prob:
                    break
                else:
                    doubles += 1
                    image_prepare(img, blur_prob, noise_prob)
                    cv2.imwrite(os.path.join(dataset_save_path, f"{filename[:-4]}_{doubles}.jpg"), img)
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