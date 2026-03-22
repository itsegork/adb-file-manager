import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Gdk, Pango

class FileTreeView:
    def __init__(self, title, on_double_click, on_context_menu):
        self.on_double_click = on_double_click
        self.on_context_menu = on_context_menu

        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Заголовок
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_label = Gtk.Label(label=title)
        title_label.set_hexpand(True)
        title_label.set_halign(Gtk.Align.START)
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh")
        refresh_btn.set_tooltip_text("Обновить")
        refresh_btn.connect("clicked", lambda btn: on_double_click(None))
        header.append(title_label)
        header.append(refresh_btn)
        self.widget.append(header)

        # Навигация
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        up_btn = Gtk.Button.new_from_icon_name("go-up")
        up_btn.set_tooltip_text("Наверх")
        up_btn.connect("clicked", lambda btn: on_double_click("up"))
        home_btn = Gtk.Button.new_from_icon_name("go-home")
        home_btn.set_tooltip_text("Домой")
        home_btn.connect("clicked", lambda btn: on_double_click("home"))
        self.path_label = Gtk.Label(label="")
        self.path_label.set_hexpand(True)
        self.path_label.set_halign(Gtk.Align.START)
        self.path_label.set_ellipsize(Pango.EllipsizeMode.END)
        nav.append(up_btn)
        nav.append(home_btn)
        nav.append(self.path_label)
        self.widget.append(nav)

        # ScrolledWindow + TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.tree = Gtk.TreeView()
        self.store = Gtk.ListStore(str, str, str, bool, str)  # display, size, extra, is_dir, path
        self.tree.set_model(self.store)

        col_name = Gtk.TreeViewColumn("Имя")
        cell_name = Gtk.CellRendererText()
        col_name.pack_start(cell_name, True)
        col_name.add_attribute(cell_name, "text", 0)
        self.tree.append_column(col_name)

        col_size = Gtk.TreeViewColumn("Размер")
        cell_size = Gtk.CellRendererText()
        col_size.pack_start(cell_size, True)
        col_size.add_attribute(cell_size, "text", 1)
        self.tree.append_column(col_size)

        col_extra = Gtk.TreeViewColumn("Инфо")
        cell_extra = Gtk.CellRendererText()
        col_extra.pack_start(cell_extra, True)
        col_extra.add_attribute(cell_extra, "text", 2)
        self.tree.append_column(col_extra)

        self.tree.connect("row-activated", self._on_row_activated)

        # Gesture для правого клика
        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(3)
        click_gesture.connect("pressed", self._on_right_click)
        self.tree.add_controller(click_gesture)

        scrolled.set_child(self.tree)
        self.widget.append(scrolled)

        # Drag and drop (приём файлов)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.widget.add_controller(drop_target)

    def _on_row_activated(self, treeview, path, column):
        iter = self.store.get_iter(path)
        is_dir = self.store.get_value(iter, 3)
        file_path = self.store.get_value(iter, 4)
        if is_dir:
            self.on_double_click(file_path)

    def _on_right_click(self, gesture, n_press, x, y):
        path = self.tree.get_path_at_pos(int(x), int(y))
        if path:
            self.tree.set_cursor(path[0])
            # Передаём координаты в виде простого объекта
            event = type('Event', (), {'x': x, 'y': y})()
            self.on_context_menu(event)
        return True

    def _on_drop(self, target, value, x, y):
        files = value.get_files()
        paths = [f.get_path() for f in files]
        if paths:
            self.on_double_click("drop", paths)
        return True

    def clear(self):
        self.store.clear()

    def add_parent_item(self):
        self.store.append(["..", "", "", True, "parent"])

    def add_file(self, file_info, path):
        icon = "folder" if file_info.is_dir else "text-x-generic"
        if file_info.name.lower().endswith('.apk'):
            icon = "package-x-generic"
        display = f"{icon} {file_info.name}"
        self.store.append([display, file_info.size, file_info.permissions or file_info.modified, file_info.is_dir, path])

    def get_selection(self):
        selection = self.tree.get_selection()
        model, rows = selection.get_selected_rows()
        items = []
        for row in rows:
            iter = model.get_iter(row)
            is_dir = model.get_value(iter, 3)
            file_path = model.get_value(iter, 4)
            items.append((is_dir, file_path))
        return items

    def set_path(self, path):
        self.path_label.set_text(path)