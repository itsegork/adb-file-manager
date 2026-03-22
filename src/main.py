#!/usr/bin/env python3
import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gtk, Gio, GLib, Gdk

import os
import threading
from pathlib import Path
import shutil
import webbrowser
import subprocess
from typing import List, Optional
from datetime import datetime
import time

import requests

from config import Config
from models import DeviceInfo, FileInfo
from adb_helper import ADBHelper
from file_tree_view import FileTreeView
from info_window import InfoWindow
from utils import normalize_android_path, format_size


class ADBFileManager(Adw.Application):
    def __init__(self):
        super().__init__(application_id="ru.github.itsegork.adbfilemanager",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.adb = ADBHelper()
        self.current_android_path = Config.ANDROID_HOME
        self.current_local_path = str(Path.home())
        self.device_info = DeviceInfo()
        self.log_buffer = None
        self.window = None
        self.progress_bar = None
        self.progress_label = None
        self.log_textview = None
        self._context_selection = None   # для хранения выбранного элемента в контекстном меню

    def do_activate(self):
        if not self.adb.check_adb():
            dialog = Adw.MessageDialog.new(
                self.window, "Ошибка", Config.Messages.NO_ADB
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            self.quit()
            return

        self.window = Adw.ApplicationWindow(application=self)
        self.window.set_default_size(*Config.WINDOW_SIZE)
        self.window.set_title("ADB File Manager")

        # ---------------- Системный шрифт ----------------
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        * {
            font-family: system-ui;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window.set_content(main_box)

        # ---------------- Header ----------------
        info_bar = Adw.HeaderBar()
        self.device_label = Gtk.Label(label="Устройство: не подключено")
        info_bar.set_title_widget(self.device_label)

        menu_button = Gtk.MenuButton()
        menu = Gio.Menu()
        menu.append("О программе", "app.about")
        menu.append("Проверить обновления", "app.check-updates")
        menu.append("Scrcpy", "app.scrcpy")
        menu_button.set_menu_model(menu)
        info_bar.pack_end(menu_button)
        main_box.append(info_bar)

        # ---------------- Кнопки управления файлами ----------------
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        install_btn = Gtk.Button.new_with_label("Установить APK")
        install_btn.connect("clicked", lambda b: self._select_apk_files())
        send_btn = Gtk.Button.new_with_label("Отправить на Android")
        send_btn.connect("clicked", lambda b: self._select_files_to_send())
        button_box.append(install_btn)
        button_box.append(send_btn)
        main_box.append(button_box)

        # ---------------- Панель Android ----------------
        self.android_view = FileTreeView(
            "Android",
            self._on_android_double_click,
            self._show_android_context_menu
        )
        main_box.append(self.android_view.widget)

        # ---------------- Прогресс и лог ----------------
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.append(bottom_box)

        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.progress_label = Gtk.Label(label="")
        self.progress_bar = Gtk.ProgressBar()
        progress_box.append(self.progress_label)
        progress_box.append(self.progress_bar)
        bottom_box.append(progress_box)

        log_frame = Gtk.Frame()
        log_frame.set_label("Лог операций")
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.log_textview = Gtk.TextView()
        self.log_textview.set_editable(False)
        self.log_buffer = self.log_textview.get_buffer()
        scrolled.set_child(self.log_textview)
        log_frame.set_child(scrolled)
        bottom_box.append(log_frame)

        # Кнопки управления логом
        log_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        clear_btn = Gtk.Button.new_with_label("Очистить лог")
        clear_btn.connect("clicked", self.clear_log)
        copy_btn = Gtk.Button.new_with_label("Копировать всё")
        copy_btn.connect("clicked", self.copy_log_to_clipboard)
        save_btn = Gtk.Button.new_with_label("Сохранить лог")
        save_btn.connect("clicked", self.save_log_to_file)
        log_buttons.append(clear_btn)
        log_buttons.append(copy_btn)
        log_buttons.append(save_btn)
        bottom_box.append(log_buttons)

        # Нижняя строка для ADB команды
        cmd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.cmd_entry = Gtk.Entry()
        self.cmd_entry.set_placeholder_text("Введите ADB команду (например: shell ls /sdcard)")
        self.cmd_entry.connect("activate", lambda e: self._execute_adb_command())
        cmd_box.append(self.cmd_entry)
        exec_btn = Gtk.Button.new_with_label("Выполнить")
        exec_btn.connect("clicked", lambda b: self._execute_adb_command())
        cmd_box.append(exec_btn)
        bottom_box.append(cmd_box)

        self.window.present()

        # Подключение устройства
        self._connect_device()
        self._check_for_updates()
        self._start_device_info_updater()
        self._setup_context_actions()

    def _setup_context_actions(self):
        # Локальные действия
        local_actions = {
            "local.open": self._local_open,
            "local.refresh": lambda: self._load_local_files(),
            "local.rename": self._rename_local_item,
            "local.install": lambda: self._install_single_apk(self._context_selection[0][1] if self._context_selection else ""),
            "local.send": self._send_files,
            "local.delete": self._delete_local_files,
        }
        for name, callback in local_actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda a, p, cb=callback: cb())
            self.add_action(action)

        # Android действия
        android_actions = {
            "android.open": self._android_open,
            "android.pull": self._pull_files,
            "android.rename": self._rename_android_item,
            "android.delete": self._delete_android_files,
            "android.mkdir": self._create_android_folder,
            "android.refresh": self._load_android_files,
            "android.install": self._install_apk_from_device,
        }
        for name, callback in android_actions.items():
            action = Gio.SimpleAction.new(name, None)
            if name == "android.install":
                action.connect("activate", lambda a, p, cb=callback: cb(self._context_selection[0][1] if self._context_selection else ""))
            else:
                action.connect("activate", lambda a, p, cb=callback: cb())
            self.add_action(action)

        # Действия для верхнего меню
        app_actions = {
            "about": self._show_info_window,
            "check-updates": lambda a, p: self._check_for_updates(),
            "scrcpy": lambda a, p: self._show_scrcpy_dialog(),
        }
        for name, callback in app_actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _connect_device(self):
        devices = self.adb.get_devices()
        if not devices:
            dialog = Adw.MessageDialog.new(
                self.window, "Внимание", Config.Messages.NO_DEVICE
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            return

        if len(devices) == 1:
            self.adb.device = devices[0]
        else:
            self._show_device_selection_dialog(devices)

        if self.adb.device:
            self._update_device_info()
            self.log("Подключено к устройству", "success")
            self._load_android_files()

    def _show_device_selection_dialog(self, devices: List[str]):
        dialog = Adw.MessageDialog.new(self.window, "Выбор устройства", "Выберите устройство:")
        listbox = Gtk.ListBox()
        for dev in devices:
            model = self.adb.get_device_model(dev)
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=f"{model} ({dev})")
            row.set_child(label)
            listbox.append(row)
        dialog.set_extra_child(listbox)
        dialog.add_response("cancel", "Отмена")
        dialog.add_response("select", "Выбрать")
        dialog.set_response_appearance("select", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, resp: self._on_device_selected(d, resp, devices, listbox))
        dialog.present()

    def _on_device_selected(self, dialog, response, devices, listbox):
        if response == "select":
            row = listbox.get_selected_row()
            if row:
                idx = row.get_index()
                self.adb.device = devices[idx]
                self._update_device_info()
                self._load_android_files()
        dialog.destroy()

    def _update_device_info(self):
        if not self.adb.device:
            return
        self.device_info = self.adb.get_device_info()

        # Батарея текстом
        if self.device_info.battery_status == "зарядка":
            battery_text = f"Батарея: {self.device_info.battery_level}% (зарядка)"
        else:
            battery_text = f"Батарея: {self.device_info.battery_level}%"
        if self.device_info.battery_temperature > 0:
            battery_text += f", {self.device_info.battery_temperature:.1f}°C"
        if self.device_info.battery_health and self.device_info.battery_health != "хорошее":
            battery_text += f" [{self.device_info.battery_health}]"

        # Память
        storage_text = ""
        if self.device_info.free_storage and self.device_info.total_storage:
            storage_text = f" | Свободно: {self.device_info.free_storage} / Всего: {self.device_info.total_storage}"
        elif self.device_info.free_storage:
            storage_text = f" | Свободно: {self.device_info.free_storage}"
        elif self.device_info.total_storage:
            storage_text = f" | Всего: {self.device_info.total_storage}"

        info_text = (
            f"{self.device_info.model} (Android {self.device_info.android_version}) | "
            f"{battery_text}{storage_text}"
        )
        self.device_label.set_label(info_text)

    def _start_device_info_updater(self):
        def update():
            if self.adb.device:
                self._update_device_info()
            GLib.timeout_add_seconds(30, update)
        GLib.timeout_add_seconds(30, update)

    def _select_apk_files(self):
        dialog = Gtk.FileChooserNative.new(
            "Выберите APK для установки",
            self.window,
            Gtk.FileChooserAction.OPEN,
            "Выбрать",
            "Отмена"
        )
        dialog.set_select_multiple(True)
        dialog.connect("response", self._on_apk_files_selected)
        dialog.show()

    def _on_apk_files_selected(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            files = [f.get_path() for f in dialog.get_files()]
            if files:
                threading.Thread(target=self._install_apks_thread, args=(files,), daemon=True).start()
        dialog.destroy()

    def _select_files_to_send(self):
        dialog = Gtk.FileChooserNative.new(
            "Выберите файлы для отправки на Android",
            self.window,
            Gtk.FileChooserAction.OPEN,
            "Выбрать",
            "Отмена"
        )
        dialog.set_select_multiple(True)
        dialog.connect("response", self._on_files_to_send_selected)
        dialog.show()

    def _on_files_to_send_selected(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            files = [f.get_path() for f in dialog.get_files()]
            if files:
                self._send_files_from_drop(files)
        dialog.destroy()

    def _pull_files(self):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        selection = self.android_view.get_selection()
        files = [name for is_dir, name in selection]
        if not files:
            self.log("Выберите файлы для скачивания", "warning")
            return

        # Открываем системный диалог выбора папки
        dialog = Gtk.FileChooserNative.new(
            "Выберите папку для сохранения",
            self.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            "Выбрать",
            "Отмена"
        )
        dialog.connect("response", lambda d, resp: self._on_save_folder_selected(d, resp, files))
        dialog.show()

    def _on_save_folder_selected(self, dialog, response, files):
        if response == Gtk.ResponseType.ACCEPT:
            folder = dialog.get_file().get_path()
            threading.Thread(target=self._pull_files_thread, args=(files, folder), daemon=True).start()
        dialog.destroy()

    def _pull_files_thread(self, files: list, local_folder: str):
        self._show_progress(True, "Скачивание файлов...")
        total_size = 0
        sizes = {}

        # Сначала считаем общий размер
        def compute_size(remote_path):
            try:
                if self.adb.is_directory(remote_path):
                    size = self.adb.get_directory_size(remote_path)
                    sizes[remote_path] = size
                    return size
                else:
                    size = self.adb.get_file_size(remote_path)
                    sizes[remote_path] = size
                    return size
            except Exception:
                return 0

        for f in files:
            remote_path = f"{self.current_android_path.rstrip('/')}/{f}"
            total_size += compute_size(remote_path)

        self._show_progress(True, f"Скачивание файлов ({format_size(total_size)})...")
        downloaded = 0

        def pull_path(remote_path, local_base):
            nonlocal downloaded
            try:
                if self.adb.is_directory(remote_path):
                    folder_name = os.path.basename(remote_path)
                    local_folder_path = os.path.join(local_base, folder_name)
                    os.makedirs(local_folder_path, exist_ok=True)
                    for f in self.adb.list_files(remote_path):
                        pull_path(f"{remote_path.rstrip('/')}/{f.name}", local_folder_path)
                else:
                    filename = os.path.basename(remote_path)
                    success = self.adb.pull_file(remote_path, local_base)
                    if success:
                        file_size = self.adb.get_file_size(remote_path)  # получаем размер реально скачанного файла
                        downloaded += file_size
                        GLib.idle_add(lambda f=filename: self.log(f"{f} скачан", "success"))
                        GLib.idle_add(lambda d=downloaded, t=total_size: self._update_progress(
                            d / t * 100,
                            f"Скачивание... ({format_size(d)} / {format_size(t)})"
                        ))
                    else:
                        GLib.idle_add(lambda f=filename: self.log(f"Ошибка при скачивании {f}", "error"))
            except Exception as e:
                GLib.idle_add(lambda f=remote_path, err=e: self.log(f"Ошибка при скачивании {f}: {err}", "error"))

        for f in files:
            remote_path = f"{self.current_android_path.rstrip('/')}/{f}"
            pull_path(remote_path, local_folder)

        GLib.idle_add(self._show_progress, False)

    def _load_android_files(self):
        if not self.adb.device:
            return
        threading.Thread(target=self._load_android_files_thread, daemon=True).start()

    def _load_android_files_thread(self):
        try:
            current_path = self.current_android_path
            GLib.idle_add(lambda: self.log(f"Загрузка файлов из {current_path}...", "info"))
            if not self.adb.check_directory_access(current_path):
                GLib.idle_add(lambda: self.log(f"Нет доступа к {current_path}", "warning"))
                GLib.idle_add(lambda: self._update_android_tree([]))
                return
            files = self.adb.list_files(current_path)
            files = [f for f in files if f.name and f.name.strip()]

            GLib.idle_add(lambda: self._update_android_tree(files))
            if not files:
                GLib.idle_add(lambda: self.log("Папка пуста или нет доступа", "warning"))
            else:
                dirs = len([f for f in files if f.is_dir])
                f_count = len([f for f in files if not f.is_dir])
                GLib.idle_add(lambda: self.log(f"Загружено: {dirs} папок, {f_count} файлов", "success"))
        except Exception as e:
            GLib.idle_add(lambda: self.log(f"Ошибка при загрузке Android файлов: {e}", "error"))
            GLib.idle_add(lambda: self._update_android_tree([]))

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
        self.android_view.set_path(display_path)

    def _on_android_double_click(self, event, data=None):
        if event == "up":
            self._android_navigate_up()
        elif event == "home":
            self._android_go_home()
        elif event == "drop":
            if data:
                self._send_files_from_drop(data)
        elif event is None:
            self._load_android_files()
        elif isinstance(event, str):
            folder_name = event.strip('\'"').strip()
            current = self.current_android_path.rstrip('/')
            new_path = f"/{folder_name}" if current == "/" else f"{current}/{folder_name}"
            self.current_android_path = normalize_android_path(new_path)
            self._load_android_files()

    def _send_files_from_drop(self, paths: List[str]):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        self._ask_yes_no("Подтверждение", f"Отправить {len(paths)} файл(ов)?",
                         lambda: threading.Thread(target=self._send_files_thread, args=(paths,), daemon=True).start())

    def _send_files(self):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        selection = self.local_view.get_selection()
        files = [path for is_dir, path in selection if path != "parent"]
        if not files:
            self.log("Выберите файлы для отправки", "warning")
            return
        self._ask_yes_no("Подтверждение", f"Отправить {len(files)} файл(ов)?",
                         lambda: threading.Thread(target=self._send_files_thread, args=(files,), daemon=True).start())
        
    def get_total_size(paths: list) -> int:
        total = 0
        for path in paths:
            if os.path.isfile(path):
                total += os.path.getsize(path)
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for f in files:
                        total += os.path.getsize(os.path.join(root, f))
        return total

    def _send_files_thread(self, paths: List[str]):
        # Сначала подсчитаем общее количество файлов и размер
        all_files = []
        total_size = 0
        self._show_progress(True, "Подсчёт файлов...")
        for path in paths:
            if os.path.isfile(path):
                all_files.append(path)
                total_size += os.path.getsize(path)
            else:
                for root, _, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        all_files.append(fp)
                        total_size += os.path.getsize(fp)
        total_files = len(all_files)

        sent_bytes = 0
        self._show_progress(True, f"Отправка {total_files} файл(ов) ({format_size(total_size)})...")
        for i, file in enumerate(all_files):
            # формируем путь на устройстве
            relative = os.path.relpath(file, start=os.path.commonpath(paths))
            remote_path = f"{self.current_android_path.rstrip('/')}/{relative.replace(os.sep, '/')}"
            success = self.adb.push_file(file, remote_path)
            if success:
                sent_bytes += os.path.getsize(file)
                progress = (sent_bytes / total_size * 100) if total_size > 0 else (i + 1) / total_files * 100
                GLib.idle_add(lambda p=progress, sb=sent_bytes, ts=total_size, tf=total_files, idx=i: self._update_progress(p, f"Отправка {idx+1}/{tf} ({format_size(sb)} / {format_size(ts)})"))
                GLib.idle_add(lambda f=file: self.log(f"{os.path.basename(f)} отправлен", "success"))
            else:
                GLib.idle_add(lambda f=file: self.log(f"Ошибка при отправке {os.path.basename(f)}", "error"))
        self._show_progress(False)

    def _delete_local_files(self):
        selection = self.local_view.get_selection()
        files = [path for is_dir, path in selection if path != "parent"]
        if not files:
            return
        self._ask_yes_no("Подтверждение", f"Удалить {len(files)} файл(ов)?\n{Config.Messages.CONFIRM_DELETE}",
                         self._delete_local_files_thread, files)

    def _delete_local_files_thread(self, files):
        for file in files:
            try:
                if os.path.isfile(file):
                    os.remove(file)
                elif os.path.isdir(file):
                    shutil.rmtree(file)
                GLib.idle_add(lambda f=os.path.basename(file): self.log(f"{f} удалён", "success"))
            except Exception as e:
                GLib.idle_add(lambda f=os.path.basename(file), err=e: self.log(f"Ошибка при удалении {f}: {err}", "error"))
                GLib.idle_add(self._update_android_tree)

    def _delete_android_files(self):
        if not self.adb.device:
            return
        selection = self.android_view.get_selection()
        files = [name for is_dir, name in selection]
        if not files:
            return
        self._ask_yes_no("Подтверждение", f"Удалить {len(files)} файл(ов)?\n{Config.Messages.CONFIRM_DELETE}",
                         lambda: threading.Thread(target=self._delete_android_files_thread, args=(files,), daemon=True).start())

    def _delete_android_files_thread(self, files: List[str]):
        for file in files:
            try:
                remote_path = f"{self.current_android_path.rstrip('/')}/{file}"
                success = self.adb.delete_file(remote_path)
                if success:
                    GLib.idle_add(lambda f=file: self.log(f"{f} удалён", "success"))
                else:
                    GLib.idle_add(lambda f=file: self.log(f"Ошибка при удалении {f}", "error"))
            except Exception as e:
                GLib.idle_add(lambda f=file, err=e: self.log(f"Ошибка при удалении {f}: {err}", "error"))
        GLib.idle_add(self._load_android_files)

    def _rename_local_item(self):
        selection = self.local_view.get_selection()
        if not selection or selection[0][1] == "parent":
            return
        _, path = selection[0]
        old_name = os.path.basename(path)
        self._rename_dialog("Переименовать", old_name,
                            lambda new_name: self._rename_local_file(path, new_name))

    def _rename_local_file(self, old_path, new_name):
        if not new_name:
            return
        parent = os.path.dirname(old_path)
        new_path = os.path.join(parent, new_name)
        try:
            os.rename(old_path, new_path)
            self.log(f"Переименовано: {os.path.basename(old_path)} -> {new_name}", "success")
            self._load_local_files()
        except Exception as e:
            self.log(f"Ошибка при переименовании: {e}", "error")

    def _rename_android_item(self):
        if not self.adb.device:
            return
        selection = self.android_view.get_selection()
        if not selection:
            return
        _, name = selection[0]
        self._rename_dialog("Переименовать", name,
                            lambda new_name: self._rename_android_file(name, new_name))

    def _rename_android_file(self, old_name, new_name):
        if not new_name:
            return
        old_full = f"{self.current_android_path.rstrip('/')}/{old_name}"
        new_full = f"{self.current_android_path.rstrip('/')}/{new_name}"
        self._show_progress(True, "Переименование...")
        def rename_thread():
            success = self.adb.rename_file(old_full, new_full)
            GLib.idle_add(self._show_progress, False)
            if success:
                GLib.idle_add(lambda: self.log(f"Переименовано: {old_name} -> {new_name}", "success"))
                GLib.idle_add(self._load_android_files)
            else:
                GLib.idle_add(lambda: self.log("Ошибка при переименовании", "error"))
        threading.Thread(target=rename_thread, daemon=True).start()

    def _create_android_folder(self):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        dialog = Adw.MessageDialog.new(self.window, "Создание папки", f"Создать папку в:\n{self.current_android_path}")
        entry = Gtk.Entry()
        entry.set_placeholder_text("Имя папки")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Отмена")
        dialog.add_response("create", "Создать")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, resp: self._on_create_folder_response(d, resp, entry.get_text()))
        dialog.present()

    def _on_create_folder_response(self, dialog, response, folder_name):
        dialog.destroy()
        if response == "create" and folder_name.strip():
            threading.Thread(target=self._create_folder_thread, args=(folder_name.strip(),), daemon=True).start()

    def _create_folder_thread(self, folder_name: str):
        folder_path = f"{self.current_android_path.rstrip('/')}/{folder_name}"
        success = self.adb.create_folder(folder_path)
        if success:
            GLib.idle_add(lambda: self.log(f"Папка {folder_name} создана", "success"))
            GLib.idle_add(self._load_android_files)
        else:
            GLib.idle_add(lambda: self.log("Ошибка при создании папки", "error"))

    def _install_single_apk(self, apk_path: str):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        self._ask_yes_no("Подтверждение", f"Установить {os.path.basename(apk_path)}?",
                         lambda: threading.Thread(target=self._install_apks_thread, args=([apk_path],), daemon=True).start())

    def _install_apk_from_device(self, apk_name: str):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        remote_path = f"{self.current_android_path.rstrip('/')}/{apk_name}"
        local_temp = os.path.join(self.current_local_path, f"temp_{apk_name}")
        self._ask_yes_no("Подтверждение", f"Скачать и установить {apk_name}?",
                         lambda: threading.Thread(target=self._install_from_device_thread, args=(remote_path, local_temp, apk_name), daemon=True).start())

    def _install_from_device_thread(self, remote_path: str, local_temp: str, apk_name: str):
        try:
            self._show_progress(True, f"Скачивание {apk_name}...")
            if not self.adb.pull_file(remote_path, local_temp):
                GLib.idle_add(lambda: self.log(f"Ошибка при скачивании {apk_name}", "error"))
                self._show_progress(False)
                return
            self._update_progress(50)
            self._show_progress(True, f"Установка {apk_name}...")
            success, message = self.adb.install_apk(local_temp)
            if success:
                GLib.idle_add(lambda: self.log(f"{apk_name} установлен", "success"))
            else:
                GLib.idle_add(lambda: self.log(f"Ошибка при установке {apk_name}: {message}", "error"))
            try:
                os.remove(local_temp)
            except:
                pass
            self._show_progress(False)
        except Exception as e:
            GLib.idle_add(lambda: self.log(f"Ошибка при установке {apk_name}: {e}", "error"))
            self._show_progress(False)

    def _install_apks_thread(self, apk_files: List[str]):
        total = len(apk_files)
        for i, apk_file in enumerate(apk_files):
            try:
                self._show_progress(True, f"Установка {os.path.basename(apk_file)} ({i+1}/{total})")
                if not apk_file.lower().endswith('.apk'):
                    GLib.idle_add(lambda f=apk_file: self.log(f"{os.path.basename(f)} не является APK", "error"))
                    continue
                success, message = self.adb.install_apk(apk_file)
                if success:
                    GLib.idle_add(lambda f=apk_file: self.log(f"{os.path.basename(f)} установлен", "success"))
                else:
                    GLib.idle_add(lambda f=apk_file, m=message: self.log(f"Ошибка при установке {os.path.basename(f)}: {m}", "error"))
                self._update_progress((i + 1) / total * 100)
            except Exception as e:
                GLib.idle_add(lambda f=apk_file, err=e: self.log(f"Ошибка при установке {os.path.basename(f)}: {err}", "error"))
        self._show_progress(False)

    def _show_scrcpy_dialog(self, action=None, param=None):
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True, timeout=5)
        except:
            dialog = Adw.MessageDialog.new(
                self.window, "Scrcpy не найден",
                "Хотите скачать его?"
            )
            dialog.add_response("cancel", "Отмена")
            dialog.add_response("download", "Скачать")
            dialog.set_response_appearance("download", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", lambda d, r: webbrowser.open("https://github.com/Genymobile/scrcpy/releases") if r == "download" else None)
            dialog.present()
            return
        try:
            subprocess.Popen(["scrcpy", "-s", self.adb.device])
            self.log(f"Scrcpy запущен для устройства {self.adb.device}", "success")
        except Exception as e:
            self.log(f"Ошибка при запуске scrcpy: {e}", "error")

    def _check_for_updates(self, action=None, param=None):
        threading.Thread(target=self._check_updates_thread, daemon=True).start()

    def _check_updates_thread(self):
        try:
            GLib.idle_add(lambda: self.log("Проверка обновлений...", "info"))
            response = requests.get(
                f"https://api.github.com/repos/{Config.GITHUB_REPO}/releases/latest",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                current = Config.CURRENT_VERSION
                if latest_version > current:
                    GLib.idle_add(lambda: self._show_update_dialog(data))
                else:
                    GLib.idle_add(lambda: self.log("У вас последняя версия", "success"))
            else:
                GLib.idle_add(lambda: self.log("Не удалось проверить обновления", "error"))
        except Exception:
            GLib.idle_add(lambda: self.log("Ошибка при проверке обновлений", "error"))

    def _show_update_dialog(self, release_data):
        dialog = Adw.MessageDialog.new(
            self.window,
            f"Доступна новая версия {release_data['tag_name']}",
            release_data.get("body", "Нет описания")
        )
        dialog.add_response("cancel", "Позже")
        dialog.add_response("download", "Скачать")
        dialog.set_response_appearance("download", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, r: webbrowser.open(release_data["html_url"]) if r == "download" else None)
        dialog.present()

    def _show_info_window(self, action, param):
        InfoWindow(self.window)

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
            dialog = Adw.MessageDialog.new(
                self.window, "Ограничение доступа",
                "Google идет по пути ограничения свободы Android.\n"
                "Получить доступ к корневой папке невозможно."
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            self.current_android_path = Config.ANDROID_HOME
        else:
            self.current_android_path = parent
        self._load_android_files()

    def _android_go_home(self):
        self.current_android_path = Config.ANDROID_HOME
        self._load_android_files()

    # ---------------------- UI helpers ----------------------
    def _show_progress(self, show: bool, text: str = ""):
        if show:
            self.progress_label.set_text(text)
            self.progress_bar.set_fraction(0)
            self.progress_bar.show()
            self.progress_label.show()
        else:
            self.progress_bar.set_fraction(0)
            self.progress_bar.hide()
            self.progress_label.set_text("")
            self.progress_label.hide()

    def _update_progress(self, value: float, text: str = None):
        self.progress_bar.set_fraction(value / 100)
        if text is not None:
            self.progress_label.set_text(text)

    def log(self, message: str, tag: str = None):
        if tag == "success":
            message = f"✓ {message}"
        elif tag == "error":
            message = f"✗ {message}"
        elif tag == "warning":
            message = f"⚠ {message}"
        elif tag == "command":
            message = f"> {message}"
        elif tag == "info":
            message = f"ℹ {message}"
        self.log_buffer.insert(self.log_buffer.get_end_iter(), message + "\n")
        # прокрутка вниз
        self.log_textview.scroll_to_mark(self.log_buffer.get_insert(), 0, True, 0, 0)

    def clear_log(self, widget=None):
        self.log_buffer.set_text("")

    def copy_log_to_clipboard(self, widget=None):
        start = self.log_buffer.get_start_iter()
        end = self.log_buffer.get_end_iter()
        text = self.log_buffer.get_text(start, end, False)
        clipboard = self.window.get_clipboard()
        clipboard.set(text)

    def save_log_to_file(self, widget=None):
        dialog = Gtk.FileChooserNative.new(
            "Сохранить лог",
            self.window,
            Gtk.FileChooserAction.SAVE,
            "Сохранить",
            "Отмена"
        )
        dialog.set_current_name("adb_log.txt")
        dialog.connect("response", self._save_log_response)
        dialog.show()

    def _save_log_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_file().get_path()
            try:
                start = self.log_buffer.get_start_iter()
                end = self.log_buffer.get_end_iter()
                text = self.log_buffer.get_text(start, end, False)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.log(f"Лог сохранён в {filename}", "success")
            except Exception as e:
                self.log(f"Ошибка при сохранении лога: {e}", "error")

    def _execute_adb_command(self):
        command = self.cmd_entry.get_text().strip()
        if not command:
            return
        if command.lower() == 'clear':
            self.clear_log()
            self.cmd_entry.set_text("")
            return
        if not self.adb.device:
            self.log("Нет подключенного устройства", "error")
            return
        self.log(f"adb -s {self.adb.device} {command}", "command")
        def run():
            stdout, stderr = self.adb.run_command(command)
            GLib.idle_add(lambda: self._show_command_result(stdout, stderr))
        threading.Thread(target=run, daemon=True).start()

    def _show_command_result(self, stdout: str, stderr: str):
        if stdout:
            for line in stdout.split('\n'):
                if line.strip():
                    self.log(line)
        if stderr:
            self.log(stderr, "error")

    def _rename_dialog(self, title, old_name, callback):
        dialog = Adw.MessageDialog.new(self.window, title, f"Переименовать:\n{old_name}")
        entry = Gtk.Entry()
        entry.set_text(old_name)
        entry.select_region(0, -1)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Отмена")
        dialog.add_response("rename", "Переименовать")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda d, resp: self._on_rename_response(d, resp, entry.get_text(), callback))
        dialog.present()

    def _on_rename_response(self, dialog, response, new_name, callback):
        dialog.destroy()
        if response == "rename" and new_name.strip():
            callback(new_name.strip())

    def _ask_yes_no(self, title, message, on_yes, *args):
        dialog = Adw.MessageDialog.new(self.window, title, message)
        dialog.add_response("no", "Нет")
        dialog.add_response("yes", "Да")
        dialog.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
        if args:
            dialog.connect("response", lambda d, resp: on_yes(*args) if resp == "yes" else None)
        else:
            dialog.connect("response", lambda d, resp: on_yes() if resp == "yes" else None)
        dialog.present()

    # ---------------------- Context menus ----------------------
    def _show_local_context_menu(self, event):
        selection = self.local_view.get_selection()
        if not selection:
            return
        self._context_selection = selection

        menu = Gio.Menu()
        multiple = len(selection) > 1
        is_parent = any(path == "parent" for _, path in selection)

        if is_parent:
            menu.append("Открыть", "app.local.open")
            menu.append("Обновить", "app.local.refresh")
        else:
            # если несколько файлов выбрано
            menu.append("Открыть", "app.local.open")
            menu.append("Переименовать", "app.local.rename")
            menu.append("Удалить", "app.local.delete")
            menu.append("Обновить", "app.local.refresh")
            # только для одного файла
            if not multiple:
                is_dir, path = selection[0]
                if path.lower().endswith('.apk'):
                    menu.append("Установить APK", "app.local.install")
                menu.append("Отправить на Android", "app.local.send")

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self.local_view.tree)
        rect = Gdk.Rectangle()
        rect.x = int(event.x)
        rect.y = int(event.y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _show_android_context_menu(self, event):
        if not self.adb.device:
            return
        selection = self.android_view.get_selection()
        if not selection:
            return
        self._context_selection = selection

        menu = Gio.Menu()
        is_dir, name = selection[0]

        if is_dir:
            menu.append("Открыть папку", "app.android.open")
            menu.append("Скачать папку", "app.android.pull")
        else:
            menu.append("Скачать на ПК", "app.android.pull")
            if name.lower().endswith('.apk'):
                menu.append("Установить APK", "app.android.install")

        menu.append("Переименовать", "app.android.rename")
        menu.append("Удалить", "app.android.delete")
        menu.append("Создать папку", "app.android.mkdir")
        menu.append("Обновить", "app.android.refresh")

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self.android_view.tree)
        rect = Gdk.Rectangle()
        rect.x = int(event.x)
        rect.y = int(event.y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _local_open(self):
        if self._context_selection:
            is_dir, path = self._context_selection[0]
            if is_dir:
                self._load_local_files(path)

    def _android_open(self):
        if self._context_selection:
            is_dir, name = self._context_selection[0]
            if is_dir:
                self._on_android_double_click(name)


def main():
    app = ADBFileManager()
    app.run()

if __name__ == "__main__":
    main()