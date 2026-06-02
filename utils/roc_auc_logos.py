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
    # Удаляем расширения из имен файлов в mapping_df для корректного сравнения
    mapping_df['image_file'] = mapping_df['image_file'].astype(str).str.split('.').str[0]
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

    # Выводим отдельные матрицы ошибок для каждого названия газеты с учетом определения титульных страниц
    newspaper_names = metrics_df['true_group'].unique()
    
    for newspaper in newspaper_names:
        if pd.isna(newspaper):  # Пропускаем NaN значения
            continue
            
        # Фильтруем данные по конкретному названию газеты
        newspaper_data = metrics_df[metrics_df['true_group'] == newspaper]

        # Формируем истинные и предсказанные метки для определения титульных страниц
        # True Positive (TP): верно определенная титульная страница
        # True Negative (TN): верно не определенная титульная страница
        # False Positive (FP): неверно определенная титульная страница (включая определение титульной страницы другой газеты)
        # False Negative (FN): неверно неопределенная титульная страница
        
        y_true_title = []
        y_pred_title = []
        
        for idx, row in newspaper_data.iterrows():
            # Истинная метка: является ли страница титульной (1) или нет (0)
            # Удаляем расширение из названия файла для сравнения
            file_name_without_ext = row['название файла'].split('.')[0]

            matching_rows = mapping_df[mapping_df['image_file'] == file_name_without_ext]

            if len(matching_rows) == 0:
                continue  # Пропускаем, если нет соответствующей строки в mapping_df
            true_is_title = 1 if matching_rows.iloc[0]['page_number'] == 1 else 0
            
            # Предсказанная метка: была ли определена титульная страница
            # Страница считается определенной как титульная (1), если:
            # 1. Степень схожести выше оптимального порога
            # 2. predicted_group совпадает с названием газеты
            pred_is_title = 1 if (row['степень схожести'] >= optimal_threshold and row['predicted_group'] == newspaper) else 0
            
            # Если определяется титульная страница другой газеты (схожесть выше порога, но predicted_group не совпадает с newspaper), то это FP
            if row['степень схожести'] >= optimal_threshold and row['predicted_group'] != 'unsorted' and row['predicted_group'] != newspaper:
                pred_is_title = 1
            
            y_true_title.append(true_is_title)
            y_pred_title.append(pred_is_title)

        # Создаем confusion matrix для определения титульных страниц, только если есть данные
        if len(y_true_title) > 0 and len(y_pred_title) > 0:
            cm_title = confusion_matrix(y_true_title, y_pred_title, labels=[1, 0])
            
            # Визуализируем confusion matrix в виде heatmap для определения титульных страниц данной газеты
            draw_confusion_matrix_heatmap(cm_title, ['Title Page', 'Not Title Page'], f'Confusion Matrix Heatmap for Title Page Detection: {newspaper}')
        else:
            print(f'Недостаточно данных для построения матрицы ошибок для газеты: {newspaper}')