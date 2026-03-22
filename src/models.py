from dataclasses import dataclass
from typing import Optional

@dataclass
class FileInfo:
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