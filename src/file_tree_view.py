#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango, GLib

class FileTreeView:
    def __init__(self, on_double_click, on_context_menu, get_path_cb=None):
        """
        on_double_click: вызывается при:
            - двойном клике по папке: on_double_click(имя_папки)
            - нажатии кнопки "Наверх": on_double_click("up")
            - нажатии кнопки "Домой": on_double_click("home")
            - нажатии кнопки "Обновить": on_double_click(None)
            - при перетаскивании файлов: on_double_click("drop", список_путей)
        on_context_menu: вызывается с объектом, имеющим поля x, y (координаты клика)
        get_path_cb: функция, возвращающая текущий путь (для копирования пути)
        """
        self.on_double_click = on_double_click
        self.on_context_menu = on_context_menu
        self.get_path_cb = get_path_cb

        # Основной контейнер
        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Панель навигации (путь)
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.path_label = Gtk.Label(label="")
        self.path_label.set_hexpand(True)
        self.path_label.set_halign(Gtk.Align.START)
        self.path_label.set_ellipsize(Pango.EllipsizeMode.END)  # Исправлено: Pango.EllipsizeMode
        nav_box.append(self.path_label)
        self.widget.append(nav_box)

        # ScrolledWindow с TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_has_frame(True)
        self.tree = Gtk.TreeView()
        self.tree.set_headers_visible(True)

        # Модель: иконка (pixbuf), имя, размер, доп. информация, is_dir, путь
        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, bool, str)
        self.tree.set_model(self.store)

        # Колонка с иконкой
        col_icon = Gtk.TreeViewColumn()
        cell_icon = Gtk.CellRendererPixbuf()
        col_icon.pack_start(cell_icon, False)
        col_icon.add_attribute(cell_icon, "pixbuf", 0)
        col_icon.set_title("")
        col_icon.set_expand(False)
        col_icon.set_min_width(30)
        self.tree.append_column(col_icon)

        # Колонка имени
        col_name = Gtk.TreeViewColumn("Имя")
        cell_name = Gtk.CellRendererText()
        col_name.pack_start(cell_name, True)
        col_name.add_attribute(cell_name, "text", 1)
        col_name.set_expand(True)
        self.tree.append_column(col_name)

        # Колонка размера
        col_size = Gtk.TreeViewColumn("Размер")
        cell_size = Gtk.CellRendererText()
        col_size.pack_start(cell_size, True)
        col_size.add_attribute(cell_size, "text", 2)
        col_size.set_expand(False)
        self.tree.append_column(col_size)

        # Колонка доп. информации (права, дата)
        col_extra = Gtk.TreeViewColumn("Инфо")
        cell_extra = Gtk.CellRendererText()
        col_extra.pack_start(cell_extra, True)
        col_extra.add_attribute(cell_extra, "text", 3)
        col_extra.set_expand(False)
        self.tree.append_column(col_extra)

        # Обработка двойного клика
        self.tree.connect("row-activated", self._on_row_activated)

        # Контекстное меню (правый клик)
        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(3)
        click_gesture.connect("pressed", self._on_right_click)
        self.tree.add_controller(click_gesture)

        # Клавиатурные сокращения
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.tree.add_controller(key_controller)

        scrolled.set_child(self.tree)
        self.widget.append(scrolled)

        # Drag and drop (приём файлов)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.widget.add_controller(drop_target)

    def _on_row_activated(self, treeview, path, column):
        """Двойной клик по строке"""
        iter = self.store.get_iter(path)
        is_dir = self.store.get_value(iter, 4)
        file_path = self.store.get_value(iter, 5)
        if is_dir:
            # Открываем папку
            self.on_double_click(file_path)

    def _on_right_click(self, gesture, n_press, x, y):
        """Обработка правого клика для контекстного меню"""
        path = self.tree.get_path_at_pos(int(x), int(y))
        if path:
            # Выделяем строку под курсором
            self.tree.set_cursor(path[0])
            # Передаём координаты в виде простого объекта
            event = type('Event', (), {'x': x, 'y': y})()
            self.on_context_menu(event)
        return True

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Обработка клавиатурных сокращений"""
        # Enter - открыть выделенную папку
        if keyval == Gdk.KEY_Return:
            self._activate_current()
            return True
        # Backspace или Ctrl+Up - на уровень вверх
        if keyval == Gdk.KEY_BackSpace or (keyval == Gdk.KEY_Up and (state & Gdk.ModifierType.CONTROL_MASK)):
            self.on_double_click("up")
            return True
        # Home - домашняя папка
        if keyval == Gdk.KEY_Home:
            self.on_double_click("home")
            return True
        # F5 или Ctrl+R - обновить
        if keyval == Gdk.KEY_F5 or (keyval == Gdk.KEY_r and (state & Gdk.ModifierType.CONTROL_MASK)):
            self.on_double_click(None)
            return True
        # Ctrl+C - копировать полный путь выделенного элемента
        if keyval == Gdk.KEY_c and (state & Gdk.ModifierType.CONTROL_MASK):
            self._copy_path_to_clipboard()
            return True
        return False

    def _activate_current(self):
        """Активировать выделенную строку (открыть папку)"""
        selection = self.tree.get_selection()
        model, rows = selection.get_selected_rows()
        if rows:
            iter = model.get_iter(rows[0])
            is_dir = model.get_value(iter, 4)
            path = model.get_value(iter, 5)
            if is_dir:
                self.on_double_click(path)

    def _copy_path_to_clipboard(self):
        """Скопировать полный путь выделенного элемента в буфер обмена"""
        if not self.get_path_cb:
            return
        selection = self.get_selection()
        if selection:
            _, file_path = selection[0]
            if file_path and file_path != "parent":
                current_path = self.get_path_cb()
                full_path = f"{current_path.rstrip('/')}/{file_path}"
                clipboard = Gdk.Display.get_default().get_clipboard()
                clipboard.set(full_path)

    def _on_drop(self, target, value, x, y):
        """Обработка перетаскивания файлов в панель"""
        files = value.get_files()
        paths = [f.get_path() for f in files]
        if paths:
            self.on_double_click("drop", paths)
        return True

    def clear(self):
        """Очистить список файлов"""
        self.store.clear()

    def add_file(self, file_info, path):
        """
        Добавить файл в список.
        file_info: объект с полями name, is_dir, size, permissions, modified
        path: относительный путь (только имя файла/папки)
        """
        # Определяем иконку
        icon_name = "folder" if file_info.is_dir else "text-x-generic"
        if file_info.name.lower().endswith('.apk'):
            icon_name = "package-x-generic"
        # Загружаем иконку из темы
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        try:
            pixbuf = icon_theme.load_icon(icon_name, 16, 0)
        except:
            pixbuf = None
        # Добавляем в модель
        self.store.append([
            pixbuf,
            file_info.name,
            file_info.size,
            file_info.permissions or file_info.modified,
            file_info.is_dir,
            path
        ])

    def get_selection(self):
        """Возвращает список выбранных элементов в виде (is_dir, path)"""
        selection = self.tree.get_selection()
        model, rows = selection.get_selected_rows()
        items = []
        for row in rows:
            iter = model.get_iter(row)
            is_dir = model.get_value(iter, 4)
            file_path = model.get_value(iter, 5)
            items.append((is_dir, file_path))
        return items

    def set_path(self, path):
        """Устанавливает текст отображаемого пути"""
        self.path_label.set_text(path)