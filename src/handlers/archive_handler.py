import os
import time
from pathlib import Path
from typing import List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArchiveHandler:
    def __init__(self, path: str, max_size_gb: float):
        self.path = Path(path)
        self.max_size_gb = max_size_gb

        # Создаем директорию, если её нет
        self.path.mkdir(parents=True, exist_ok=True)

    def calculate_folder_size(self) -> float:
        """Вычисляет размер папки в гигабайтах (рекурсивно)"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(self.path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        if os.path.exists(filepath):
                            total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError) as e:
                        logger.warning(f"Не удалось получить размер файла {filepath}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при подсчете размера папки: {e}")

        return total_size / (1024 * 1024 * 1024)

    def get_all_files_with_mtime(self) -> List[Tuple[Path, float]]:
        """Получает список всех файлов с временем модификации (рекурсивно)"""
        files = []
        try:
            for dirpath, dirnames, filenames in os.walk(self.path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    try:
                        if filepath.exists():
                            mtime = filepath.stat().st_mtime
                            files.append((filepath, mtime))
                    except (OSError, FileNotFoundError) as e:
                        logger.warning(f"Не удалось получить информацию о файле {filepath}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при получении списка файлов: {e}")

        return files

    def delete_oldest_files(self, count: int = 1) -> int:
        """
        Удаляет самые старые файлы

        Args:
            count: количество файлов для удаления

        Returns:
            количество реально удаленных файлов
        """
        files = self.get_all_files_with_mtime()

        if not files:
            logger.warning("Нет файлов для удаления")
            return 0

        # Сортируем по времени модификации (самые старые первыми)
        files.sort(key=lambda x: x[1])

        deleted_count = 0
        for filepath, _ in files[:count]:
            try:
                filepath.unlink()
                logger.info(f"Удален файл: {filepath}")
                deleted_count += 1

                # Удаляем пустые директории
                self._remove_empty_dirs(filepath.parent)
            except (OSError, FileNotFoundError) as e:
                logger.error(f"Не удалось удалить файл {filepath}: {e}")

        return deleted_count

    def _remove_empty_dirs(self, directory: Path):
        """Удаляет пустые директории (рекурсивно вверх до self.path)"""
        try:
            if directory == self.path or not directory.is_relative_to(self.path):
                return

            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
                logger.info(f"Удалена пустая директория: {directory}")
                # Рекурсивно проверяем родительскую директорию
                self._remove_empty_dirs(directory.parent)
        except Exception as e:
            logger.debug(f"Не удалось удалить директорию {directory}: {e}")

    def cleanup_by_size(self):
        """Удаляет старые файлы, пока размер не станет меньше лимита"""
        size = self.calculate_folder_size()

        if size <= self.max_size_gb:
            return

        logger.warning(
            f"Размер архива ({size:.2f} GB) превышает лимит ({self.max_size_gb} GB). "
            "Начинаю удаление старых файлов..."
        )

        # Удаляем файлы порциями для эффективности
        batch_size = 10
        while size > self.max_size_gb:
            deleted = self.delete_oldest_files(batch_size)
            if deleted == 0:
                logger.error("Не удалось удалить файлы, но лимит все еще превышен")
                break

            size = self.calculate_folder_size()
            logger.info(f"Текущий размер архива: {size:.2f} GB")

    def check_archive(self, interval_seconds: int = 60):
        """
        Основной цикл мониторинга архива

        Args:
            interval_seconds: интервал проверки в секундах
        """
        logger.info(
            f"Запущен мониторинг архива: путь={self.path}, "
            f"лимит={self.max_size_gb} GB, интервал={interval_seconds}s"
        )

        while True:
            try:
                size = self.calculate_folder_size()
                logger.info(f"Текущий размер архива: {size:.2f} GB / {self.max_size_gb} GB")

                self.cleanup_by_size()

            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")

            time.sleep(interval_seconds)


if __name__ == "__main__":
    # Тест
    handler = ArchiveHandler("./test_archive", max_size_gb=0.001)  # 1 MB для теста

    # Создаем тестовые файлы
    test_dir = Path("./test_archive/2024/01")
    test_dir.mkdir(parents=True, exist_ok=True)

    for i in range(5):
        test_file = test_dir / f"video_{i}.txt"
        test_file.write_text("x" * 1024 * 500)  # 500 KB каждый
        time.sleep(0.1)

    print(f"Размер до очистки: {handler.calculate_folder_size():.4f} GB")
    handler.cleanup_by_size()
    print(f"Размер после очистки: {handler.calculate_folder_size():.4f} GB")