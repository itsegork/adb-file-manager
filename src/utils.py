import os
from typing import List


def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_size_from_str(size_str: str) -> str:
    try:
        return format_size(int(size_str))
    except (ValueError, TypeError):
        return size_str


def normalize_android_path(path: str) -> str:
    if not path:
        return "/"
    path = os.path.normpath(path).replace('\\', '/')
    if not path.startswith('/'):
        path = '/' + path
    return path