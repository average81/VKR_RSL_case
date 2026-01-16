from visualize import draw_roc_curve
import utils
import argparse
import pandas as pd

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--table_path', type=str, default='./output/metrics.csv', help='table path')
    df = pd.read_csv(parser.parse_args().table_path)
    # Создаем колонку true_dupl
    df['true_dupl'] = df['image'].apply(lambda x: x.split('-')[1].split('.')[0] != '1')
    df['true_dupl'] = df['true_dupl'].astype(int)
    fpr, tpr, thresholds = utils.get_roc_auc_curve_data(df)
    draw_roc_curve(fpr, tpr, thresholds)
    max_th = df[df['true_dupl'] == 1]['score'].min()
    min_th = df[df['true_dupl'] == 0]['score'].max()
    tpmean = df[df['true_dupl'] == 1]['score'].mean()
    fpmean = df[df['true_dupl'] == 0]['score'].mean()
    print(f'max_th: {max_th}, min_th: {min_th}')
    print(f"Threshold difference: {max_th - min_th}")
    print(f'tpmean: {tpmean}, fpmean: {fpmean}')
    print(f'tpmean - fpmean: {tpmean - fpmean}')