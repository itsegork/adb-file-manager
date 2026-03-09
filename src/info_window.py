import tkinter as tk
from tkinter import ttk
import webbrowser

from config import Config


class InfoWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("О программе")
        self.window.geometry("400x300")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self.window.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.window.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.window.winfo_height()) // 2
        self.window.geometry(f"+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self):
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="ADB File Manager",
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 5))

        version_label = ttk.Label(
            main_frame,
            text=f"Версия {Config.CURRENT_VERSION}",
            font=('Arial', 10)
        )
        version_label.pack(pady=(0, 15))

        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        github_frame = ttk.Frame(main_frame)
        github_frame.pack(pady=5)

        github_link = tk.Label(
            github_frame,
            text="GitHub",
            fg="blue",
            cursor="hand2",
            font=('Arial', 10, 'underline')
        )
        github_link.pack(side=tk.LEFT)
        github_link.bind(
            "<Button-1>",
            lambda e: webbrowser.open(f"https://github.com/{Config.GITHUB_REPO}")
        )

        ttk.Label(github_frame, text="  |  ", font=('Arial', 10)).pack(side=tk.LEFT)

        license_link = tk.Label(
            github_frame,
            text="MIT License",
            fg="blue",
            cursor="hand2",
            font=('Arial', 10, 'underline')
        )
        license_link.pack(side=tk.LEFT)
        license_link.bind(
            "<Button-1>",
            lambda e: webbrowser.open(f"https://github.com/{Config.GITHUB_REPO}/blob/main/LICENSE")
        )

        ttk.Label(main_frame, text="\nEgor Kurochkin", font=('Arial', 10)).pack(pady=(10, 5))

        ttk.Button(
            main_frame,
            text="Закрыть",
            command=self.window.destroy,
            width=15
        ).pack(pady=(20, 0))