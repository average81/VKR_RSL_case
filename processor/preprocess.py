import cv2

def preprocess_image(img):
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Удаление шума
    img = cv2.GaussianBlur(img, (3, 3), 0)

    # Повышение контраста
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    img = clahe.apply(img)

    # Нормализация
    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

    return img