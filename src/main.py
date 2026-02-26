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
        
        if not self.check_adb():
            messagebox.showerror("Ошибка", "ADB не найден! Установите Android Debug Bridge")
            self.root.quit()
            return
        
        self.setup_ui()
        self.connect_device()
    
    def check_adb(self):
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True)
            return True
        except:
            return False
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.device_label = ttk.Label(main_frame, text="Устройство: не подключено")
        self.device_label.pack(fill=tk.X, pady=(0, 10))
        
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        left_header = ttk.Frame(left_frame)
        left_header.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(left_header, text="Локальные файлы (компьютер)", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(left_header, text="🔄", width=3, command=self.refresh_local_files).pack(side=tk.RIGHT, padx=(5, 0))
        
        local_nav = ttk.Frame(left_frame)
        local_nav.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(local_nav, text="🔼 Наверх", command=self.local_navigate_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_nav, text="🏠 Домой", command=self.local_go_home).pack(side=tk.LEFT, padx=(0, 5))
        self.local_path_label = ttk.Label(local_nav, text=self.local_current_path, wraplength=300)
        self.local_path_label.pack(side=tk.LEFT, padx=(10, 0))
        
        self.create_local_file_tree(left_frame)
        
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        right_header = ttk.Frame(right_frame)
        right_header.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(right_header, text="Файлы Android", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(right_header, text="🔄", width=3, command=self.refresh_android_files).pack(side=tk.RIGHT, padx=(5, 0))
        
        android_nav = ttk.Frame(right_frame)
        android_nav.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(android_nav, text="🔼 Наверх", command=self.android_navigate_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(android_nav, text="🏠 Внутренняя память", command=self.android_go_home).pack(side=tk.LEFT, padx=(0, 5))
        
        self.android_path_label = ttk.Label(android_nav, text=self.current_path, wraplength=300)
        self.android_path_label.pack(side=tk.LEFT, padx=(10, 0))
        
        self.create_android_file_tree(right_frame)
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(action_frame, text="📤 Отправить на Android →", 
                  command=self.send_selected_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="← 📥 Скачать с Android", 
                  command=self.pull_selected_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🖥️ Scrcpy", 
                  command=self.show_scrcpy_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="📁 Создать папку на Android", 
                  command=self.create_android_folder).pack(side=tk.LEFT, padx=5)
        
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_label = ttk.Label(self.progress_frame, text="")
        
        log_frame = ttk.LabelFrame(main_frame, text="Лог операций", padding="5")
        log_frame.pack(fill=tk.X, pady=(10, 0))
        
        log_scrollbar = ttk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=5, yscrollcommand=log_scrollbar.set)
        self.log_text.pack(fill=tk.X, expand=True)
        log_scrollbar.config(command=self.log_text.yview)
    
    def create_local_file_tree(self, parent):
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
        
        self.local_context_menu = tk.Menu(self.root, tearoff=0)
        self.load_local_files()
    
    def create_android_file_tree(self, parent):
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
        
        self.android_context_menu = tk.Menu(self.root, tearoff=0)
        
        if self.device:
            self.load_android_files()
    
    def refresh_local_files(self):
        self.load_local_files()
        self.log("✓ Список локальных файлов обновлён")
    
    def refresh_android_files(self):
        if self.device:
            self.load_android_files()
            self.log("✓ Список файлов Android обновлён")
        else:
            self.log("✗ Устройство не подключено")
    
    def load_local_files(self, path=None):
        if path:
            self.local_current_path = path
        
        for item in self.local_tree.get_children():
            self.local_tree.delete(item)
        
        try:
            if self.local_current_path != "/" and os.path.exists(os.path.dirname(self.local_current_path)):
                self.local_tree.insert("", 0, text="📁 ..", values=("", ""), tags=("parent", "dir"))
            
            items = []
            for item in os.listdir(self.local_current_path):
                full_path = os.path.join(self.local_current_path, item)
                try:
                    stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)
                    
                    display_name = f"📁 {item}" if is_dir else f"📄 {item}"
                    size = "" if is_dir else self.format_size(stat.st_size)
                    mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    
                    items.append((display_name, size, mod_time, full_path, is_dir))
                except:
                    continue
            
            items.sort(key=lambda x: (not x[4], x[0].lower()))
            
            for display_name, size, mod_time, full_path, is_dir in items:
                tag = "dir" if is_dir else "file"
                self.local_tree.insert("", tk.END, text=display_name, 
                                     values=(size, mod_time), tags=(tag, full_path))
            
            self.local_path_label.config(text=self.local_current_path)
        except Exception as e:
            self.log(f"Ошибка при загрузке локальных файлов: {e}")
    
    def load_android_files(self):
        if self.device:
            threading.Thread(target=self._load_android_files, daemon=True).start()
    
    def _load_android_files(self):
        try:
            self.root.after(0, lambda: self.android_tree.delete(*self.android_tree.get_children()))
            
            command = ["adb", "-s", self.device, "shell", "ls", "-la", self.current_path]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                self.root.after(0, lambda: self.log(f"Ошибка при чтении директории: {result.stderr}"))
                return
            
            lines = result.stdout.strip().split("\n")
            items = []
            
            pattern = r'^([drwxlst-]{10})\s+\d+\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.+)$'
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("total"):
                    continue
                
                match = re.match(pattern, line)
                if match:
                    permissions = match.group(1)
                    size = match.group(4)
                    name = match.group(7)
                else:
                    parts = line.split()
                    if len(parts) >= 8:
                        permissions = parts[0]
                        idx = 1
                        while idx < len(parts) and not parts[idx].isdigit():
                            idx += 1
                        if idx < len(parts):
                            size = parts[idx]
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
                
                is_dir = permissions.startswith('d')
                display_name = f"📁 {name}" if is_dir else f"📄 {name}"
                size_str = self.format_size(size) if size.isdigit() else size
                
                items.append((display_name, size_str, permissions, name, is_dir))
            
            items.sort(key=lambda x: (not x[4], x[0].lower()))
            
            for display_name, size_str, permissions, name, is_dir in items:
                tag = "dir" if is_dir else "file"
                self.root.after(0, lambda dn=display_name, sz=size_str, perm=permissions, nm=name, tg=tag: 
                              self.android_tree.insert("", tk.END, text=dn, 
                                                       values=(sz, perm), 
                                                       tags=(tg, nm)))
            
            self.root.after(0, lambda: self.android_path_label.config(text=self.current_path))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Ошибка при загрузке Android файлов: {e}"))
    
    def on_local_double_click(self, event):
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
        if not self.device:
            return
        
        selection = self.android_tree.selection()
        if not selection:
            return
        
        item = self.android_tree.item(selection[0])
        tags = item.get('tags', [])
        
        if "dir" in tags and len(tags) > 1:
            folder_name = tags[1]
            if self.current_path.endswith('/'):
                new_path = f"{self.current_path}{folder_name}"
            else:
                new_path = f"{self.current_path}/{folder_name}"
            
            self.current_path = new_path
            self.load_android_files()
    
    def local_navigate_up(self):
        parent = os.path.dirname(self.local_current_path)
        if parent and parent != self.local_current_path:
            self.load_local_files(parent)
    
    def local_go_home(self):
        self.load_local_files(str(Path.home()))
    
    def android_navigate_up(self):
        if self.current_path == "/storage/emulated/0":
            messagebox.showwarning(
                "Ограничение доступа", 
                "Google идет по пути ограничения свободы Android.\n"
                "Получить доступ к корневой папке невозможно :("
            )
            return
        if self.current_path != "/":
            parent = os.path.dirname(self.current_path.rstrip("/"))
            if not parent:
                parent = "/"
            self.current_path = parent
            self.load_android_files()
    
    def android_go_home(self):
        self.current_path = "/storage/emulated/0"
        self.load_android_files()
    
    def show_local_context_menu(self, event):
        item = self.local_tree.identify_row(event.y)
        if item:
            self.local_tree.selection_set(item)
            self.local_context_menu.delete(0, tk.END)
            
            item_data = self.local_tree.item(item)
            tags = item_data.get('tags', [])
            text = item_data['text']
            
            if text == "📁 ..":
                self.local_context_menu.add_command(label="📂 Открыть", command=self.local_navigate_up)
                self.local_context_menu.add_separator()
                self.local_context_menu.add_command(label="🔄 Обновить", command=self.refresh_local_files)
            else:
                self.local_context_menu.add_command(label="📂 Открыть", command=self.open_local_folder)
                
                cmd = self.send_selected_files
                self.local_context_menu.add_command(
                    label="📤 Отправить папку на Android" if "dir" in tags else "📤 Отправить файл на Android", 
                    command=cmd
                )
                
                self.local_context_menu.add_separator()
                self.local_context_menu.add_command(label="🗑️ Удалить", command=self.delete_local_files)
                self.local_context_menu.add_separator()
                self.local_context_menu.add_command(label="🔄 Обновить", command=self.refresh_local_files)
            
            self.local_context_menu.post(event.x_root, event.y_root)
    
    def show_android_context_menu(self, event):
        item = self.android_tree.identify_row(event.y)
        if item and self.device:
            self.android_tree.selection_set(item)
            self.android_context_menu.delete(0, tk.END)
            
            item_data = self.android_tree.item(item)
            tags = item_data.get('tags', [])
            
            if "dir" in tags:
                self.android_context_menu.add_command(label="📂 Открыть папку", command=self.open_android_folder)
                self.android_context_menu.add_command(label="📥 Скачать папку на компьютер", command=self.pull_selected_files)
            else:
                self.android_context_menu.add_command(label="📥 Скачать файл на компьютер", command=self.pull_selected_files)
            
            self.android_context_menu.add_separator()
            self.android_context_menu.add_command(label="🗑️ Удалить", command=self.delete_selected_files)
            self.android_context_menu.add_separator()
            self.android_context_menu.add_command(label="📁 Создать папку здесь", command=self.create_android_folder)
            self.android_context_menu.add_command(label="🔄 Обновить", command=self.refresh_android_files)
            
            self.android_context_menu.post(event.x_root, event.y_root)
    
    def open_local_folder(self):
        selection = self.local_tree.selection()
        if selection:
            item = self.local_tree.item(selection[0])
            tags = item.get('tags', [])
            if "dir" in tags and len(tags) > 1 and item['text'] != "📁 ..":
                folder_path = tags[1]
                if os.path.isdir(folder_path):
                    self.load_local_files(folder_path)
    
    def open_android_folder(self):
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
                self.load_android_files()
    
    def delete_local_files(self):
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
            
            self.load_local_files()
    
    def create_android_folder(self):
        if not self.device:
            messagebox.showerror("Ошибка", "Нет подключенного устройства")
            return
        
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
        try:
            folder_path = f"{self.current_path.rstrip('/')}/{folder_name}"
            command = ["adb", "-s", self.device, "shell", "mkdir", "-p", folder_path]
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.root.after(0, lambda: self.log(f"✓ Папка {folder_name} создана"))
                self.root.after(500, self.load_android_files)
            else:
                self.root.after(0, lambda: self.log(f"✗ Ошибка при создании папки: {result.stderr}"))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"✗ Ошибка при создании папки: {e}"))
    
    def get_selected_local_paths(self):
        paths = []
        for item in self.local_tree.selection():
            item_data = self.local_tree.item(item)
            if item_data['text'] != "📁 .." and item_data['tags'] and len(item_data['tags']) > 1:
                path = item_data['tags'][1]
                if os.path.exists(path):
                    paths.append(path)
        return paths
    
    def get_selected_android_files(self):
        files = []
        for item in self.android_tree.selection():
            item_data = self.android_tree.item(item)
            if item_data['tags'] and len(item_data['tags']) > 1:
                name = item_data['tags'][1]
                if name:
                    files.append(name)
        return files
    
    def send_selected_files(self):
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
        self.root.after(500, self.load_android_files)
    
    def pull_selected_files(self):
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
        self.root.after(0, lambda: self.show_progress(True, "Скачивание файлов..."))
        total_files = len(files)
        
        for i, file in enumerate(files):
            try:
                remote_path = f"{self.current_path.rstrip('/')}/{file}"
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
        self.root.after(500, self.load_local_files)
    
    def delete_selected_files(self):
        if not self.device:
            return
        
        files = self.get_selected_android_files()
        if not files:
            return
        
        if messagebox.askyesno("Подтверждение", f"Удалить {len(files)} файл(ов) с Android?\nЭто действие нельзя отменить!"):
            threading.Thread(target=self._delete_files, args=(files,), daemon=True).start()
    
    def _delete_files(self, files):
        for file in files:
            try:
                remote_path = f"{self.current_path.rstrip('/')}/{file}"
                command = ["adb", "-s", self.device, "shell", "rm", "-rf", f"'{remote_path}'"]
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.root.after(0, lambda f=file: self.log(f"✓ {f} удалён"))
                else:
                    self.root.after(0, lambda f=file, e=result.stderr: 
                                   self.log(f"✗ Ошибка при удалении {f}: {e}"))
            except Exception as e:
                self.root.after(0, lambda f=file, err=e: 
                               self.log(f"✗ Ошибка при удалении {f}: {err}"))
        
        self.root.after(500, self.load_android_files)
    
    def connect_device(self):
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
                dialog = tk.Toplevel(self.root)
                dialog.title("Выбор устройства")
                dialog.geometry("500x300")
                
                ttk.Label(dialog, text="Выберите устройство:").pack(pady=10)
                
                listbox = tk.Listbox(dialog)
                listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                
                for dev in connected_devices:
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
                        self.load_android_files()
                
                ttk.Button(dialog, text="Выбрать", command=select_device).pack(pady=10)
                
                dialog.transient(self.root)
                dialog.grab_set()
                self.root.wait_window(dialog)
            
            if self.device:
                try:
                    model = subprocess.run(["adb", "-s", self.device, "shell", "getprop", "ro.product.model"], 
                                          capture_output=True, text=True).stdout.strip()
                    self.device_label.config(text=f"Устройство: {model} ({self.device})")
                except:
                    self.device_label.config(text=f"Устройство: {self.device}")
                
                self.log(f"Подключено к устройству")
                self.load_android_files()
        except Exception as e:
            self.log(f"Ошибка при подключении к устройству: {e}")
    
    def show_scrcpy_dialog(self):
        if not self.device:
            messagebox.showerror("Ошибка", "Нет подключенного устройства")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Настройки scrcpy")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        audio_frame = ttk.LabelFrame(main_frame, text="Настройки звука", padding="10")
        audio_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(audio_frame, text="Источник звука:").grid(row=0, column=0, sticky=tk.W, pady=2)
        audio_source = ttk.Combobox(audio_frame, 
                                   values=["playback (системный)", "none (без звука)"],
                                   state="readonly", width=25)
        audio_source.grid(row=0, column=1, padx=5, pady=2)
        audio_source.current(0)
        
        ttk.Label(audio_frame, text="Кодек:").grid(row=1, column=0, sticky=tk.W, pady=2)
        audio_codec = ttk.Combobox(audio_frame, 
                                  values=["aac", "opus", "raw"],
                                  state="readonly", width=25)
        audio_codec.grid(row=1, column=1, padx=5, pady=2)
        audio_codec.current(0)
        
        ttk.Label(audio_frame, text="Битрейт:").grid(row=2, column=0, sticky=tk.W, pady=2)
        audio_bitrate = ttk.Combobox(audio_frame, 
                                    values=["64K", "128K", "192K", "256K"],
                                    state="readonly", width=25)
        audio_bitrate.grid(row=2, column=1, padx=5, pady=2)
        audio_bitrate.current(1)
        
        video_frame = ttk.LabelFrame(main_frame, text="Настройки видео", padding="10")
        video_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(video_frame, text="Макс. разрешение:").grid(row=0, column=0, sticky=tk.W, pady=2)
        max_size = ttk.Combobox(video_frame, 
                               values=["1024", "1280", "1920", "2560", "оригинал"],
                               state="readonly", width=25)
        max_size.grid(row=0, column=1, padx=5, pady=2)
        max_size.current(2)
        
        ttk.Label(video_frame, text="Битрейт видео:").grid(row=1, column=0, sticky=tk.W, pady=2)
        video_bitrate = ttk.Combobox(video_frame, 
                                    values=["2M", "4M", "8M", "16M", "32M"],
                                    state="readonly", width=25)
        video_bitrate.grid(row=1, column=1, padx=5, pady=2)
        video_bitrate.current(2)
        
        options_frame = ttk.LabelFrame(main_frame, text="Дополнительно", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        stay_awake = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Не выключать экран", 
                       variable=stay_awake).pack(anchor=tk.W, pady=2)
        
        turn_screen_off = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Выключить экран телефона", 
                       variable=turn_screen_off).pack(anchor=tk.W, pady=2)
        
        info_frame = ttk.LabelFrame(main_frame, text="Устройство", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        device_info = f"Подключено: {self.device_label.cget('text').replace('Устройство: ', '')}"
        ttk.Label(info_frame, text=device_info, wraplength=400).pack()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def launch():
            device_serial = self.device.split()[-1].strip('()') if '(' in self.device else self.device
            
            params = ["scrcpy", "-s", device_serial]
            
            source = audio_source.get().split()[0]
            if source != "none":
                params.extend(["--audio-source", source])
                params.extend(["--audio-codec", audio_codec.get()])
                params.extend(["--audio-bit-rate", audio_bitrate.get()])
            
            if max_size.get() != "оригинал":
                params.extend(["--max-size", max_size.get()])
            params.extend(["--video-bit-rate", video_bitrate.get()])
            
            if stay_awake.get():
                params.append("--stay-awake")
            if turn_screen_off.get():
                params.append("--turn-screen-off")
            
            dialog.destroy()
            
            try:
                subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
                subprocess.Popen(params)
                self.log(f"✓ Scrcpy запущен для устройства {device_serial}")
            except subprocess.CalledProcessError:
                self.log("✗ Scrcpy не найден. Установите scrcpy для этой функции")
            except Exception as e:
                self.log(f"✗ Ошибка при запуске scrcpy: {e}")
        
        ttk.Button(button_frame, text="Запустить", command=launch, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.yview(tk.END)
    
    def show_progress(self, show=True, text=""):
        if show:
            self.progress_label.config(text=text)
            self.progress_label.pack(side=tk.LEFT, padx=(0, 10))
            self.progress_bar.pack(side=tk.LEFT)
            self.progress_var.set(0)
        else:
            self.progress_label.pack_forget()
            self.progress_bar.pack_forget()
    
    def update_progress(self, value):
        self.progress_var.set(value)
    
    def format_size(self, size):
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

def main():
    root = tk.Tk()
    app = ADBFileManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()