from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    ANDROID_HOME = "/storage/emulated/0"
    WINDOW_SIZE = (1200, 800)
    GITHUB_REPO = "itsegork/adb-file-manager"
    CURRENT_VERSION = "prototype_3.0.0_build_22032026_1100"
    

    class Messages:
        NO_DEVICE = "Нет подключенного устройства"
        NO_ADB = "ADB не найден! Установите Android Debug Bridge"
        CONFIRM_DELETE = "Это действие нельзя отменить!"