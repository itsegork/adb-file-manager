from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    ANDROID_HOME = "/storage/emulated/0"
    WINDOW_SIZE = "1200x800"
    LOG_HEIGHT = 8
    PROGRESS_LENGTH = 400
    GITHUB_REPO = "itsegork/adb-file-manager"
    CURRENT_VERSION = "2.0.2"

    class Messages:
        NO_DEVICE = "Нет подключенного устройства"
        NO_ADB = "ADB не найден! Установите Android Debug Bridge"
        CONFIRM_DELETE = "Это действие нельзя отменить!"