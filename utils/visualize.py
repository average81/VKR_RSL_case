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

def draw_clusters_bar_chart(df, duplicate_threshold=0.7, num_bins=20):
    """
    Отрисовывает столбчатую диаграмму распределения числа изображений (дубликатов и уникальных)
    по диапазонам схожести.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame с колонками 'image' и 'score'
    duplicate_threshold : float
        Пороговое значение для определения дубликата
    num_bins : int
        Количество баров на графике (по умолчанию 20, каждый покрывает 5% диапазона)
    """
    # Создаем колонку true_dupl на основе имени файла (как в roc_auc_dupl.py)
    df = df.copy()
    df['true_dupl'] = df['image'].apply(lambda x: x.split('-')[1].split('.')[0] != '1')
    df['true_dupl'] = df['true_dupl'].astype(int)
    
    # Делим диапазон [0, 1] на num_bins бинов
    bin_edges = np.linspace(0, 1, num_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Подсчитываем количество дубликатов и уникальных в каждом бине
    dup_counts = []
    unique_counts = []
    
    for i in range(num_bins):
        # Создаем бин-маску
        mask_dup = (df['score'] >= bin_edges[i]) & (df['score'] < bin_edges[i+1])
        
        # Для последнего бина добавляем значения, равные точно 1.0
        if i == num_bins - 1:
            mask_dup = mask_dup | (df['score'] == 1.0)
        
        dup_count = len(df[(df['true_dupl'] == 1) & mask_dup])
        unique_count = len(df[(df['true_dupl'] == 0) & mask_dup])
        
        dup_counts.append(dup_count)
        unique_counts.append(unique_count)
    
    # Создаем график
    plt.figure(figsize=(8, 8))
    
    width = 0.04  # Ширина столбцов
    
    # Столбцы для дубликатов
    plt.bar(bin_centers - width/2, dup_counts, width, color='red', alpha=0.7, 
            label=f'Дубликаты (true_dupl=1)', edgecolor='black')
    
    # Столбцы для уникальных
    plt.bar(bin_centers + width/2, unique_counts, width, color='blue', alpha=0.7, 
            label=f'Уникальные (true_dupl=0)', edgecolor='black')
    
    # Добавляем вертикальную линию порога
    plt.axvline(x=duplicate_threshold, color='green', linestyle='--', linewidth=2, 
                label=f'Оптимальный порог ({duplicate_threshold})')
    
    # Настройки графика
    plt.xlabel('Степень сходства', fontsize=12)
    plt.ylabel('Число изображений', fontsize=12)
    plt.title(f'Распределение дубликатов и уникальных изображений\n'
              f'(Оптимальный порог: {duplicate_threshold}', fontsize=14)
    plt.legend(loc='best')
    plt.xlim(0, 1)
    plt.xticks(bin_edges, rotation=45)
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
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
