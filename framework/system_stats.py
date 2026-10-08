# system_stats.py - сбор статистики системы
import os
import platform
import psutil
from datetime import datetime


def get_cpu_temperature():
    """Возвращает температуру CPU в °C. Только для Raspberry Pi / Linux."""
    try:
        # На Raspberry Pi температура хранится в millidegrees
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip())
        return round(temp / 1000.0, 1)
    except (FileNotFoundError, ValueError, PermissionError):
        # На Windows или при отсутствии файла — возвращаем None
        return None


def get_system_stats():
    """Возвращает словарь с текущими метриками системы."""
    # === CPU ===
    # cpu_percent(interval=0.5) — средняя нагрузка за 0.5 сек,
    # чтобы получить осмысленное значение (не 0.0)
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    cpu_freq_current = round(cpu_freq.current, 0) if cpu_freq else None

    # === Память (RAM) ===
    mem = psutil.virtual_memory()
    # Размеры в мегабайтах для читаемости
    mem_total_mb = round(mem.total / (1024 ** 2), 1)
    mem_used_mb = round(mem.used / (1024 ** 2), 1)
    mem_free_mb = round(mem.available / (1024 ** 2), 1)

    # === Swap ===
    swap = psutil.swap_memory()
    swap_total_mb = round(swap.total / (1024 ** 2), 1)
    swap_used_mb = round(swap.used / (1024 ** 2), 1)

    # === Диск ===
    # На Linux корень "/", на Windows — "C:\\"
    disk_path = '/' if os.name == 'posix' else 'C:\\'
    disk = psutil.disk_usage(disk_path)

    # === Система ===
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    uptime_str = str(uptime).split('.')[0]  # без микросекунд

    # === Процессы ===
    process_count = len(psutil.pids())

    # === Load average (только Linux) ===
    load_avg = None
    if hasattr(os, 'getloadavg'):
        load_avg = [round(x, 2) for x in os.getloadavg()]

    return {
        # CPU
        'cpu_percent': cpu_percent,
        'cpu_count': cpu_count,
        'cpu_freq': cpu_freq_current,
        'cpu_temp': get_cpu_temperature(),

        # Память
        'mem_percent': mem.percent,
        'mem_total_mb': mem_total_mb,
        'mem_used_mb': mem_used_mb,
        'mem_free_mb': mem_free_mb,

        # Swap
        'swap_percent': swap.percent,
        'swap_total_mb': swap_total_mb,
        'swap_used_mb': swap_used_mb,

        # Диск
        'disk_path': disk_path,
        'disk_percent': disk.percent,
        'disk_total_gb': round(disk.total / (1024 ** 3), 1),
        'disk_used_gb': round(disk.used / (1024 ** 3), 1),
        'disk_free_gb': round(disk.free / (1024 ** 3), 1),

        # Система
        'uptime': uptime_str,
        'boot_time': boot_time.strftime('%d.%m.%Y %H:%M'),
        'process_count': process_count,

        # Load average
        'load_avg': load_avg,

        # ОС
        'hostname': platform.node(),
        'os_name': platform.system(),
        'os_version': platform.release(),
        'python_version': platform.python_version(),
    }