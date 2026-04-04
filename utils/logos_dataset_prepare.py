import os
import shutil
import argparse
import re

def prepare_dataset(source_dir, output_dir):
    """
    Подготавливает датасет изображений для оценки алгоритмов поиска титульных страниц.
    
    Копирует изображения из исходного датасета, чьи имена оканчиваются на "_1",
    удаляет окончание "_1" и переименовывает файлы с четырехзначными номерами.
    
    :param source_dir: Путь к исходному датасету
    :param output_dir: Путь к выходной папке
    """
    # Создаем выходную директорию, если она не существует
    os.makedirs(output_dir, exist_ok=True)

    # Поддерживаемые форматы изображений
    supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')

    # Получение и сортировка списков изображений
    input_images = [
        f for f in os.listdir(source_dir)
        if f.lower().endswith(supported_formats)
    ]
    # Сортировка с учетом длины имени файла
    max_len = max([len(f) for f in input_images]) if input_images else 0
    input_images_with_key = []
    for f in input_images:
        # Извлекаем номер из названия файла
        num_match = re.search(r"(\d+)", f)
        if num_match:
            prefix = f[:num_match.start()]
            postfix = f[num_match.end():]
            num = num_match.group()
            # Формируем ключ сортировки с дополнением нулями
            sort_key = prefix + "0"*(max_len-len(f)) + num + postfix
        else:
            sort_key = f
        input_images_with_key.append((f, sort_key))
    # Сортируем по ключу
    input_images_with_key.sort(key=lambda x: x[1])
    # Извлекаем отсортированные имена файлов
    filtered_files = [f for f, key in input_images_with_key]
    filtered_files = [f for f in filtered_files if '-' in f and f.split('-')[-1].split('.')[0] == '1']
    # Копируем и переименовываем файлы
    for i, filename in enumerate(filtered_files, 1):
        # Разделяем имя файла и расширение
        name_parts = filename.split('.')
        extension = name_parts[-1]  # Сохраняем оригинальное расширение
        name_without_ext = '.'.join(name_parts[:-1])
        
        # Удаляем окончание "-1" из имени файла
        name_without_suffix_temp = name_without_ext.split('-')[0].join(name_without_ext.split('-')[:-1])
        
        # Удаляем число в конце имени файла с помощью регулярного выражения
        name_without_suffix = re.sub(r'\d+$', '', name_without_suffix_temp)
        
        # Формируем новое имя с четырехзначным номером и сохраняем оригинальное расширение
        new_filename = f"{name_without_suffix}{i:04d}.{extension}"
        
        # Полные пути к файлам
        source_path = os.path.join(source_dir, filename)
        output_path = os.path.join(output_dir, new_filename)
        
        # Копируем файл
        shutil.copy2(source_path, output_path)
        
        print(f"Скопировано: {filename} -> {new_filename}")
    
    print(f"\nГотово! Скопировано {len(filtered_files)} файлов.")


def main():
    parser = argparse.ArgumentParser(description='Подготовка датасета изображений для оценки алгоритмов поиска титульных страниц')
    parser.add_argument('source_dir', help='Путь к исходному датасету')
    parser.add_argument('output_dir', help='Путь к выходной папке')
    
    args = parser.parse_args()
    
    prepare_dataset(args.source_dir, args.output_dir)


if __name__ == "__main__":
    main()