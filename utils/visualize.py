import cv2
import matplotlib.pyplot as plt
import numpy as np
#Визуализация дефектов
def visualize_defects(image, pascal_voc):
    img2 = image.copy()
    for item in pascal_voc["annotation"]["objects"]:
        xmin = int(item["bndbox"]["xmin"])
        ymax = int(item["bndbox"]["ymax"])
        xmax = int(item["bndbox"]["xmax"])
        ymin = int(item["bndbox"]["ymin"])
        if item["name"] == "ellipse":
            cv2.rectangle(img2, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        else:
            cv2.rectangle(img2, (xmin, ymin), (xmax, ymax), (0, 0, 255), 2)
    return img2

def draw_roc_curve(fpr, tpr, thresholds):
    if fpr is not None and tpr is not None:
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label='ROC curve')
        plt.plot([0, 1], [0, 1], 'k--', label='Random guess')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve')
        plt.legend()
        plt.show()

def draw_confusion_matrix_heatmap(confusion_matrix, labels, title='Confusion Matrix'):
    """
    Отрисовывает confusion matrix в виде heatmap в отдельном окне
    """
    plt.figure(figsize=(10, 8))
    plt.imshow(confusion_matrix, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(labels))
    plt.xticks(tick_marks, labels, rotation=45)
    plt.yticks(tick_marks, labels)
    
    # Добавляем значения в ячейки
    thresh = confusion_matrix.max() / 2.
    for i in range(confusion_matrix.shape[0]):
        for j in range(confusion_matrix.shape[1]):
            plt.text(j, i, format(confusion_matrix[i, j], 'd'),
                    ha="center", va="center",
                    color="white" if confusion_matrix[i, j] > thresh else "black")
    
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()
    plt.show()