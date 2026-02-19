#!/usr/bin/env python
"""
Скрипт для конвертации PDF-файла в набор изображений.

Каждая страница сохраняется как PNG-файл с именем формата "rollXXXX.png",
где XXXX — сквозная нумерация с ведущими нулями (начиная с 0001).
"""

import sys
import os
import csv
import fitz  # PyMuPDF


def pdf_to_images(input_path, output_dir, csv_path=None):
    """
    Конвертирует PDF-файл или все PDF-файлы из директории в набор изображений.

    :param input_path: Путь к PDF-файлу или к директории с PDF-файлами
    :param output_dir: Путь к выходной директории
    """
    # Проверка существования входного пути
    if not os.path.exists(input_path):
        print(f"Ошибка: Путь '{input_path}' не существует.")
        sys.exit(1)

    # Создание выходной директории, если она не существует
    os.makedirs(output_dir, exist_ok=True)

    # Проверка, является ли путь файлом или директорией
    if os.path.isfile(input_path):
        pdf_files = [input_path]
    elif os.path.isdir(input_path):
        pdf_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print(f"Ошибка: В директории '{input_path}' не найдено PDF-файлов.")
            sys.exit(1)
    else:
        print(f"Ошибка: Путь '{input_path}' не является ни файлом, ни директорией.")
        sys.exit(1)

    # Получаем текущее количество файлов в выходной директории для продолжения нумерации
    existing_files = [f for f in os.listdir(output_dir) if f.startswith("roll") and f.endswith(".png")]
    roll_numbers = []
    for f in existing_files:
        try:
            # Извлекаем номер из имени файла вида roll0001.png
            num_part = f[4:-4]  # убираем "roll" и ".png"
            if num_part.isdigit():
                roll_numbers.append(int(num_part))
        except:
            continue
    
    # Определяем начальный номер для сквозной нумерации
    next_roll_number = max(roll_numbers) + 1 if roll_numbers else 1

    # Открытие CSV-файла для записи, если указан путь
    csv_file = None
    csv_writer = None
    if csv_path:
        csv_file = open(csv_path, 'w', newline='', encoding='utf-8')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['image_file', 'source_pdf', 'page_number'])

    # Обработка каждого PDF-файла
    for pdf_path in pdf_files:
        try:
            print(f"Обработка файла: {pdf_path}")
            document = fitz.open(pdf_path)
            
            for page_num in range(len(document)):
                page = document.load_page(page_num)
                # Определение требуемого разрешения
                mat = fitz.Matrix(1, 1)  # Базовая матрица
                rect = page.rect
                width, height = rect.width, rect.height

                # Определение текущего минимума и максимума
                min_dim = min(width, height)
                max_dim = max(width, height)

                # Масштабирование, чтобы меньшая сторона была не менее 2000, а большая — не менее 3000
                scale_x = 2000 / min_dim if min_dim < 2000 else (3000 / max_dim if max_dim < 3000 else 1)
                scale_y = scale_x  # Сохраняем пропорции

                mat = fitz.Matrix(scale_x, scale_y)
                pix = page.get_pixmap(matrix=mat)
                # Формирование имени файла с ведущими нулями и сквозной нумерацией
                image_filename = f"roll{next_roll_number:04d}.png"
                output_path = os.path.join(output_dir, image_filename)
                pix.save(output_path)
                print(f"Сохранено: {output_path}")
                
                # Запись в CSV, если файл открыт
                if csv_writer:
                    # Используем только имя PDF-файла, без полного пути
                    pdf_filename = os.path.basename(pdf_path)
                    csv_writer.writerow([image_filename, pdf_filename, page_num + 1])
                
                next_roll_number += 1
            
            document.close()
            
        except Exception as e:
            print(f"Ошибка при обработке файла '{pdf_path}': {e}")
            continue  # Переход к следующему файлу при ошибке
    
    # Закрытие CSV-файла, если он был открыт
    if csv_file:
        csv_file.close()


def main():
    if len(sys.argv) < 3:
        print("Использование: python pdf_to_images.py <путь_к_pdf_или_директории> <путь_к_директории_вывода> [путь_к_csv]")
        print("Пример: python pdf_to_images.py ./pdfs ./images mapping.csv")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    csv_path = sys.argv[3] if len(sys.argv) > 3 else None

    pdf_to_images(input_path, output_dir, csv_path)


if __name__ == "__main__":
    main()