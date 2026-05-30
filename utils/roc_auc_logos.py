from visualize import draw_roc_curve, draw_confusion_matrix_heatmap
import utils
import argparse
import pandas as pd
import numpy as np
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt

def get_true_group_name(image_file, mapping_df):
    """
    Получает истинное название группы (газеты/журнала) для изображения из mapping.csv
    """
    row = mapping_df[mapping_df['image_file'].str.split('.').str[0] == image_file.split('.')[0]]
    if len(row) > 0:
        return row.iloc[0]['name']
    return None

def get_predicted_group_name(logo_name):
    """
    Извлекает название группы из строки logo_name в формате "папка/файл_логотипа"
    """
    if '/' in logo_name:
        return logo_name.split('/')[0]
    return logo_name

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrics_path', type=str, required=True, help='Путь к файлу metrics.csv')
    parser.add_argument('--mapping_path', type=str, required=True, help='Путь к файлу mapping.csv')
    args = parser.parse_args()
    
    # Загружаем данные
    metrics_df = pd.read_csv(args.metrics_path)
    mapping_df = pd.read_csv(args.mapping_path)
    
    # Создаем колонку true_group с истинными названиями групп
    metrics_df['true_group'] = metrics_df['название файла'].apply(lambda x: get_true_group_name(x, mapping_df))
    
    # Сортируем DataFrame по названию файла (предполагаем, что файлы обрабатываются в порядке имен)
    #metrics_df = metrics_df.sort_values('название файла').reset_index(drop=True)
    
    # Получаем данные для ROC кривой
    fpr, tpr, thresholds = utils.get_roc_auc_curve_data(pd.DataFrame({'score': metrics_df['степень схожести'].values, 'true_dupl': [0]*len(metrics_df)}))
    
    # Для каждой точки ROC кривой (порога) вычисляем предсказания
    compare_pred = np.zeros([len(thresholds), mapping_df.shape[0],4]) # TP,TN,FP,FN

    for tn,threshold in enumerate(thresholds):
        current_group = None
        predicted_groups = []
        
        for idx, row in metrics_df.iterrows():
            similarity = row['степень схожести']
            logo_name = row['название логотипа']

            # Если степень схожести превышает текущий порог ROC кривой
            if similarity >= threshold:
                current_group = get_predicted_group_name(logo_name)
                if current_group == metrics_df['true_group'][idx] and mapping_df['page_number'][idx] == 1:
                    compare_pred[tn,idx,0] = 1  #TP
                else:
                    compare_pred[tn,idx,2] = 1  #FP
            else:
                if mapping_df['page_number'][idx] != 1:
                    compare_pred[tn,idx,1] = 1  #TN
                else:
                    compare_pred[tn,idx,3] = 1  #FN
    compare_pred = compare_pred.sum(axis=1)
    # Извлекаем TP, TN, FP, FN из compare_pred
    TP = compare_pred[:, 0]
    TN = compare_pred[:, 1] 
    FP = compare_pred[:, 2]
    FN = compare_pred[:, 3]
    
    # Вычисляем TPR и FPR для ROC кривой
    TPR = TP / (TP + FN)  # Sensitivity, Recall
    FPR = FP / (FP + TN)  # 1 - Specificity
    
    # Заменяем NaN значения (деление на ноль)
    TPR = np.nan_to_num(TPR)
    FPR = np.nan_to_num(FPR)
    
    # Сортируем точки по FPR для корректного построения кривой
    sort_indices = np.argsort(FPR)
    FPR_sorted = FPR[sort_indices]
    TPR_sorted = TPR[sort_indices]
    thresholds_sorted = thresholds[sort_indices]
    
    # Добавляем точку (0,0) в начало
    FPR_sorted = np.concatenate([[0], FPR_sorted])
    TPR_sorted = np.concatenate([[0], TPR_sorted])
    thresholds_sorted = np.concatenate([[1], thresholds_sorted])
    
    # Рисуем ROC кривую
    draw_roc_curve(FPR_sorted, TPR_sorted, thresholds_sorted)
    
    # Вычисляем ROC AUC
    from sklearn.metrics import auc
    roc_auc = auc(FPR_sorted, TPR_sorted)
    
    # Вычисляем другие метрики для каждого порога
    accuracy = (TP + TN) / (TP + TN + FP + FN)
    precision = TP / (TP + FP)
    recall = TP / (TP + FN)
    f1_score = 2 * precision * recall / (precision + recall)
    
    # Заменяем NaN значения
    accuracy = np.nan_to_num(accuracy)
    precision = np.nan_to_num(precision)
    recall = np.nan_to_num(recall)
    f1_score = np.nan_to_num(f1_score)
    
    # Находим оптимальный порог по F1-мере
    optimal_idx = np.argmax(f1_score)
    optimal_threshold = thresholds[optimal_idx]
    
    print(f'Optimal threshold: {optimal_threshold:.4f}')
    print(f'Max F1-score: {f1_score[optimal_idx]:.4f}')
    print(f'Precision at optimal threshold: {precision[optimal_idx]:.4f}')
    print(f'Recall at optimal threshold: {recall[optimal_idx]:.4f}')
    print(f'Accuracy at optimal threshold: {accuracy[optimal_idx]:.4f}')
    print(f'ROC AUC: {roc_auc:.4f}')

    # Определяем уникальные названия групп из mapping_df и предсказанных значений
    unique_true_groups = sorted(mapping_df['name'].unique())
    unique_predicted_groups = sorted(metrics_df['название логотипа'].apply(get_predicted_group_name).unique())
    all_groups = sorted(set(unique_true_groups) | set(unique_predicted_groups))
    
    # Формируем предсказанные группы с учетом правила последовательного присвоения
    predicted_groups = []
    current_group = 'unsorted'
    
    for idx, row in metrics_df.iterrows():
        similarity = row['степень схожести']
        
        if similarity >= optimal_threshold:
            current_group = get_predicted_group_name(row['название логотипа'])
        
        predicted_groups.append(current_group)
    
    # Добавляем предсказанные группы в DataFrame
    metrics_df['predicted_group'] = predicted_groups
    
    # Формируем матрицу ошибок (confusion matrix) по группам
    y_true = metrics_df['true_group']
    y_pred = metrics_df['predicted_group']
    
    # Создаем confusion matrix с учетом всех возможных групп
    cm = confusion_matrix(y_true, y_pred, labels=all_groups + ['unsorted'])
    
    # Визуализируем confusion matrix в виде heatmap
    draw_confusion_matrix_heatmap(cm, all_groups + ['unsorted'], 'Confusion Matrix Heatmap for Newspaper/Journal Groups')