import os

def format_size(size_bytes: int) -> str:
    """Форматирует размер в человекочитаемый вид"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}PB"

def format_size_from_str(size_str: str) -> str:
    """Пытается привести строку к числу и форматировать"""
    try:
        return format_size(int(size_str))
    except (ValueError, TypeError):
        return size_str


def normalize_android_path(path: str) -> str:
    """Нормализует путь для Android (Unix-подобный формат)"""
    if not path:
        return "/"
    path = os.path.normpath(path).replace('\\', '/')
    if not path.startswith('/'):
        path = '/' + path
    return path


def parse_size(size_str: str) -> int:
    """Парсит размер из строки вроде '1.2G' в байты"""
    size_str = size_str.strip()
    if not size_str:
        return 0
    units = {'B': 1, 'K': 1024, 'KB': 1024, 'M': 1024**2, 'MB': 1024**2, 'G': 1024**3, 'GB': 1024**3, 'T': 1024**4, 'TB': 1024**4}
    for unit, multiplier in units.items():
        if size_str.upper().endswith(unit.upper()):
            try:
                num_str = size_str[:-len(unit)].strip()
                num = float(num_str)
                return int(num * multiplier)
            except ValueError:
                return 0
    # Если нет единицы, assume bytes
    try:
        return int(float(size_str))
    except ValueError:
        return 0