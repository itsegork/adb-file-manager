import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
from pathlib import Path
import re
from datetime import datetime

class ADBFileManager:
    def __init__(self, root):
        self.root = root
        self.root.title("ADB File Manager")
        self.root.geometry("1000x700")
        
        self.device = None
        self.current_path = "/storage/emulated/0"
        self.local_current_path = str(Path.home())
        
        # Таймеры для автообновления
        self.local_update_timer = None
        self.android_update_timer = None
        
        # Проверка наличия ADB
        if not self.check_adb():
            messagebox.showerror("Ошибка", "ADB не найден! Установите Android Debug Bridge")
            self.root.quit()
            return
        
        self.setup_ui()
        self.connect_device()
        
        # Запуск автообновления
        self.schedule_local_update()
        self.schedule_android_update()
    
    def check_adb(self):
        """Проверка наличия ADB в системе"""
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True)
            return True
        except:
            return False
    
    def setup_ui(self):
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Информация об устройстве
        self.device_label = ttk.Label(main_frame, text="Устройство: не подключено")
        self.device_label.pack(fill=tk.X, pady=(0, 10))
        
        # Фрейм для двух панелей
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Левая панель - локальные файлы
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Локальные файлы (компьютер)", font=('Arial', 10, 'bold')).pack(pady=(0, 5))
        
        # Навигация для локальных файлов
        local_nav = ttk.Frame(left_frame)
        local_nav.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(local_nav, text="🔼 Наверх", command=self.local_navigate_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_nav, text="🏠 Домой", command=self.local_go_home).pack(side=tk.LEFT, padx=(0, 5))
        self.local_path_label = ttk.Label(local_nav, text=self.local_current_path, wraplength=300)
        self.local_path_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Дерево локальных файлов
        self.create_local_file_tree(left_frame)
        
        # Правая панель - Android файлы
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        ttk.Label(right_frame, text="Файлы Android", font=('Arial', 10, 'bold')).pack(pady=(0, 5))
        
        # Навигация для Android файлов
        android_nav = ttk.Frame(right_frame)
        android_nav.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(android_nav, text="🔼 Наверх", command=self.android_navigate_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(android_nav, text="🏠 Внутренняя память", command=self.android_go_home).pack(side=tk.LEFT, padx=(0, 5))
        
        self.android_path_label = ttk.Label(android_nav, text=self.current_path, wraplength=300)
        self.android_path_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Дерево Android файлов
        self.create_android_file_tree(right_frame)
        
        # Фрейм для кнопок действий
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(action_frame, text="📤 Отправить на Android →", 
                  command=self.send_selected_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="← 📥 Скачать с Android", 
                  command=self.pull_selected_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🖥️ Scrcpy", 
                  command=self.start_scrcpy).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="📁 Создать папку на Android", 
                  command=self.create_android_folder).pack(side=tk.LEFT, padx=5)
        
        # Прогресс бар
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        
        self.progress_label = ttk.Label(self.progress_frame, text="")
        
        # Лог операций
        log_frame = ttk.LabelFrame(main_frame, text="Лог операций", padding="5")
        log_frame.pack(fill=tk.X, pady=(10, 0))
        
        log_scrollbar = ttk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=5, yscrollcommand=log_scrollbar.set)
        self.log_text.pack(fill=tk.X, expand=True)
        
        log_scrollbar.config(command=self.log_text.yview)
    
    def create_local_file_tree(self, parent):
        """Создание дерева локальных файлов"""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.local_tree = ttk.Treeview(tree_frame, columns=("size", "modified"), 
                                       show="tree", yscrollcommand=scrollbar.set)
        self.local_tree.pack(fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.local_tree.yview)
        
        self.local_tree.column("#0", width=300)
        self.local_tree.column("size", width=100, anchor="e")
        self.local_tree.column("modified", width=150)
        
        self.local_tree.heading("#0", text="Имя")
        self.local_tree.heading("size", text="Размер")
        self.local_tree.heading("modified", text="Дата изменения")
        
        self.local_tree.bind("<Double-1>", self.on_local_double_click)
        self.local_tree.bind("<Button-3>", self.show_local_context_menu)
        self.local_tree.bind("<<TreeviewSelect>>", self.on_local_select)
        
        # Контекстное меню для локальных файлов (будет обновляться динамически)
        self.local_context_menu = tk.Menu(self.root, tearoff=0)
        
        self.load_local_files()
    
    def create_android_file_tree(self, parent):
        """Создание дерева Android файлов"""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.android_tree = ttk.Treeview(tree_frame, columns=("size", "permissions"), 
                                         show="tree", yscrollcommand=scrollbar.set)
        self.android_tree.pack(fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.android_tree.yview)
        
        self.android_tree.column("#0", width=300)
        self.android_tree.column("size", width=100, anchor="e")
        self.android_tree.column("permissions", width=100)
        
        self.android_tree.heading("#0", text="Имя")
        self.android_tree.heading("size", text="Размер")
        self.android_tree.heading("permissions", text="Права")
        
        self.android_tree.bind("<Double-1>", self.on_android_double_click)
        self.android_tree.bind("<Button-3>", self.show_android_context_menu)
        self.android_tree.bind("<<TreeviewSelect>>", self.on_android_select)
        
        # Контекстное меню для Android файлов (будет обновляться динамически)
        self.android_context_menu = tk.Menu(self.root, tearoff=0)
    
    def schedule_local_update(self):
        """Планирование автообновления локальных файлов"""
        self.load_local_files()
        self.local_update_timer = threading.Timer(5.0, self.schedule_local_update)
        self.local_update_timer.daemon = True
        self.local_update_timer.start()
    
    def schedule_android_update(self):
        """Планирование автообновления Android файлов"""
        if self.device:
            self.refresh_android_files()
        self.android_update_timer = threading.Timer(5.0, self.schedule_android_update)
        self.android_update_timer.daemon = True
        self.android_update_timer.start()
    
    def load_local_files(self, path=None):
        """Загрузка локальных файлов"""
        if path:
            self.local_current_path = path
        
        # Очистка дерева
        for item in self.local_tree.get_children():
            self.local_tree.delete(item)
        
        try:
            # Добавляем ".." для навигации вверх
            if self.local_current_path != "/" and os.path.exists(os.path.dirname(self.local_current_path)):
                self.local_tree.insert("", 0, text="📁 ..", values=("", ""), tags=("parent", "dir"))
            
            # Загружаем файлы
            items = []
            for item in os.listdir(self.local_current_path):
                full_path = os.path.join(self.local_current_path, item)
                try:
                    stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)
                    
                    if is_dir:
                        display_name = f"📁 {item}"
                        size = ""
                    else:
                        display_name = f"📄 {item}"
                        size = self.format_size(stat.st_size)
                    
                    # Форматирование даты
                    mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    
                    items.append((display_name, size, mod_time, full_path, is_dir))
                except:
                    continue
            
            # Сортируем: сначала папки, потом файлы
            items.sort(key=lambda x: (not x[4], x[0].lower()))
            
            for display_name, size, mod_time, full_path, is_dir in items:
                tag = "dir" if is_dir else "file"
                self.local_tree.insert("", tk.END, text=display_name, 
                                     values=(size, mod_time), tags=(tag, full_path))
            
            self.local_path_label.config(text=self.local_current_path)
            
        except Exception as e:
            self.log(f"Ошибка при загрузке локальных файлов: {e}")
    
    def refresh_android_files(self):
        """Обновление списка Android файлов"""
        if self.device:
            threading.Thread(target=self._load_android_files, daemon=True).start()
    
    def _load_android_files(self):
        """Фоновая загрузка Android файлов"""
        try:
            # Очистка дерева в главном потоке
            self.root.after(0, lambda: self.android_tree.delete(*self.android_tree.get_children()))
            
            # Получение списка файлов с детальной информацией
            command = ["adb", "-s", self.device, "shell", "ls", "-la", self.current_path]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                self.root.after(0, lambda: self.log(f"Ошибка при чтении директории: {result.stderr}"))
                return
            
            lines = result.stdout.strip().split("\n")
            items = []
            
            # Паттерн для парсинга ls -la
            pattern = r'^([drwxlst-]{10})\s+\d+\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.+)$'
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("total"):
                    continue
                
                # Пробуем разные паттерны для разных версий ls
                match = re.match(pattern, line)
                if match:
                    permissions = match.group(1)
                    size = match.group(4)
                    name = match.group(7)
                else:
                    # Упрощенный парсинг
                    parts = line.split()
                    if len(parts) >= 8:
                        permissions = parts[0]
                        # Пропускаем некоторые поля
                        idx = 1
                        while idx < len(parts) and not parts[idx].isdigit():
                            idx += 1
                        if idx < len(parts):
                            size = parts[idx]
                            # Ищем имя
                            name_parts = parts[idx+1:] if idx+1 < len(parts) else []
                            if name_parts and ':' in name_parts[0]:
                                name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                            else:
                                name = ' '.join(name_parts)
                        else:
                            continue
                    else:
                        continue
                
                if not name or name in ['.', '..']:
                    continue
                
                # Определение типа
                is_dir = permissions.startswith('d')
                
                # Формируем отображаемое имя
                if is_dir:
                    display_name = f"📁 {name}"
                else:
                    display_name = f"📄 {name}"
                
                # Форматируем размер
                try:
                    size_val = int(size)
                    size_str = self.format_size(size_val)
                except:
                    size_str = size
                
                items.append((display_name, size_str, permissions, name, is_dir))
            
            # Сортируем: сначала папки, потом файлы
            items.sort(key=lambda x: (not x[4], x[0].lower()))
            
            # Добавляем элементы в дерево
            for display_name, size_str, permissions, name, is_dir in items:
                tag = "dir" if is_dir else "file"
                self.root.after(0, lambda dn=display_name, sz=size_str, perm=permissions, nm=name, tg=tag: 
                              self.android_tree.insert("", tk.END, text=dn, 
                                                       values=(sz, perm), 
                                                       tags=(tg, nm)))
            
            self.root.after(0, lambda: self.android_path_label.config(text=self.current_path))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Ошибка при загрузке Android файлов: {e}"))
    
    def on_local_select(self, event):
        """Обработка выбора элемента в локальном дереве"""
        # Обновляем контекстное меню при изменении выбора
        pass
    
    def on_android_select(self, event):
        """Обработка выбора элемента в Android дереве"""
        # Обновляем контекстное меню при изменении выбора
        pass
    
    def on_local_double_click(self, event):
        """Обработка двойного клика по локальному файлу"""
        selection = self.local_tree.selection()
        if not selection:
            return
        
        item = self.local_tree.item(selection[0])
        text = item['text']
        tags = item.get('tags', [])
        
        if text == "📁 ..":
            self.local_navigate_up()
        elif "dir" in tags and len(tags) > 1:
            full_path = tags[1]
            if os.path.isdir(full_path):
                self.load_local_files(full_path)
    
    def on_android_double_click(self, event):
        """Обработка двойного клика по Android файлу"""
        if not self.device:
            return
        
        selection = self.android_tree.selection()
        if not selection:
            return
        
        item = self.android_tree.item(selection[0])
        text = item['text']
        tags = item.get('tags', [])
        
        if "dir" in tags and len(tags) > 1:
            folder_name = tags[1]
            # Формируем новый путь
            if self.current_path.endswith('/'):
                new_path = f"{self.current_path}{folder_name}"
            else:
                new_path = f"{self.current_path}/{folder_name}"
            
            self.current_path = new_path
            self.refresh_android_files()
    
    def local_navigate_up(self):
        """Переход на уровень вверх в локальной файловой системе"""
        parent = os.path.dirname(self.local_current_path)
        if parent and parent != self.local_current_path:
            self.load_local_files(parent)
    
    def local_go_home(self):
        """Переход в домашнюю папку"""
        self.load_local_files(str(Path.home()))
    
    def android_navigate_up(self):
        """Переход на уровень вверх в Android файловой системе"""
        if self.current_path == "/storage/emulated/0":
            messagebox.showwarning(
                "Ограничение доступа", 
                "Google идет по пути ограничения Android.\n"
                "Получить доступ к корневой папке невозможно :("
            )
            return
        if self.current_path != "/":
            parent = os.path.dirname(self.current_path.rstrip("/"))
            if not parent:
                parent = "/"
            self.current_path = parent
            self.refresh_android_files()
    
    def android_go_home(self):
        """Переход во внутреннюю память Android"""
        self.current_path = "/storage/emulated/0"
        self.refresh_android_files()
    
    def show_local_context_menu(self, event):
        """Показ контекстного меню для локальных файлов"""
        item = self.local_tree.identify_row(event.y)
        if item:
            self.local_tree.selection_set(item)
            
            # Очищаем меню
            self.local_context_menu.delete(0, tk.END)
            
            # Получаем информацию о выбранном элементе
            item_data = self.local_tree.item(item)
            tags = item_data.get('tags', [])
            text = item_data['text']
            
            if text == "📁 ..":
                # Для "наверх" только базовые действия
                self.local_context_menu.add_command(label="📂 Открыть", command=self.local_navigate_up)
                self.local_context_menu.add_separator()
                self.local_context_menu.add_command(label="🔄 Обновить", command=lambda: self.load_local_files())
            else:
                # Общие действия для всех
                self.local_context_menu.add_command(label="📂 Открыть", 
                                                  command=self.open_local_folder)
                
                # Действия для папок
                if "dir" in tags:
                    self.local_context_menu.add_command(label="📤 Отправить папку на Android", 
                                                      command=self.send_selected_files)
                else:
                    # Действия для файлов
                    self.local_context_menu.add_command(label="📤 Отправить файл на Android", 
                                                      command=self.send_selected_files)
                
                self.local_context_menu.add_separator()
                
                # Удаление для всех (кроме "..")
                self.local_context_menu.add_command(label="🗑️ Удалить", 
                                                  command=self.delete_local_files)
                
                self.local_context_menu.add_separator()
                self.local_context_menu.add_command(label="🔄 Обновить", 
                                                  command=lambda: self.load_local_files())
            
            self.local_context_menu.post(event.x_root, event.y_root)
    
    def show_android_context_menu(self, event):
        """Показ контекстного меню для Android файлов"""
        item = self.android_tree.identify_row(event.y)
        if item and self.device:
            self.android_tree.selection_set(item)
            
            # Очищаем меню
            self.android_context_menu.delete(0, tk.END)
            
            # Получаем информацию о выбранном элементе
            item_data = self.android_tree.item(item)
            tags = item_data.get('tags', [])
            
            # Общие действия для всех
            if "dir" in tags:
                self.android_context_menu.add_command(label="📂 Открыть папку", 
                                                    command=self.open_android_folder)
                self.android_context_menu.add_command(label="📥 Скачать папку на компьютер", 
                                                    command=self.pull_selected_files)
            else:
                self.android_context_menu.add_command(label="📥 Скачать файл на компьютер", 
                                                    command=self.pull_selected_files)
            
            self.android_context_menu.add_separator()
            
            # Удаление для всех
            self.android_context_menu.add_command(label="🗑️ Удалить", 
                                                command=self.delete_selected_files)
            
            self.android_context_menu.add_separator()
            self.android_context_menu.add_command(label="📁 Создать папку здесь", 
                                                command=self.create_android_folder)
            
            self.android_context_menu.post(event.x_root, event.y_root)
    
    def open_local_folder(self):
        """Открыть выбранную локальную папку"""
        selection = self.local_tree.selection()
        if selection:
            item = self.local_tree.item(selection[0])
            tags = item.get('tags', [])
            if "dir" in tags and len(tags) > 1 and item['text'] != "📁 ..":
                folder_path = tags[1]
                if os.path.isdir(folder_path):
                    self.load_local_files(folder_path)
    
    def open_android_folder(self):
        """Открыть выбранную Android папку"""
        selection = self.android_tree.selection()
        if selection and self.device:
            item = self.android_tree.item(selection[0])
            tags = item.get('tags', [])
            if "dir" in tags and len(tags) > 1:
                folder_name = tags[1]
                if self.current_path.endswith('/'):
                    new_path = f"{self.current_path}{folder_name}"
                else:
                    new_path = f"{self.current_path}/{folder_name}"
                
                self.current_path = new_path
                self.refresh_android_files()
    
    def delete_local_files(self):
        """Удаление выбранных локальных файлов"""
        files = self.get_selected_local_paths()
        if not files:
            return
        
        if messagebox.askyesno("Подтверждение", f"Удалить {len(files)} файл(ов) с компьютера?\nЭто действие нельзя отменить!"):
            for file in files:
                try:
                    if os.path.isfile(file):
                        os.remove(file)
                        self.log(f"✓ Файл {os.path.basename(file)} удалён")
                    elif os.path.isdir(file):
                        import shutil
                        shutil.rmtree(file)
                        self.log(f"✓ Папка {os.path.basename(file)} удалена")
                except Exception as e:
                    self.log(f"✗ Ошибка при удалении {os.path.basename(file)}: {e}")
            
            # Обновляем список после удаления
            self.load_local_files()
    
    def create_android_folder(self):
        """Создание новой папки на Android"""
        if not self.device:
            messagebox.showerror("Ошибка", "Нет подключенного устройства")
            return
        
        # Диалог для ввода имени папки
        dialog = tk.Toplevel(self.root)
        dialog.title("Создание папки")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Создать папку в:\n{self.current_path}").pack(pady=10)
        
        frame = ttk.Frame(dialog)
        frame.pack(pady=10)
        
        ttk.Label(frame, text="Имя папки:").pack(side=tk.LEFT, padx=(0, 5))
        folder_name = ttk.Entry(frame, width=30)
        folder_name.pack(side=tk.LEFT)
        folder_name.focus()
        
        def create():
            name = folder_name.get().strip()
            if name:
                dialog.destroy()
                threading.Thread(target=self._create_folder, args=(name,), daemon=True).start()
            else:
                messagebox.showwarning("Предупреждение", "Введите имя папки")
        
        ttk.Button(dialog, text="Создать", command=create).pack(pady=10)
    
    def _create_folder(self, folder_name):
        """Фоновое создание папки"""
        try:
            if self.current_path.endswith('/'):
                folder_path = f"{self.current_path}{folder_name}"
            else:
                folder_path = f"{self.current_path}/{folder_name}"
            
            command = ["adb", "-s", self.device, "shell", "mkdir", "-p", folder_path]
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.root.after(0, lambda: self.log(f"✓ Папка {folder_name} создана"))
            else:
                self.root.after(0, lambda: self.log(f"✗ Ошибка при создании папки: {result.stderr}"))
                
        except Exception as e:
            self.root.after(0, lambda: self.log(f"✗ Ошибка при создании папки: {e}"))
    
    def get_selected_local_paths(self):
        """Получение путей выбранных локальных файлов"""
        paths = []
        for item in self.local_tree.selection():
            item_data = self.local_tree.item(item)
            if item_data['text'] != "📁 ..":  # Игнорируем ".."
                if item_data['tags'] and len(item_data['tags']) > 1:
                    path = item_data['tags'][1]
                    if os.path.exists(path):
                        paths.append(path)
        return paths
    
    def get_selected_android_files(self):
        """Получение имен выбранных Android файлов"""
        files = []
        for item in self.android_tree.selection():
            item_data = self.android_tree.item(item)
            # Получаем имя из текста, убирая эмодзи
            text = item_data['text']
            if text.startswith("📁 ") or text.startswith("📄 "):
                name = text[2:]  # Убираем эмодзи и пробел
                if name and name != "..":
                    files.append(name)
            elif item_data['tags'] and len(item_data['tags']) > 1:
                # Запасной вариант через теги
                name = item_data['tags'][1]
                if name:
                    files.append(name)
        return files
    
    def send_selected_files(self):
        """Отправка выбранных файлов на Android"""
        if not self.device:
            messagebox.showerror("Ошибка", "Нет подключенного устройства")
            return
        
        files = self.get_selected_local_paths()
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для отправки")
            return
        
        if messagebox.askyesno("Подтверждение", f"Отправить {len(files)} файл(ов) в {self.current_path}?"):
            threading.Thread(target=self._send_files, args=(files,), daemon=True).start()
    
    def _send_files(self, files):
        """Фоновая отправка файлов"""
        self.root.after(0, lambda: self.show_progress(True, "Отправка файлов..."))
        total_files = len(files)
        
        for i, file in enumerate(files):
            try:
                command = ["adb", "-s", self.device, "push", file, self.current_path]
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.root.after(0, lambda f=file: self.log(f"✓ {os.path.basename(f)} отправлен"))
                else:
                    self.root.after(0, lambda f=file, e=result.stderr: 
                                   self.log(f"✗ Ошибка при отправке {os.path.basename(f)}: {e}"))
                
                self.root.after(0, lambda v=(i+1)/total_files*100: self.update_progress(v))
                
            except Exception as e:
                self.root.after(0, lambda f=file, err=e: 
                               self.log(f"✗ Ошибка при отправке {os.path.basename(f)}: {err}"))
        
        self.root.after(0, lambda: self.show_progress(False))
    
    def pull_selected_files(self):
        """Скачивание выбранных файлов с Android"""
        if not self.device:
            messagebox.showerror("Ошибка", "Нет подключенного устройства")
            return
        
        files = self.get_selected_android_files()
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для скачивания")
            return
        
        if messagebox.askyesno("Подтверждение", f"Скачать {len(files)} файл(ов) в {self.local_current_path}?"):
            threading.Thread(target=self._pull_files, args=(files,), daemon=True).start()
    
    def _pull_files(self, files):
        """Фоновое скачивание файлов"""
        self.root.after(0, lambda: self.show_progress(True, "Скачивание файлов..."))
        total_files = len(files)
        
        for i, file in enumerate(files):
            try:
                if self.current_path.endswith('/'):
                    remote_path = f"{self.current_path}{file}"
                else:
                    remote_path = f"{self.current_path}/{file}"
                
                command = ["adb", "-s", self.device, "pull", remote_path, self.local_current_path]
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.root.after(0, lambda f=file: self.log(f"✓ {f} скачан"))
                else:
                    self.root.after(0, lambda f=file, e=result.stderr: 
                                   self.log(f"✗ Ошибка при скачивании {f}: {e}"))
                
                self.root.after(0, lambda v=(i+1)/total_files*100: self.update_progress(v))
                
            except Exception as e:
                self.root.after(0, lambda f=file, err=e: 
                               self.log(f"✗ Ошибка при скачивании {f}: {err}"))
        
        self.root.after(0, lambda: self.show_progress(False))
    
    def delete_selected_files(self):
        """Удаление выбранных файлов с Android"""
        if not self.device:
            return
        
        files = self.get_selected_android_files()
        if not files:
            return
        
        if messagebox.askyesno("Подтверждение", f"Удалить {len(files)} файл(ов) с Android?\nЭто действие нельзя отменить!"):
            threading.Thread(target=self._delete_files, args=(files,), daemon=True).start()
    
    def _delete_files(self, files):
        """Фоновое удаление файлов"""
        for file in files:
            try:
                # Формируем путь
                if self.current_path.endswith('/'):
                    remote_path = f"{self.current_path}{file}"
                else:
                    remote_path = f"{self.current_path}/{file}"
                
                # Используем одинарные кавычки вокруг всего пути
                command = ["adb", "-s", self.device, "shell", "rm", "-rf", f"'{remote_path}'"]
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.root.after(0, lambda f=file: self.log(f"✓ {f} удалён"))
                else:
                    # Если не сработало, пробуем без кавычек
                    command = ["adb", "-s", self.device, "shell", "rm", "-rf", remote_path]
                    result = subprocess.run(command, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        self.root.after(0, lambda f=file: self.log(f"✓ {f} удалён"))
                    else:
                        self.root.after(0, lambda f=file, e=result.stderr: 
                                    self.log(f"✗ Ошибка при удалении {f}: {e}"))
                
            except Exception as e:
                self.root.after(0, lambda f=file, err=e: 
                            self.log(f"✗ Ошибка при удалении {f}: {err}"))
    
    def connect_device(self):
        """Подключение к устройству"""
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = result.stdout.split("\n")[1:]
            connected_devices = [line.split("\t")[0] for line in devices if "device" in line]
            
            if not connected_devices:
                messagebox.showwarning("Внимание", "Нет подключенных устройств")
                return
            
            if len(connected_devices) == 1:
                self.device = connected_devices[0]
            else:
                # Создаем диалог выбора устройства
                dialog = tk.Toplevel(self.root)
                dialog.title("Выбор устройства")
                dialog.geometry("500x300")
                
                ttk.Label(dialog, text="Выберите устройство:").pack(pady=10)
                
                listbox = tk.Listbox(dialog)
                listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                
                for dev in connected_devices:
                    # Получаем информацию об устройстве
                    try:
                        model = subprocess.run(["adb", "-s", dev, "shell", "getprop", "ro.product.model"], 
                                              capture_output=True, text=True).stdout.strip()
                        listbox.insert(tk.END, f"{model} ({dev})")
                    except:
                        listbox.insert(tk.END, dev)
                
                def select_device():
                    selection = listbox.curselection()
                    if selection:
                        self.device = connected_devices[selection[0]]
                        dialog.destroy()
                
                ttk.Button(dialog, text="Выбрать", command=select_device).pack(pady=10)
                
                dialog.transient(self.root)
                dialog.grab_set()
                self.root.wait_window(dialog)
            
            if self.device:
                # Получаем модель устройства
                try:
                    model = subprocess.run(["adb", "-s", self.device, "shell", "getprop", "ro.product.model"], 
                                          capture_output=True, text=True).stdout.strip()
                    self.device_label.config(text=f"Устройство: {model} ({self.device})")
                except:
                    self.device_label.config(text=f"Устройство: {self.device}")
                
                self.log(f"Подключено к устройству")
                self.refresh_android_files()
            
        except Exception as e:
            self.log(f"Ошибка при подключении к устройству: {e}")
    
    def start_scrcpy(self):
        """Запуск scrcpy"""
        try:
            # Проверка наличия scrcpy
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
            
            # Запуск в отдельном процессе
            subprocess.Popen(["scrcpy"])
            self.log("✓ Scrcpy запущен")
            
        except subprocess.CalledProcessError:
            self.log("✗ Scrcpy не найден. Установите scrcpy для этой функции")
        except Exception as e:
            self.log(f"✗ Ошибка при запуске scrcpy: {e}")
    
    def format_size(self, size):
        """Форматирование размера файла"""
        try:
            size = int(size)
            if size < 1024:
                return f"{size} B"
            elif size < 1024**2:
                return f"{size/1024:.1f} KB"
            elif size < 1024**3:
                return f"{size/1024**2:.1f} MB"
            else:
                return f"{size/1024**3:.1f} GB"
        except:
            return str(size)
    
    def log(self, message):
        """Добавление сообщения в лог"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.yview(tk.END)
        self.root.update_idletasks()
    
    def show_progress(self, show=True, text=""):
        """Отображение/скрытие прогресс бара"""
        if show:
            self.progress_label.config(text=text)
            self.progress_label.pack(side=tk.LEFT, padx=(0, 10))
            self.progress_bar.pack(side=tk.LEFT)
            self.progress_var.set(0)
        else:
            self.progress_label.pack_forget()
            self.progress_bar.pack_forget()
    
    def update_progress(self, value):
        """Обновление прогресса"""
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def __del__(self):
        """Остановка таймеров при закрытии"""
        if self.local_update_timer:
            self.local_update_timer.cancel()
        if self.android_update_timer:
            self.android_update_timer.cancel()

def main():
    root = tk.Tk()
    app = ADBFileManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()