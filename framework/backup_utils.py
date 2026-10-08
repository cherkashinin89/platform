# backup_utils.py - утилиты резервного копирования
import os
import subprocess
import tarfile
from datetime import datetime
from urllib.parse import urlparse, unquote


def is_mounted(path):
    """
    Проверяет, является ли путь точкой монтирования.
    Возвращает True, если диск смонтирован и доступен для чтения.
    """
    if not path or not os.path.exists(path):
        return False
    try:
        result = subprocess.run(
            ['mountpoint', '-q', path],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # mountpoint не установлен — используем os.path.ismount
        return os.path.ismount(path)


def get_disk_info(path):
    """
    Возвращает информацию о диске: всего, занято, свободно (в ГБ).
    Если путь не существует — возвращает None.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        stat = os.statvfs(path)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        return {
            'path': path,
            'total_gb': round(total / (1024 ** 3), 1),
            'used_gb': round(used / (1024 ** 3), 1),
            'free_gb': round(free / (1024 ** 3), 1),
            'percent': round(used / total * 100, 1) if total else 0,
        }
    except (OSError, ZeroDivisionError):
        return None


def dump_postgresql(database_url, dest_path, progress_callback=None):
    """
    Создаёт дамп PostgreSQL в custom-формате (-Fc) с gzip-сжатием.
    Подключение берётся из DATABASE_URL (postgresql://user:pass@host:port/dbname).

    :param database_url: строка подключения
    :param dest_path: путь, куда положить .dump
    :param progress_callback: функция для статуса (опционально)
    :return: {'ok': bool, 'error': str|None}
    """
    try:
        parsed = urlparse(database_url)
        user = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None
        host = parsed.hostname or 'localhost'
        port = parsed.port or 5432
        dbname = parsed.path.lstrip('/') if parsed.path else None

        if not (user and dbname):
            return {
                'ok': False,
                'error': f'Некорректный DATABASE_URL: не хватает user/dbname ({database_url!r})'
            }

        # PGPASSWORD — через env, чтобы не светить в ps
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        cmd = [
            'pg_dump',
            '-Fc',          # custom формат
            '-Z', '6',      # gzip-сжатие
            '-h', host,
            '-p', str(port),
            '-U', user,
            '-d', dbname,
            '-f', dest_path,
        ]

        if progress_callback:
            progress_callback(f'pg_dump: {dbname}@{host}:{port}')

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            err = result.stderr.strip() or 'Неизвестная ошибка pg_dump'
            return {'ok': False, 'error': err}

        if not os.path.exists(dest_path) or os.path.getsize(dest_path) < 512:
            return {'ok': False, 'error': 'pg_dump создал пустой файл'}

        return {'ok': True, 'error': None}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'pg_dump: превышено время ожидания (300 с)'}
    except FileNotFoundError:
        return {'ok': False, 'error': 'pg_dump не найден в $PATH'}
    except Exception as e:
        return {'ok': False, 'error': f'Ошибка pg_dump: {e}'}


def create_full_backup(project_dir, dest_root, subdir='myframework',
                       keep_count=10, progress_callback=None):
    """
    Создаёт полный бэкап проекта во внешний диск.

    :param project_dir: путь к проекту (например, /home/deploy/apps/myframework)
    :param dest_root: точка монтирования внешнего диска (например, /mnt/backup)
    :param subdir: подпапка на диске (например, myframework)
    :param keep_count: сколько последних архивов хранить
    :param progress_callback: функция для передачи статуса (опционально)
    :return: словарь {'ok': bool, 'archive': str, 'size_mb': float, 'error': str}
    """
    if progress_callback:
        progress_callback('Проверка внешнего диска…')

    if not is_mounted(dest_root):
        return {
            'ok': False,
            'error': f'Внешний диск не смонтирован: {dest_root}',
        }

    # Готовим папку на внешнем диске
    backup_dir = os.path.join(dest_root, subdir)
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_name = f'myframework_full_{timestamp}.tar.gz'
    archive_path = os.path.join(backup_dir, archive_name)

    if progress_callback:
        progress_callback('Копирование базы данных…')

    # Создаём дамп PostgreSQL во временном файле
    temp_dump = os.path.join(backup_dir, f'.tmp_db_{timestamp}.dump')
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {'ok': False, 'error': 'DATABASE_URL не задан в окружении процесса'}

    dump_result = dump_postgresql(database_url, temp_dump, progress_callback)
    if not dump_result['ok']:
        # На всякий случай чистим возможный недописанный файл
        if os.path.exists(temp_dump):
            try:
                os.remove(temp_dump)
            except OSError:
                pass
        return {'ok': False, 'error': f"Ошибка дампа БД: {dump_result['error']}"}

    if progress_callback:
        progress_callback('Упаковка проекта в архив…')

    # Список того, что НЕ попадает в бэкап
    exclude_names = {
        'venv', '__pycache__', '.git', '.vscode',
        'node_modules', '.pytest_cache',
    }

    def filter_func(tarinfo):
        """Исключает ненужные папки из архива."""
        name = os.path.basename(tarinfo.name)
        if name in exclude_names:
            return None
        # Исключаем сам архив, если он вдруг попал
        if tarinfo.name.endswith('.tar.gz'):
            return None
        return tarinfo

    try:
        with tarfile.open(archive_path, 'w:gz') as tar:
            # 1. Дамп PostgreSQL (custom-формат, восстановление через pg_restore)
            if os.path.exists(temp_dump):
                tar.add(temp_dump, arcname='db.dump')

            # 2. Весь остальной проект
            for item in os.listdir(project_dir):
                if item in exclude_names or item == 'site.db':
                    continue
                full_path = os.path.join(project_dir, item)
                tar.add(full_path, arcname=item, filter=filter_func)
    except Exception as e:
        # Удаляем неполный архив
        if os.path.exists(archive_path):
            os.remove(archive_path)
        return {'ok': False, 'error': f'Ошибка упаковки: {e}'}
    finally:
        # Удаляем временный дамп
        if os.path.exists(temp_dump):
            os.remove(temp_dump)

    # === ПРОВЕРКА: файл реально записан и не пустой ===
    if not os.path.exists(archive_path):
        return {'ok': False, 'error': 'Архив не создан'}

    size_bytes = os.path.getsize(archive_path)
    if size_bytes < 1024:
        os.remove(archive_path)
        return {
            'ok': False,
            'error': f'Архив пустой или повреждён ({size_bytes} байт). '
                     f'Проверьте, что диск смонтирован и доступен для записи.'
        }

    # Принудительная синхронизация буферов на диск
    try:
        import subprocess as _sp
        _sp.run(['sync'], timeout=10)
    except Exception:
        pass

    size_mb = round(size_bytes / (1024 ** 2), 1)

    if progress_callback:
        progress_callback('Удаление старых бэкапов…')

    # Чистим старые архивы
    try:
        existing = sorted(
            [f for f in os.listdir(backup_dir)
             if f.startswith('myframework_full_') and f.endswith('.tar.gz')],
            reverse=True
        )
        for old in existing[keep_count:]:
            os.remove(os.path.join(backup_dir, old))
    except OSError:
        pass  # ошибка очистки не критична

    return {
        'ok': True,
        'archive': archive_path,
        'archive_name': archive_name,
        'size_mb': size_mb,
    }


def list_backups(dest_root, subdir='myframework'):
    """Возвращает список бэкапов на внешнем диске с размерами и датами."""
    backup_dir = os.path.join(dest_root, subdir)
    if not os.path.isdir(backup_dir):
        return []

    files = []
    for name in os.listdir(backup_dir):
        if not name.endswith('.tar.gz'):
            continue
        full = os.path.join(backup_dir, name)
        try:
            st = os.stat(full)
            files.append({
                'name': name,
                'size_mb': round(st.st_size / (1024 ** 2), 1),
                'mtime': datetime.fromtimestamp(st.st_mtime),
            })
        except OSError:
            continue

    files.sort(key=lambda x: x['mtime'], reverse=True)
    return files


def sync_buffers():
    """
    Принудительно сбрасывает буферы файловой системы на диск.
    Использует /usr/bin/sudo -n sync (по правилам в /etc/sudoers.d/myframework-mount).
    """
    try:
        result = subprocess.run(
            ['/usr/bin/sudo', '-n', 'sync'],
            capture_output=True,
            timeout=15
        )
        return result.returncode == 0
    except Exception:
        return False


def mount_disk(mount_point, device=None):
    """
    Монтирует внешний диск по конкретной точке монтирования.
    Опция device игнорируется (оставлена для совместимости).

    :return: {'ok': bool, 'error': str или None}
    """
    if is_mounted(mount_point):
        return {'ok': True, 'error': None, 'message': 'Диск уже смонтирован'}

    if not os.path.exists(mount_point):
        return {'ok': False, 'error': f'Точка монтирования не существует: {mount_point}'}

    try:
        # Монтируем конкретную точку (правило sudoers для /usr/bin/mount /mnt/backup).
        result = subprocess.run(
            ['/usr/bin/sudo', '-n', 'mount', mount_point],
            capture_output=True,
            timeout=30,
            text=True
        )

        if result.returncode != 0:
            error = result.stderr.strip() or 'Неизвестная ошибка mount'
            return {'ok': False, 'error': error}

        # Проверяем, что диск действительно смонтировался
        if not is_mounted(mount_point):
            return {
                'ok': False,
                'error': f'Диск не смонтирован после mount. '
                         f'Проверьте /etc/fstab и наличие устройства.'
            }

        return {'ok': True, 'error': None, 'message': 'Диск смонтирован'}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'Превышено время ожидания mount'}
    except Exception as e:
        return {'ok': False, 'error': f'Неожиданная ошибка mount: {e}'}


def unmount_disk(mount_point):
    """
    Безопасно отмонтирует внешний диск:
    1. sync — сбрасывает буферы на диск
    2. umount — отмонтирует

    :return: {'ok': bool, 'error': str или None}
    """
    if not is_mounted(mount_point):
        return {'ok': True, 'error': None, 'message': 'Диск уже отмонтирован'}

    # 1. Синхронизация буферов (не критично, если упадёт)
    sync_buffers()

    # 2. Отмонтирование
    try:
        result = subprocess.run(
            ['/usr/bin/sudo', '-n', 'umount', mount_point],
            capture_output=True,
            timeout=30,
            text=True
        )

        if result.returncode != 0:
            error = result.stderr.strip() or 'Неизвестная ошибка umount'
            return {'ok': False, 'error': error}

        return {'ok': True, 'error': None, 'message': 'Диск отмонтирован. Можно безопасно извлечь.'}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'Превышено время ожидания umount'}
    except Exception as e:
        return {'ok': False, 'error': f'Неожиданная ошибка umount: {e}'}