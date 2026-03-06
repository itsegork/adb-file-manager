import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
from pathlib import Path
import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple, Callable
import shutil
import requests
import webbrowser

@dataclass(frozen=True)
class Config:
    ANDROID_HOME = "/storage/emulated/0"
    WINDOW_SIZE = "1200x800"
    LOG_HEIGHT = 8
    PROGRESS_LENGTH = 400
    GITHUB_REPO = "itsegork/adb-file-manager"
    CURRENT_VERSION = "2.0.0"
    
    class Messages:
        NO_DEVICE = "Нет подключенного устройства"
        NO_ADB = "ADB не найден! Установите Android Debug Bridge"
        CONFIRM_DELETE = "Это действие нельзя отменить!"

@dataclass
class FileInfo:
    """Информация о файле"""
    name: str
    path: str
    size: str = ""
    permissions: str = ""
    modified: str = ""
    is_dir: bool = False
    
    @property
    def display_name(self) -> str:
        return f"📁 {self.name}" if self.is_dir else f"📄 {self.name}"
    
    @property
    def is_apk(self) -> bool:
        return self.name.lower().endswith('.apk')

@dataclass
class DeviceInfo:
    """Информация об устройстве"""
    model: str = ""
    battery_level: int = 0
    battery_status: str = ""
    battery_health: str = ""
    battery_temperature: float = 0.0
    total_storage: str = ""
    used_storage: str = ""
    free_storage: str = ""
    android_version: str = ""
    serial: str = ""

class ADBHelper:
    """Работа с ADB командами"""
    
    def __init__(self):
        self.device: Optional[str] = None
    
    @staticmethod
    def check_adb() -> bool:
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=5)
            return True
        except:
            return False
    
    def get_devices(self) -> List[str]:
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            devices = result.stdout.split("\n")[1:]
            return [line.split("\t")[0] for line in devices if "device" in line]
        except:
            return []
    
    def get_device_model(self, serial: str) -> str:
        """Получить модель устройства по серийному номеру"""
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or serial
        except:
            return serial
    
    def get_device_info(self) -> DeviceInfo:
        """Получить подробную информацию об устройстве"""
        info = DeviceInfo(serial=self.device)
        
        if not self.device:
            return info
        
        try:
            info.model = subprocess.run(
                ["adb", "-s", self.device, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            
            info.android_version = subprocess.run(
                ["adb", "-s", self.device, "shell", "getprop", "ro.build.version.release"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            
            battery_result = subprocess.run(
                ["adb", "-s", self.device, "shell", "dumpsys", "battery"],
                capture_output=True, text=True, timeout=5
            )
            
            battery_output = battery_result.stdout
            
            level_patterns = [
                r'level:\s*(\d+)',
                r'level\s*=\s*(\d+)',
                r'LEVEL:\s*(\d+)',
                r'battery level[:\s]+(\d+)'
            ]
            
            for pattern in level_patterns:
                level_match = re.search(pattern, battery_output, re.IGNORECASE)
                if level_match:
                    info.battery_level = int(level_match.group(1))
                    break
                     
            temp_match = re.search(r'temperature:\s*(\d+)', battery_output, re.IGNORECASE)
            if temp_match:
                info.battery_temperature = int(temp_match.group(1)) / 10
            
            storage = subprocess.run(
                ["adb", "-s", self.device, "shell", "df", "-h", "/storage/emulated/0"],
                capture_output=True, text=True, timeout=5
            ).stdout
            
            lines = storage.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    info.total_storage = parts[1] if len(parts) > 1 else "N/A"
                    info.used_storage = parts[2] if len(parts) > 2 else "N/A"
                    info.free_storage = parts[3] if len(parts) > 3 else "N/A"
            
        except subprocess.TimeoutExpired:
            print("Таймаут при получении информации об устройстве")
        except Exception as e:
            print(f"Ошибка получения информации об устройстве: {e}")
            info.battery_level = 0
            info.battery_status = "неизвестно"
        
        return info
    
    def run_command(self, command: str) -> Tuple[str, str]:
        if not self.device:
            return "", "Нет подключенного устройства"
        
        try:
            full_cmd = f"adb -s {self.device} {command}"
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            return result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return "", "Ошибка: команда выполнялась слишком долго (таймаут 30 сек)"
        except Exception as e:
            return "", str(e)
    
    def list_files(self, path: str) -> List[FileInfo]:
        if not self.device:
            return []
        
        try:
            clean_path = path.strip('\'"')
            escaped_path = clean_path.replace("'", "'\\''")
            
            commands = [
                ["adb", "-s", self.device, "shell", "ls", "-la", escaped_path],
                ["adb", "-s", self.device, "shell", "ls", "-l", escaped_path],
                ["adb", "-s", self.device, "shell", "ls", "-a", escaped_path],
                ["adb", "-s", self.device, "shell", "ls", escaped_path]
            ]
            
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        encoding='utf-8', 
                        errors='ignore', 
                        timeout=10
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        files = self._parse_ls_output(result.stdout)
                        if files:
                            return files
                except:
                    continue
            
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "ls", "-1", escaped_path],
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore', 
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                names = [name.strip() for name in result.stdout.strip().split('\n') 
                        if name.strip() and name.strip() not in ['.', '..']]
                
                files = []
                for name in names:
                    check_cmd = ["adb", "-s", self.device, "shell", "ls", "-ld", f"'{escaped_path}/{name}'"]
                    try:
                        check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                        is_dir = check_result.stdout.startswith('d') if check_result.stdout else False
                    except:
                        is_dir = False
                    
                    files.append(FileInfo(
                        name=name,
                        path=name,
                        is_dir=is_dir
                    ))
                
                return files
            
        except subprocess.TimeoutExpired:
            print(f"Таймаут при получении списка файлов из {path}")
        except Exception as e:
            print(f"Ошибка при получении списка файлов: {e}")
        
        return []
    
    def _parse_ls_output(self, output: str) -> List[FileInfo]:
        """Парсинг вывода ls -la"""
        files = []
        
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("total"):
                continue
            
            parts = line.split()
            if len(parts) < 6:
                continue
            
            permissions = parts[0]
            is_dir = permissions.startswith('d')
            
            if parts[-1] in ['.', '..']:
                continue
            
            size_index = 4
            
            if len(parts) > size_index and not parts[size_index].isdigit():
                for i in range(4, min(8, len(parts))):
                    if parts[i].isdigit():
                        size_index = i
                        break
            
            if size_index < len(parts) and parts[size_index].isdigit():
                size = parts[size_index]
                
                name_start = size_index + 3
                
                if name_start >= len(parts):
                    name_start = size_index + 1
                
                name_parts = parts[name_start:]
                name = ' '.join(name_parts)
            else:
                name = parts[-1]
                size = ""
            
            name = name.strip('\'"')
            
            if not name:
                continue
            
            files.append(FileInfo(
                name=name,
                path=name,
                size=self._format_size(size) if size and size.isdigit() else "",
                permissions=permissions,
                is_dir=is_dir
            ))
        
        return files
    
    def _format_size(self, size: str) -> str:
        try:
            size_int = int(size)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_int < 1024:
                    return f"{size_int:.1f} {unit}"
                size_int /= 1024
            return f"{size_int:.1f} TB"
        except:
            return size
    
    def check_directory_access(self, path: str) -> bool:
        if not self.device:
            return False
        
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "ls", path],
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def push_file(self, local_path: str, remote_dir: str) -> bool:
        if not self.device:
            return False
        
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "push", local_path, remote_dir],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except:
            return False
    
    def pull_file(self, remote_path: str, local_dir: str) -> bool:
        if not self.device:
            return False
        
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "pull", remote_path, local_dir],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except:
            return False
    
    def delete_file(self, remote_path: str) -> bool:
        if not self.device:
            return False
        
        try:
            escaped_path = remote_path.replace("'", "'\\''")
            
            commands = [
                f"rm -rf '{escaped_path}'",
                f"rm -r '{escaped_path}'",
                f"rm -f '{escaped_path}'"
            ]
            
            for cmd in commands:
                result = subprocess.run(
                    ["adb", "-s", self.device, "shell", cmd],
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
                
                check_result = subprocess.run(
                    ["adb", "-s", self.device, "shell", "ls", "-d", f"'{escaped_path}'"],
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if check_result.returncode != 0:
                    return True
                
                if result.returncode == 0:
                    continue
               
            check_result = subprocess.run(
                ["adb", "-s", self.device, "shell", "ls", "-d", f"'{escaped_path}'"],
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            return check_result.returncode != 0
            
        except subprocess.TimeoutExpired:
            print(f"Таймаут при удалении {remote_path}")
            return False
        except Exception as e:
            print(f"Ошибка при удалении {remote_path}: {e}")
            return False
    
    def rename_file(self, old_path: str, new_path: str) -> bool:
        if not self.device:
            return False
        
        try:
            escaped_old = old_path.replace("'", "'\\''")
            escaped_new = new_path.replace("'", "'\\''")
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "mv", escaped_old, escaped_new],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except:
            return False
    
    def create_folder(self, path: str) -> bool:
        if not self.device:
            return False
        
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "mkdir", "-p", path],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def install_apk(self, apk_path: str) -> Tuple[bool, str]:
        if not self.device:
            return False, "Нет подключенного устройства"
        
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "install", "-r", apk_path],
                capture_output=True, text=True, timeout=120
            )
            success = result.returncode == 0
            message = result.stdout if success else result.stderr
            return success, message
        except subprocess.TimeoutExpired:
            return False, "Таймаут при установке"
        except Exception as e:
            return False, str(e)

class FileTreeView:
    
    def __init__(self, parent, title: str, on_double_click: Callable, on_context_menu: Callable):
        self.tree = None
        self.path_label = None
        self._setup_ui(parent, title, on_double_click, on_context_menu)
    
    def _setup_ui(self, parent, title: str, on_double_click: Callable, on_context_menu: Callable):
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header, text=title, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text="🔄", width=3, 
                  command=lambda: on_double_click(None)).pack(side=tk.RIGHT, padx=(5, 0))
        
        nav = ttk.Frame(parent)
        nav.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(nav, text="🔼 Наверх", 
                  command=lambda: on_double_click("up")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(nav, text="🏠 Домой", 
                  command=lambda: on_double_click("home")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.path_label = ttk.Label(nav, text="", wraplength=350)
        self.path_label.pack(side=tk.LEFT, padx=(10, 0))
        
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(tree_frame, columns=("size", "extra"), 
                                 show="tree", yscrollcommand=scrollbar.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)
        
        self.tree.column("#0", width=350)
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("extra", width=120)
        
        self.tree.heading("#0", text="Имя")
        self.tree.heading("size", text="Размер")
        self.tree.heading("extra", text="Инфо")
        
        self.tree.bind("<Double-1>", on_double_click)
        self.tree.bind("<Button-3>", on_context_menu)
    
    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def add_parent_item(self):
        self.tree.insert("", 0, text="📁 ..", values=("", ""), tags=("parent", "dir"))
    
    def add_file(self, file_info: FileInfo, tag_data: str):
        self.tree.insert("", tk.END, 
                        text=file_info.display_name,
                        values=(file_info.size, file_info.permissions or file_info.modified),
                        tags=("dir" if file_info.is_dir else "file", tag_data))
    
    def get_selection(self) -> List[Tuple[str, str]]:
        items = []
        for item in self.tree.selection():
            item_data = self.tree.item(item)
            if item_data['tags'] and len(item_data['tags']) > 1:
                items.append((item_data['tags'][0], item_data['tags'][1]))
        return items
    
    def get_item_text(self, item) -> str:
        item_data = self.tree.item(item)
        return item_data['text']

class ADBFileManager:
    def __init__(self, root):
        self.root = root
        self.root.title("ADB File Manager")
        self.root.geometry(Config.WINDOW_SIZE)
        
        self.adb = ADBHelper()
        self.current_android_path = Config.ANDROID_HOME
        self.current_local_path = str(Path.home())
        self.device_info = DeviceInfo()
        
        if not self.adb.check_adb():
            messagebox.showerror("Ошибка", Config.Messages.NO_ADB)
            self.root.quit()
            return
        
        self._setup_ui()
        self._connect_device()
        self._check_for_updates()
        
        self._start_device_info_updater()
    
    def _setup_ui(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        info_frame = ttk.LabelFrame(top_frame, text="Информация об устройстве", padding="5")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.device_info_label = ttk.Label(info_frame, text="Устройство: не подключено", wraplength=800)
        self.device_info_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(info_frame, text="🖥️ Scrcpy", 
                  command=self._show_scrcpy_dialog).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(info_frame, text="🔄 Проверить обновления", 
                  command=self._check_for_updates).pack(side=tk.RIGHT, padx=5)
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        self.local_view = FileTreeView(
            left_frame, 
            "Локальные файлы (компьютер)",
            self._on_local_double_click,
            self._show_local_context_menu
        )
        self.local_view.path_label.config(text=self.current_local_path)
        
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        self.android_view = FileTreeView(
            right_frame,
            "Файлы Android",
            self._on_android_double_click,
            self._show_android_context_menu
        )
        self.android_view.path_label.config(text=self.current_android_path)
        
        self._setup_progress_bar(main_frame)
        
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        cmd_frame = ttk.LabelFrame(bottom_frame, text="ADB команда", padding="5")
        cmd_frame.pack(fill=tk.X, pady=(0, 10))
        
        cmd_input_frame = ttk.Frame(cmd_frame)
        cmd_input_frame.pack(fill=tk.X)
        
        self.adb_command = ttk.Entry(cmd_input_frame)
        self.adb_command.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.adb_command.bind("<Return>", lambda e: self._execute_adb_command())
        
        self.adb_command.insert(0, "Введите команду (например: shell ls /sdcard, clear)")
        self.adb_command.bind("<FocusIn>", self._on_adb_command_focus_in)
        self.adb_command.bind("<FocusOut>", self._on_adb_command_focus_out)
        
        ttk.Button(cmd_input_frame, text="Выполнить", 
                  command=self._execute_adb_command).pack(side=tk.RIGHT)
        
        self._setup_log(bottom_frame)
        
        self._load_local_files()
    
    def _setup_progress_bar(self, parent):
        self.progress_frame = ttk.Frame(parent)
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            variable=self.progress_var, 
            maximum=100, 
            length=Config.PROGRESS_LENGTH
        )
        self.progress_label = ttk.Label(self.progress_frame, text="")
    
    def _setup_log(self, parent):
        log_frame = ttk.LabelFrame(parent, text="Лог операций", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(log_control_frame, text="🗑️ Очистить лог", 
                  command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(log_control_frame, text="📋 Копировать всё", 
                  command=self.copy_log_to_clipboard).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(log_control_frame, text="💾 Сохранить лог", 
                  command=self.save_log_to_file).pack(side=tk.LEFT, padx=5)
        
        text_scroll_frame = ttk.Frame(log_frame)
        text_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_scroll_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(text_scroll_frame, height=Config.LOG_HEIGHT, 
                               yscrollcommand=scrollbar.set, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("info", foreground="blue")
        self.log_text.tag_configure("command", foreground="purple")
        
        self.log_text.bind("<Button-3>", self._show_log_context_menu)
    
    def _connect_device(self):
        try:
            devices = self.adb.get_devices()
            
            if not devices:
                messagebox.showwarning("Внимание", Config.Messages.NO_DEVICE)
                return
            
            if len(devices) == 1:
                self.adb.device = devices[0]
            else:
                self._show_device_selection_dialog(devices)
            
            if self.adb.device:
                self._update_device_info()
                self.log("✓ Подключено к устройству", "success")
                self._load_android_files()
                
        except Exception as e:
            self.log(f"✗ Ошибка при подключении: {e}", "error")
    
    def _update_device_info(self):
        if not self.adb.device:
            return
        
        self.device_info = self.adb.get_device_info()
        
        if self.device_info.battery_status == "зарядка":
            battery_icon = "⚡"
        elif self.device_info.battery_level > 80:
            battery_icon = "🔋"
        elif self.device_info.battery_level > 20:
            battery_icon = "🔋"
        else:
            battery_icon = "⚠️"
        
        temp_info = ""
        if self.device_info.battery_temperature > 0:
            temp_info = f" {self.device_info.battery_temperature:.1f}°C"
        
        health_info = ""
        if self.device_info.battery_health and self.device_info.battery_health != "хорошее":
            health_info = f" [{self.device_info.battery_health}]"
        
        storage_info = ""
        if self.device_info.free_storage and self.device_info.total_storage:
            storage_info = f"💾 Свободно: {self.device_info.free_storage} / Всего: {self.device_info.total_storage}"
        else:
            storage_info = "💾 Информация о памяти недоступна"
        
        info_text = (
            f"📱 {self.device_info.model} (Android {self.device_info.android_version}) | "
            f"{battery_icon} {self.device_info.battery_level}% ({self.device_info.battery_status}{temp_info}{health_info}) | "
            f"{storage_info}"
        )
        
        self.device_info_label.config(text=info_text)
    
    def _start_device_info_updater(self):
        def update():
            if self.adb.device:
                self._update_device_info()
            self.root.after(30000, update)
        
        self.root.after(30000, update)
    
    def _show_device_selection_dialog(self, devices: List[str]):
        dialog = tk.Toplevel(self.root)
        dialog.title("Выбор устройства")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Выберите устройство:").pack(pady=10)
        
        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for dev in devices:
            model = self.adb.get_device_model(dev)
            listbox.insert(tk.END, f"{model} ({dev})")
        
        def select():
            selection = listbox.curselection()
            if selection:
                self.adb.device = devices[selection[0]]
                dialog.destroy()
                self._update_device_info()
                self._load_android_files()
        
        ttk.Button(dialog, text="Выбрать", command=select).pack(pady=10)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def _check_for_updates(self):
        threading.Thread(target=self._check_updates_thread, daemon=True).start()
    
    def _check_updates_thread(self):
        try:
            self.root.after(0, lambda: self.log("🔍 Проверка обновлений...", "info"))
            
            response = requests.get(
                f"https://api.github.com/repos/{Config.GITHUB_REPO}/releases/latest",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                
                current = Config.CURRENT_VERSION
                latest = latest_version
                
                try:
                    from packaging import version
                    has_update = version.parse(latest) > version.parse(current)
                except:
                    has_update = latest > current
                
                if has_update:
                    self.root.after(0, lambda: self._show_update_dialog(data))
                else:
                    self.root.after(0, lambda: self.log("✓ У вас последняя версия", "success"))
            else:
                self.root.after(0, lambda: self.log("✗ Не удалось проверить обновления", "error"))
                
        except Exception as error:
            self.root.after(0, lambda: self.log(f"✗ Ошибка при проверке обновлений", "error"))
    
    def _show_update_dialog(self, release_data):
        dialog = tk.Toplevel(self.root)
        dialog.title("Доступно обновление")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Доступна новая версия {release_data['tag_name']}", 
                font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, height=15)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)
        
        text.insert(tk.END, release_data.get("body", "Нет описания"))
        text.config(state=tk.DISABLED)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def download():
            webbrowser.open(release_data["html_url"])
            dialog.destroy()
        
        def later():
            dialog.destroy()
        
        download_btn = ttk.Button(button_frame, text="📥 Скачать", command=download, width=15)
        download_btn.pack(side=tk.LEFT, padx=5, expand=True)
        
        later_btn = ttk.Button(button_frame, text="⏰ Позже", command=later, width=15)
        later_btn.pack(side=tk.LEFT, padx=5, expand=True)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        dialog.focus_set()
        dialog.grab_set()
        dialog.wait_window()
    
    def _on_adb_command_focus_in(self, event):
        if self.adb_command.get() == "Введите команду (например: shell ls /sdcard, clear)":
            self.adb_command.delete(0, tk.END)
    
    def _on_adb_command_focus_out(self, event):
        if not self.adb_command.get():
            self.adb_command.insert(0, "Введите команду (например: shell ls /sdcard, clear)")
    
    def _execute_adb_command(self):
        command = self.adb_command.get().strip()
        if not command:
            return
        
        if command.lower() in ['clear']:
            self.clear_log()
            self.adb_command.delete(0, tk.END)
            return
        
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        self.log(f"> adb -s {self.adb.device} {command}", "command")
        
        def run():
            stdout, stderr = self.adb.run_command(command)
            self.root.after(0, lambda: self._show_command_result(stdout, stderr))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _show_command_result(self, stdout: str, stderr: str):
        if stdout:
            for line in stdout.split('\n'):
                if line.strip():
                    self.log(f"  {line}")
        if stderr:
            self.log(f"✗ {stderr}", "error")
    
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def copy_log_to_clipboard(self):
        log_content = self.log_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(log_content)
        self.log("✓ Лог скопирован в буфер обмена", "success")
    
    def save_log_to_file(self):
        filename = filedialog.asksaveasfilename(
            title="Сохранить лог",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                self.log(f"✓ Лог сохранён в {filename}", "success")
            except Exception as e:
                self.log(f"✗ Ошибка при сохранении лога: {e}", "error")
    
    def _show_log_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        
        menu.add_command(label="📋 Копировать", command=self.copy_selected_log)
        menu.add_command(label="📋 Копировать всё", command=self.copy_log_to_clipboard)
        menu.add_separator()
        menu.add_command(label="🗑️ Очистить", command=self.clear_log)
        menu.add_separator()
        menu.add_command(label="💾 Сохранить...", command=self.save_log_to_file)
        
        menu.post(event.x_root, event.y_root)
    
    def copy_selected_log(self):
        try:
            selected_text = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass
    
    def _load_local_files(self, path: Optional[str] = None):
        if path:
            self.current_local_path = path
        
        self.local_view.clear()
        
        try:
            if self.current_local_path != "/" and os.path.exists(os.path.dirname(self.current_local_path)):
                self.local_view.add_parent_item()
            
            files = []
            for item in os.listdir(self.current_local_path):
                full_path = os.path.join(self.current_local_path, item)
                try:
                    stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)
                    
                    file_info = FileInfo(
                        name=item,
                        path=full_path,
                        size=self._format_size(stat.st_size) if not is_dir else "",
                        modified=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        is_dir=is_dir
                    )
                    files.append(file_info)
                except:
                    continue
            
            files.sort(key=lambda x: (not x.is_dir, x.name.lower()))
            
            for file_info in files:
                self.local_view.add_file(file_info, file_info.path)
            
            self.local_view.path_label.config(text=self.current_local_path)
            
        except Exception as e:
            self.log(f"✗ Ошибка при загрузке локальных файлов: {e}", "error")
    
    def _load_android_files(self):
        if not self.adb.device:
            return
        
        threading.Thread(target=self._load_android_files_thread, daemon=True).start()
    
    def _load_android_files_thread(self):
        try:
            current_path = self.current_android_path
            self.root.after(0, lambda: self.log(f"📂 Загрузка файлов из {current_path}...", "info"))
            
            if not self.adb.check_directory_access(current_path):
                self.root.after(0, lambda: self.log(f"⚠ Нет доступа к {current_path}", "warning"))
                self.root.after(0, lambda: self._update_android_tree([]))
                return
            
            files = self.adb.list_files(current_path)
            
            files = [f for f in files if f.name and f.name.strip()]
            
            self.root.after(0, lambda: self._update_android_tree(files))
            
            if not files:
                self.root.after(0, lambda: self.log("⚠ Папка пуста или нет доступа", "warning"))
            else:
                dirs = len([f for f in files if f.is_dir])
                files_count = len([f for f in files if not f.is_dir])
                self.root.after(0, lambda: self.log(f"✓ Загружено: {dirs} папок, {files_count} файлов", "success"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"✗ Ошибка при загрузке Android файлов: {e}", "error"))
            self.root.after(0, lambda: self._update_android_tree([]))
    
    def _update_android_tree(self, files: List[FileInfo]):
        self.android_view.clear()
        
        files.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        
        for file_info in files:
            if not file_info.name:
                continue
            
            self.android_view.add_file(file_info, file_info.name)
        
        display_path = self.current_android_path
        if len(display_path) > 50:
            parts = display_path.split('/')
            if len(parts) > 3:
                display_path = f".../{'/'.join(parts[-3:])}"
        
        self.android_view.path_label.config(text=display_path)
    
    def normalize_android_path(self, path: str) -> str:
        if not path:
            return "/"
        
        path = os.path.normpath(path)
        
        path = path.replace('\\', '/')
        
        if not path.startswith('/'):
            path = '/' + path
        
        return path
    
    def _on_local_double_click(self, event):
        if event == "up":
            self._local_navigate_up()
        elif event == "home":
            self._local_go_home()
        elif event is None:
            self._load_local_files()
        else:
            selection = self.local_view.get_selection()
            if selection and selection[0][0] == "dir":
                self._load_local_files(selection[0][1])
    
    def _on_android_double_click(self, event):
        if event == "up":
            self._android_navigate_up()
        elif event == "home":
            self._android_go_home()
        elif event is None:
            self._load_android_files()
        else:
            selection = self.android_view.get_selection()
            if selection and selection[0][0] == "dir":
                folder_name = selection[0][1]
                folder_name = folder_name.strip('\'"').strip()
                
                current = self.current_android_path.rstrip('/')
                if current == "/":
                    new_path = f"/{folder_name}"
                else:
                    new_path = f"{current}/{folder_name}"
                
                self.current_android_path = self.normalize_android_path(new_path)
                self._load_android_files()
    
    def _local_navigate_up(self):
        parent = os.path.dirname(self.current_local_path)
        if parent and parent != self.current_local_path:
            self._load_local_files(parent)
    
    def _local_go_home(self):
        self._load_local_files(str(Path.home()))
    
    def _android_navigate_up(self):
        
        current = self.current_android_path.rstrip('/')
        parent = os.path.dirname(current)
        
        if not parent or parent == current:
            parent = "/storage/emulated/0"
        
        if parent == "/storage/emulated":
            messagebox.showwarning(
                "Ограничение доступа", 
                "Google идет по пути ограничения свободы Android.\n"
                "Получить доступ к корневой папке невозможно :("
            )
            self.current_android_path = Config.ANDROID_HOME
        else:
            self.current_android_path = parent
        
        self._load_android_files()
    
    def _android_go_home(self):
        self.current_android_path = Config.ANDROID_HOME
        self._load_android_files()
    
    def _rename_local_item(self):
        selection = self.local_view.get_selection()
        if not selection or selection[0][0] == "parent":
            return
        
        tag, path = selection[0]
        old_name = os.path.basename(path)
        parent_dir = os.path.dirname(path)
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Переименование")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Переименовать:\n{old_name}").pack(pady=10)
        
        frame = ttk.Frame(dialog)
        frame.pack(pady=10)
        
        ttk.Label(frame, text="Новое имя:").pack(side=tk.LEFT, padx=(0, 5))
        new_name_entry = ttk.Entry(frame, width=30)
        new_name_entry.pack(side=tk.LEFT)
        new_name_entry.insert(0, old_name)
        new_name_entry.select_range(0, tk.END)
        new_name_entry.focus()
        
        def rename():
            new_name = new_name_entry.get().strip()
            if not new_name:
                messagebox.showwarning("Предупреждение", "Введите новое имя")
                return
            
            if new_name == old_name:
                dialog.destroy()
                return
            
            new_path = os.path.join(parent_dir, new_name)
            
            try:
                os.rename(path, new_path)
                self.log(f"✓ Переименовано: {old_name} -> {new_name}", "success")
                self._load_local_files()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось переименовать: {e}")
        
        ttk.Button(dialog, text="Переименовать", command=rename).pack(pady=10)
        
        dialog.bind('<Return>', lambda e: rename())
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def _rename_android_item(self):
        if not self.adb.device:
            return
        
        selection = self.android_view.get_selection()
        if not selection or selection[0][0] == "parent":
            return
        
        tag, name = selection[0]
        old_name = name
        current_path = self.current_android_path.rstrip('/')
        old_full_path = f"{current_path}/{old_name}"
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Переименование")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Переименовать:\n{old_name}").pack(pady=10)
        
        frame = ttk.Frame(dialog)
        frame.pack(pady=10)
        
        ttk.Label(frame, text="Новое имя:").pack(side=tk.LEFT, padx=(0, 5))
        new_name_entry = ttk.Entry(frame, width=30)
        new_name_entry.pack(side=tk.LEFT)
        new_name_entry.insert(0, old_name)
        new_name_entry.select_range(0, tk.END)
        new_name_entry.focus()
        
        def rename():
            new_name = new_name_entry.get().strip()
            if not new_name:
                messagebox.showwarning("Предупреждение", "Введите новое имя")
                return
            
            if new_name == old_name:
                dialog.destroy()
                return
            
            new_full_path = f"{current_path}/{new_name}"
            
            def rename_thread():
                self._show_progress(True, "Переименование...")
                
                success = self.adb.rename_file(old_full_path, new_full_path)
                
                if success:
                    self.root.after(0, lambda: self.log(f"✓ Переименовано: {old_name} -> {new_name}", "success"))
                    self.root.after(500, self._load_android_files)
                else:
                    self.root.after(0, lambda: self.log(f"✗ Ошибка при переименовании", "error"))
                
                self.root.after(0, lambda: self._show_progress(False))
                dialog.destroy()
            
            threading.Thread(target=rename_thread, daemon=True).start()
        
        ttk.Button(dialog, text="Переименовать", command=rename).pack(pady=10)
        
        dialog.bind('<Return>', lambda e: rename())
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def _show_local_context_menu(self, event):
        item = self.local_view.tree.identify_row(event.y)
        if not item:
            return
        
        self.local_view.tree.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0)
        
        selection = self.local_view.get_selection()
        if not selection:
            return
        
        tag, path = selection[0]
        
        if tag == "parent":
            menu.add_command(label="📂 Открыть", command=self._local_navigate_up)
            menu.add_separator()
            menu.add_command(label="🔄 Обновить", command=lambda: self._load_local_files())
        else:
            is_dir = tag == "dir"
            
            if is_dir:
                menu.add_command(label="📂 Открыть", 
                               command=lambda: self._load_local_files(path))
            else:
                menu.add_command(label="📄 Открыть", state="disabled")
            
            menu.add_command(label="✏️ Переименовать", command=self._rename_local_item)
            
            if path.lower().endswith('.apk'):
                menu.add_command(label="📱 Установить APK", 
                               command=lambda: self._install_single_apk(path))
            
            menu.add_command(label="📤 Отправить на Android", command=self._send_files)
            menu.add_separator()
            menu.add_command(label="🗑️ Удалить", command=self._delete_local_files)
            menu.add_separator()
            menu.add_command(label="🔄 Обновить", command=lambda: self._load_local_files())
        
        menu.post(event.x_root, event.y_root)
    
    def _show_android_context_menu(self, event):
        if not self.adb.device:
            return
        
        item = self.android_view.tree.identify_row(event.y)
        if not item:
            return
        
        self.android_view.tree.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0)
        
        selection = self.android_view.get_selection()
        if not selection:
            return
        
        tag, name = selection[0]
        
        if tag == "dir":
            menu.add_command(label="📂 Открыть папку", 
                           command=lambda: self._on_android_double_click(None))
            menu.add_command(label="📥 Скачать папку", command=self._pull_files)
        else:
            menu.add_command(label="📥 Скачать файл", command=self._pull_files)
            
            if name.lower().endswith('.apk'):
                menu.add_command(label="📱 Установить APK", 
                               command=lambda: self._install_apk_from_device(name))
        
        menu.add_command(label="✏️ Переименовать", command=self._rename_android_item)
        menu.add_separator()
        menu.add_command(label="🗑️ Удалить", command=self._delete_android_files)
        menu.add_separator()
        menu.add_command(label="📁 Создать папку здесь", command=self._create_android_folder)
        menu.add_command(label="🔄 Обновить", command=self._load_android_files)
        
        menu.post(event.x_root, event.y_root)
    
    def _send_files(self):
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        files = [path for _, path in self.local_view.get_selection() if path != "parent"]
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для отправки")
            return
        
        if messagebox.askyesno("Подтверждение", f"Отправить {len(files)} файл(ов)?"):
            threading.Thread(target=self._send_files_thread, args=(files,), daemon=True).start()
    
    def _send_files_thread(self, files: List[str]):
        self._show_progress(True, "Отправка файлов...")
        
        for i, file in enumerate(files):
            try:
                success = self.adb.push_file(file, self.current_android_path)
                basename = os.path.basename(file)
                
                if success:
                    self.root.after(0, lambda f=basename: self.log(f"✓ {f} отправлен", "success"))
                else:
                    self.root.after(0, lambda f=basename: self.log(f"✗ Ошибка при отправке {f}", "error"))
                
                self._update_progress((i + 1) / len(files) * 100)
                
            except Exception as e:
                self.root.after(0, lambda f=basename, err=e: 
                               self.log(f"✗ Ошибка при отправке {f}: {err}", "error"))
        
        self._show_progress(False)
        self.root.after(500, self._load_android_files)
    
    def _pull_files(self):
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        files = [name for _, name in self.android_view.get_selection()]
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для скачивания")
            return
        
        if messagebox.askyesno("Подтверждение", f"Скачать {len(files)} файл(ов)?"):
            threading.Thread(target=self._pull_files_thread, args=(files,), daemon=True).start()
    
    def _pull_files_thread(self, files: List[str]):
        self._show_progress(True, "Скачивание файлов...")
        
        for i, file in enumerate(files):
            try:
                remote_path = f"{self.current_android_path.rstrip('/')}/{file}"
                success = self.adb.pull_file(remote_path, self.current_local_path)
                
                if success:
                    self.root.after(0, lambda f=file: self.log(f"✓ {f} скачан", "success"))
                else:
                    self.root.after(0, lambda f=file: self.log(f"✗ Ошибка при скачивании {f}", "error"))
                
                self._update_progress((i + 1) / len(files) * 100)
                
            except Exception as e:
                self.root.after(0, lambda f=file, err=e: 
                               self.log(f"✗ Ошибка при скачивании {f}: {err}", "error"))
        
        self._show_progress(False)
        self.root.after(500, self._load_local_files)
    
    def _delete_local_files(self):
        files = [path for _, path in self.local_view.get_selection() if path != "parent"]
        if not files:
            return
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить {len(files)} файл(ов)?\n{Config.Messages.CONFIRM_DELETE}"):
            for file in files:
                try:
                    if os.path.isfile(file):
                        os.remove(file)
                    elif os.path.isdir(file):
                        shutil.rmtree(file)
                    self.log(f"✓ {os.path.basename(file)} удалён", "success")
                except Exception as e:
                    self.log(f"✗ Ошибка при удалении {os.path.basename(file)}: {e}", "error")
            
            self._load_local_files()
    
    def _delete_android_files(self):
        if not self.adb.device:
            return
        
        files = [name for _, name in self.android_view.get_selection()]
        if not files:
            return
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить {len(files)} файл(ов)?\n{Config.Messages.CONFIRM_DELETE}"):
            threading.Thread(target=self._delete_android_files_thread, args=(files,), daemon=True).start()
    
    def _delete_android_files_thread(self, files: List[str]):
        for file in files:
            try:
                remote_path = f"{self.current_android_path.rstrip('/')}/{file}"
                success = self.adb.delete_file(remote_path)
                
                if success:
                    self.root.after(0, lambda f=file: self.log(f"✓ {f} удалён", "success"))
                else:
                    self.root.after(0, lambda f=file: self.log(f"✗ Ошибка при удалении {f}", "error"))
                    
            except Exception as e:
                self.root.after(0, lambda f=file, err=e: 
                               self.log(f"✗ Ошибка при удалении {f}: {err}", "error"))
        
        self.root.after(500, self._load_android_files)
    
    def _create_android_folder(self):
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Создание папки")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Создать папку в:\n{self.current_android_path}").pack(pady=10)
        
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
                threading.Thread(target=self._create_folder_thread, args=(name,), daemon=True).start()
            else:
                messagebox.showwarning("Предупреждение", "Введите имя папки")
        
        ttk.Button(dialog, text="Создать", command=create).pack(pady=10)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def _create_folder_thread(self, folder_name: str):
        folder_path = f"{self.current_android_path.rstrip('/')}/{folder_name}"
        success = self.adb.create_folder(folder_path)
        
        if success:
            self.root.after(0, lambda: self.log(f"✓ Папка {folder_name} создана", "success"))
            self.root.after(500, self._load_android_files)
        else:
            self.root.after(0, lambda: self.log(f"✗ Ошибка при создании папки", "error"))
    
    def _install_single_apk(self, apk_path: str):
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        if messagebox.askyesno("Подтверждение", f"Установить {os.path.basename(apk_path)}?"):
            threading.Thread(target=self._install_apks_thread, args=([apk_path],), daemon=True).start()
    
    def _install_apk_from_device(self, apk_name: str):
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        remote_path = f"{self.current_android_path.rstrip('/')}/{apk_name}"
        local_temp = os.path.join(self.current_local_path, f"temp_{apk_name}")
        
        if messagebox.askyesno("Подтверждение", f"Скачать и установить {apk_name}?"):
            threading.Thread(target=self._install_from_device_thread, 
                           args=(remote_path, local_temp, apk_name), daemon=True).start()
    
    def _install_from_device_thread(self, remote_path: str, local_temp: str, apk_name: str):
        try:
            self._show_progress(True, f"Скачивание {apk_name}...")
            
            if not self.adb.pull_file(remote_path, local_temp):
                self.root.after(0, lambda: self.log(f"✗ Ошибка при скачивании {apk_name}", "error"))
                self._show_progress(False)
                return
            
            self._update_progress(50)
            self._show_progress(True, f"Установка {apk_name}...")
            
            success, message = self.adb.install_apk(local_temp)
            
            if success:
                self.root.after(0, lambda: self.log(f"✓ {apk_name} установлен", "success"))
            else:
                self.root.after(0, lambda: self.log(f"✗ Ошибка при установке {apk_name}: {message}", "error"))
            
            try:
                os.remove(local_temp)
            except:
                pass
            
            self._show_progress(False)
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"✗ Ошибка при установке {apk_name}: {e}", "error"))
            self._show_progress(False)
    
    def _install_apks_thread(self, apk_files: List[str]):
        total_files = len(apk_files)
        
        for i, apk_file in enumerate(apk_files):
            try:
                self._show_progress(True, f"Установка {os.path.basename(apk_file)} ({i+1}/{total_files})")
                
                if not apk_file.lower().endswith('.apk'):
                    self.root.after(0, lambda f=apk_file: 
                                   self.log(f"✗ {os.path.basename(f)} не является APK", "error"))
                    continue
                
                success, message = self.adb.install_apk(apk_file)
                
                if success:
                    self.root.after(0, lambda f=apk_file: 
                                   self.log(f"✓ {os.path.basename(f)} установлен", "success"))
                else:
                    self.root.after(0, lambda f=apk_file, m=message: 
                                   self.log(f"✗ Ошибка при установке {os.path.basename(f)}: {m}", "error"))
                
                self._update_progress((i + 1) / total_files * 100)
                
            except Exception as e:
                self.root.after(0, lambda f=apk_file, err=e: 
                               self.log(f"✗ Ошибка при установке {os.path.basename(f)}: {err}", "error"))
        
        self._show_progress(False)
    
    def _show_scrcpy_dialog(self):
        if not self.adb.device:
            messagebox.showerror("Ошибка", Config.Messages.NO_DEVICE)
            return
        
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True, timeout=5)
        except:
            result = messagebox.askyesno(
                "Scrcpy не найден",
                "Scrcpy не установлен. Хотите скачать его?"
            )
            if result:
                webbrowser.open("https://github.com/Genymobile/scrcpy/releases")
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
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def launch():
            device_serial = self.adb.device
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
                subprocess.Popen(params)
                self.log(f"✓ Scrcpy запущен для устройства {device_serial}", "success")
            except Exception as e:
                self.log(f"✗ Ошибка при запуске scrcpy: {e}", "error")
        
        ttk.Button(button_frame, text="Запустить", command=launch, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def log(self, message: str, tag: str = None):
        if tag is None:
            if message.startswith('✓'):
                tag = "success"
            elif message.startswith('✗'):
                tag = "error"
            elif message.startswith('⚠'):
                tag = "warning"
            elif message.startswith('>'):
                tag = "command"
            elif message.startswith('📂') or message.startswith('🔍') or message.startswith('📊'):
                tag = "info"
        
        if tag:
            self.log_text.insert(tk.END, message + "\n", tag)
        else:
            self.log_text.insert(tk.END, message + "\n")
        
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()
    
    def _show_progress(self, show: bool = True, text: str = ""):
        if show:
            self.progress_label.config(text=text)
            self.progress_label.pack(side=tk.LEFT, padx=(0, 10))
            self.progress_bar.pack(side=tk.LEFT)
            self.progress_var.set(0)
        else:
            self.progress_label.pack_forget()
            self.progress_bar.pack_forget()
    
    def _update_progress(self, value: float):
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def _format_size(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

def main():
    root = tk.Tk()
    app = ADBFileManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
