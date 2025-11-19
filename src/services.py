import datetime
import os
import time

import asyncio

import docker
import psutil
import cv2

from src import settings
from src.video_writer import AsyncVideoWriter
from src.real_time_object_detection import object_detection
from src.settings import save_path


def get_filename(camera_key):
    now = datetime.datetime.now()
    current_time = now.strftime('%Y-%m-%d_%H:%M:%S')
    path = os.path.join(save_path, camera_key, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f'm_{current_time}.avi')


def cache_frames_old(camera_key: str, camera_source: str, last_frame: dict, running) -> None:
    """ Кэширование кадров """
    print('services.py, cache_frames, source:', camera_source)
    frame_count = 0
    cap = cv2.VideoCapture(camera_source)
    filename = ''
    while running.value:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # в некоторых случаях это позволяет избавится от старых кадров
        if not cap.isOpened():
            print(f"Не удается открыть поток камеры {camera_key}. Попытка переподключения через 60 секунд.")
            time.sleep(60)
            continue
        else:
            print(f'Камера {camera_key} подключена')
        fps = cap.get(cv2.CAP_PROP_FPS)
        dom_frame = None
        motion_detected = False
        video_writer = None
        frames_recorded = 0
        while running.value:
            ret, frame = cap.read()  # Чтение кадра
            frame_count += 1
            if frame_count % 10 != 0:  # Обработать каждый 10-й кадр
                continue
            if ret:  # Если кадр считан
                # Реализация детекции движения
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                # В первый раз устанавливаем доминантный кадр
                if dom_frame is None:
                    dom_frame = gray
                    continue

                frame_delta = cv2.absdiff(dom_frame, gray)
                thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)

                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours is not None:
                    for contour in contours:
                        if cv2.contourArea(contour) < 500:  # можно регулировать размер области детектирования
                            continue
                        if settings.display_frame_change_zones:
                            # Рисуем прямоугольники зон изменения кадра
                            (x, y, w, h) = cv2.boundingRect(contour)
                            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        motion_detected = True
                        break
                # конец детекции
                frame = cv2.resize(frame, (640, 360))  # Изменение размера кадра, по необходимости
                object_detected, new_frame = object_detection(frame)
                _, buffer = cv2.imencode(
                    '.jpg',
                    new_frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                )  # Кодирование кадра в JPEG
                # Запись в файл
                if motion_detected and frames_recorded <= 500:  # Если обнаружено движение
                    # detect objects:
                    if object_detected:
                        if video_writer is None:  # Инициализировать записывающее устройство, если его нет
                            video_writer = AsyncVideoWriter(camera_key)
                            asyncio.run(video_writer.write_frame(new_frame))

                        asyncio.run(video_writer.write_frame(new_frame))  # Запись кадра
                        frames_recorded += 1

                else:  # Если нет движения
                    if video_writer is not None:  # Если записывающее устройство инициализировано
                        asyncio.run(video_writer.stop_recording())
                        video_writer = None
                        frames_recorded = 0
                # Конец записи в файл
                last_frame[camera_key] = buffer.tobytes()  # Кэширование кадра
            else:
                print(f"Потеряно соединение с камерой {camera_key}. Попытка переподключения через 60 секунд.")
                cap.release()  # Высвобождаем захват перед тем, как пытаться переподключиться
                time.sleep(60)
                break  # Выходим
            time.sleep(1 / (fps + 1))  # Интервал между кадрами
        cap.release()


def is_running_in_docker():
    return os.path.isfile('/.dockerenv')


def get_resource_usage(processes, summary=True):
    total_memory_use = 0
    total_cpu_use = 0
    detail_usage = []
    py = None
    for p in processes:
        if p.is_alive():
            py = psutil.Process(p.pid)
            cpu_affinity = py.cpu_affinity()
            memory_use = py.memory_info()[0] / 2. ** 30  # память в Гб
            cpu_use = py.cpu_percent(interval=1)  # процент использования процессора
            total_memory_use += memory_use
            total_cpu_use += cpu_use / os.cpu_count()
            detail_usage.append({
                'pid': p.pid,
                'name': p.name,
                'memory_use': memory_use,
                'cpu_use': cpu_use,
                'cpu_affinity': cpu_affinity,
            })
    # print(detail_usage)
    # print('py:', py)
    if not summary:
        return detail_usage

    return {
        "total_memory_use": total_memory_use,
        "total_cpu_use": total_cpu_use,
    }


def calculate_cpu_percent(stats):
    cpu_percent = 0.0
    cpu_delta = float(stats['cpu_stats']['cpu_usage']['total_usage']) - float(stats['precpu_stats']['cpu_usage']['total_usage'])
    system_delta = float(stats['cpu_stats']['system_cpu_usage']) - float(stats['precpu_stats']['system_cpu_usage'])
    if system_delta > 0.0:
        cpu_percent = cpu_delta / system_delta * 100.0
    return cpu_percent


def get_container_resource_usage():
    container_id = os.getenv('HOSTNAME')
    client = docker.from_env()
    container = client.containers.get(container_id)
    stats_objects = container.stats(stream=False)
    cpu_stats = stats_objects['cpu_stats']
    mem_stats = stats_objects['memory_stats']
    net_stats = stats_objects['networks']
    memory_usage_in_gb = float(mem_stats['usage'] / (1024 ** 3))
    cpu_usage = calculate_cpu_percent(stats_objects)
    return {
        "total_memory_use": memory_usage_in_gb,
        "total_cpu_use": cpu_usage,
        "net_use": net_stats,
    }
