import subprocess
import re
from typing import List, Optional, Tuple

from models import FileInfo, DeviceInfo
from utils import format_size_from_str


class ADBHelper:

    def __init__(self):
        self.device: Optional[str] = None

    @staticmethod
    def check_adb() -> bool:
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def get_devices(self) -> List[str]:
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            devices = result.stdout.split("\n")[1:]
            return [line.split("\t")[0] for line in devices if "device" in line]
        except subprocess.SubprocessError:
            return []

    def get_device_model(self, serial: str) -> str:
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() or serial
        except subprocess.SubprocessError:
            return serial

    def get_device_info(self) -> DeviceInfo:
        info = DeviceInfo(serial=self.device)
        if not self.device:
            return info

        try:
            info.model = self._get_property("ro.product.model")
            info.android_version = self._get_property("ro.build.version.release")

            battery_out = self._run_shell("dumpsys battery")
            if battery_out:
                level_match = re.search(r'level:\s*(\d+)', battery_out, re.IGNORECASE)
                if level_match:
                    info.battery_level = int(level_match.group(1))
                temp_match = re.search(r'temperature:\s*(\d+)', battery_out, re.IGNORECASE)
                if temp_match:
                    info.battery_temperature = int(temp_match.group(1)) / 10
                status_match = re.search(r'status:\s*(\d+)', battery_out, re.IGNORECASE)
                if status_match:
                    status_codes = {1: "неизвестно", 2: "зарядка", 3: "разрядка",
                                    4: "не заряжается", 5: "полный"}
                    info.battery_status = status_codes.get(int(status_match.group(1)), "")
                health_match = re.search(r'health:\s*(\d+)', battery_out, re.IGNORECASE)
                if health_match:
                    health_codes = {1: "неизвестно", 2: "хорошее", 3: "перегрев",
                                    4: "мёртв", 5: "перенапряжение", 6: "не указано",
                                    7: "холод"}
                    info.battery_health = health_codes.get(int(health_match.group(1)), "")

            # Память
            storage_out = self._run_shell("df -h /storage/emulated/0")
            if storage_out:
                lines = storage_out.strip().split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        info.total_storage = parts[1]
                        info.used_storage = parts[2]
                        info.free_storage = parts[3]

        except Exception as e:
            print(f"Ошибка получения информации об устройстве: {e}")

        return info

    def _get_property(self, prop: str) -> str:
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "getprop", prop],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except subprocess.SubprocessError:
            return ""

    def _run_shell(self, command: str) -> str:
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", command],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout
        except subprocess.SubprocessError:
            return ""

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
                names = [n.strip() for n in result.stdout.strip().split('\n')
                         if n.strip() and n.strip() not in ['.', '..']]
                files = []
                for name in names:
                    check_cmd = ["adb", "-s", self.device, "shell", "ls", "-ld", f"'{escaped_path}/{name}'"]
                    try:
                        check_res = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                        is_dir = check_res.stdout.startswith('d') if check_res.stdout else False
                    except:
                        is_dir = False
                    files.append(FileInfo(name=name, path=name, is_dir=is_dir))
                return files

        except subprocess.TimeoutExpired:
            print(f"Таймаут при получении списка файлов из {path}")
        except Exception as e:
            print(f"Ошибка при получении списка файлов: {e}")

        return []

    def _parse_ls_output(self, output: str) -> List[FileInfo]:
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

            if parts[-1] in ('.', '..'):
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
                size=format_size_from_str(size) if size and size.isdigit() else "",
                permissions=permissions,
                is_dir=is_dir
            ))

        return files

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
        except subprocess.SubprocessError:
            return False

    def push_file(self, local_path: str, remote_dir: str) -> bool:
        if not self.device:
            return False
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "push", local_path, remote_dir],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def pull_file(self, remote_path, local_path):
        return subprocess.Popen(
            ["adb", "-s", self.device, "pull", remote_path, local_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

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
                subprocess.run(
                    ["adb", "-s", self.device, "shell", cmd],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                check = subprocess.run(
                    ["adb", "-s", self.device, "shell", "ls", "-d", f"'{escaped_path}'"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if check.returncode != 0:
                    return True
            check = subprocess.run(
                ["adb", "-s", self.device, "shell", "ls", "-d", f"'{escaped_path}'"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return check.returncode != 0
        except subprocess.SubprocessError:
            return False

    def rename_file(self, old_path: str, new_path: str) -> bool:
        if not self.device:
            return False
        try:
            escaped_old = old_path.replace("'", "'\\''")
            escaped_new = new_path.replace("'", "'\\''")
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "mv", escaped_old, escaped_new],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def create_folder(self, path: str) -> bool:
        if not self.device:
            return False
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", "mkdir", "-p", path],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def install_apk(self, apk_path: str) -> Tuple[bool, str]:
        if not self.device:
            return False, "Нет подключенного устройства"
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "install", "-r", apk_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            success = result.returncode == 0
            message = result.stdout if success else result.stderr
            return success, message
        except subprocess.TimeoutExpired:
            return False, "Таймаут при установке"
        except Exception as e:
            return False, str(e)
        
    def get_file_size(self, remote_path: str) -> int:
        """
        Считает суммарный размер всех файлов в папке (рекурсивно) через adb.
        Возвращает размер в байтах.
        """
        import subprocess

        total = 0
        try:
            # Получаем список всех файлов с полными путями
            cmd = f'adb -s {self.device} shell "find \\"{remote_path}\\" -type f"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            files = result.stdout.strip().splitlines()
            for f in files:
                # Получаем размер каждого файла
                size_cmd = f'adb -s {self.device} shell "stat -c %s \\"{f}\\" "'
                size_result = subprocess.run(size_cmd, shell=True, capture_output=True, text=True)
                s = size_result.stdout.strip()
                if s.isdigit():
                    total += int(s)
        except Exception:
            pass
        return total
    
    def get_directory_size(self, path: str) -> int:
        """Получает размер папки с помощью du -sh для быстрого подсчёта"""
        from utils import parse_size
        output = self._run_shell(f"du -sh '{path}'")
        if output:
            parts = output.split()
            if parts:
                size_str = parts[0]
                return parse_size(size_str)
        return 0
    
    def is_directory(self, path: str) -> bool:
        """Возвращает True, если путь на устройстве — папка"""
        result, _ = self.run_command(f'shell [ -d "{path}" ] && echo 1 || echo 0')
        return result.strip() == "1"
    
    def list_all_files(self, folder: str) -> List[str]:
        """Возвращает список всех файлов (с полными путями) внутри папки"""
        files = []
        def walk(remote_path):
            entries = self.list_files(remote_path)  # твой существующий метод, который возвращает FileInfo[]
            for f in entries:
                full_path = f"{remote_path.rstrip('/')}/{f.name}"
                if f.is_dir:
                    walk(full_path)
                else:
                    files.append(full_path)
        walk(folder)
        return files
    
    def get_total_size(self, remote_path: str) -> int:
        """
        Возвращает размер файла или папки в байтах рекурсивно.
        """
        if self.is_directory(remote_path):
            total = 0
            for f in self.list_files(remote_path):
                total += self.get_total_size(f"{remote_path.rstrip('/')}/{f.name}")
            return total
        else:
            return self.get_file_size(remote_path)