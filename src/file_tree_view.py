import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Tuple, Optional

from models import FileInfo


class FileTreeView:
    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        on_double_click: Callable,
        on_context_menu: Callable
    ):
        self.tree: Optional[ttk.Treeview] = None
        self.path_label: Optional[ttk.Label] = None
        self._setup_ui(parent, title, on_double_click, on_context_menu)

    def _setup_ui(self, parent, title, on_double_click, on_context_menu):
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header, text=title, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(
            header,
            text="🔄",
            width=3,
            command=lambda: on_double_click(None)
        ).pack(side=tk.RIGHT, padx=(5, 0))

        nav = ttk.Frame(parent)
        nav.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(
            nav,
            text="🔼 Наверх",
            command=lambda: on_double_click("up")
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            nav,
            text="🏠 Домой",
            command=lambda: on_double_click("home")
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.path_label = ttk.Label(nav, text="", wraplength=350)
        self.path_label.pack(side=tk.LEFT, padx=(10, 0))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("size", "extra"),
            show="tree",
            yscrollcommand=scrollbar.set
        )
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
        self.tree.insert(
            "",
            tk.END,
            text=file_info.display_name,
            values=(file_info.size, file_info.permissions or file_info.modified),
            tags=("dir" if file_info.is_dir else "file", tag_data)
        )

    def get_selection(self) -> List[Tuple[str, str]]:
        items = []
        for item in self.tree.selection():
            item_data = self.tree.item(item)
            if item_data['tags'] and len(item_data['tags']) > 1:
                items.append((item_data['tags'][0], item_data['tags'][1]))
        return items

    def get_item_text(self, item) -> str:
        return self.tree.item(item)['text']