"""
Скрипт для генерации иконки приложения app.ico
Создает желтый равносторонний треугольник на зеленом фоне.
"""

from PIL import Image, ImageDraw
import math


def create_triangle_icon(size):
    """
    Создать иконку с треугольником заданного размера.
    
    Args:
        size: Размер изображения (width, height)
        
    Returns:
        PIL.Image: Изображение иконки
    """
    # Создаем изображение с зеленым фоном
    img = Image.new('RGB', size, color='#228B22')  # Зеленый цвет (Forest Green)
    draw = ImageDraw.Draw(img)
    
    width, height = size
    
    # Вычисляем координаты для равностороннего треугольника
    # Центрируем треугольник на изображении
    center_x = width / 2
    center_y = height / 2
    
    # Радиус окружности, описанной вокруг треугольника
    # Используем 80% от меньшей стороны, чтобы треугольник не касался краев
    radius = min(width, height) * 0.4
    
    # Вычисляем координаты вершин равностороннего треугольника
    # Первая вершина вверху (0 градусов от вертикали)
    # Углы между вершинами: 120 градусов (360/3)
    vertices = []
    for i in range(3):
        # Угол в радианах: начинаем с -90 градусов (вверх), затем добавляем 120 градусов
        angle = math.radians(-90 + i * 120)
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        vertices.append((x, y))
    
    # Рисуем желтый треугольник
    yellow_color = '#FFD700'  # Золотисто-желтый (Gold)
    draw.polygon(vertices, fill=yellow_color, outline=yellow_color)
    
    return img


def create_ico_file(output_path='app.ico', sizes=None):
    """
    Создать .ico файл с иконкой в разных размерах.
    
    Args:
        output_path: Путь для сохранения .ico файла
        sizes: Список размеров для иконки (по умолчанию: стандартные размеры)
    """
    if sizes is None:
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    
    # Создаем изображения для каждого размера
    images = []
    for size in sizes:
        print(f"Создание иконки размера {size[0]}x{size[1]}...")
        img = create_triangle_icon(size)
        images.append(img)
    
    # Сохраняем все изображения в один .ico файл
    print(f"Сохранение иконки в файл {output_path}...")
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:]
    )
    
    print(f"Иконка успешно создана: {output_path}")
    print(f"Размеры иконки: {', '.join([f'{w}x{h}' for w, h in sizes])}")


if __name__ == '__main__':
    import sys
    
    # Путь для сохранения иконки (можно указать как аргумент командной строки)
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'app.ico'
    
    try:
        create_ico_file(output_file)
    except Exception as e:
        print(f"Ошибка при создании иконки: {e}")
        sys.exit(1)
