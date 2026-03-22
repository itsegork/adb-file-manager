import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from config import Config

class InfoWindow:
    def __init__(self, parent):
        about = Adw.AboutWindow(
            transient_for=parent,
            application_name="ADB File Manager",
            version=Config.CURRENT_VERSION,
            comments="Менеджер файлов для Android через ADB",
            developers=["Egor Kurochkin"],
            license_type=Gtk.License.MIT_X11,
            copyright="© 2026 Egor Kurochkin",
            website=f"https://github.com/{Config.GITHUB_REPO}",
        )
        about.present()