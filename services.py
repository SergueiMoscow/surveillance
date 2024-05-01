import datetime
import os
import time
import psutil
import cv2
from settings import save_path


def get_filename(camera_key):
    now = datetime.datetime.now()
    current_time = now.strftime('%Y-%m-%d_%H:%M:%S')
    path = os.path.join(save_path, camera_key, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f'm_{current_time}.avi')


def cache_frames(camera_key: str, camera_source: str, last_frame: dict, running) -> None:
    """ Кэширование кадров """
    print('services.py, cache_frames, source:', camera_source)
    while running.value:
        cap = cv2.VideoCapture(camera_source)
        # cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) #в некоторых случаях это позволяет избавится от старых кадров
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
                        if cv2.contourArea(contour) < 1000:  # можно регулировать размер области детектирования
                            continue

                        (x, y, w, h) = cv2.boundingRect(contour)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        motion_detected = True

                # конец детекции
                # frame = cv2.resize(frame, (640, 360))  # Изменение размера кадра, по необходимости
                _, buffer = cv2.imencode(
                    '.jpg',
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                )  # Кодирование кадра в JPEG
                # Запись в файл
                if motion_detected and frames_recorded <= 500:  # Если обнаружено движение
                    if video_writer is None:  # Инициализировать записывающее устройство, если его нет
                        fshape = frame.shape
                        fheight = fshape[0]
                        fwidth = fshape[1]
                        fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # Вы можете выбрать кодек, который вам подходит
                        filename = get_filename(camera_key)
                        video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (fwidth, fheight))

                    video_writer.write(frame)  # Запись кадра
                    frames_recorded += 1

                else:  # Если нет движения
                    if video_writer is not None:  # Если записывающее устройство инициализировано
                        video_writer.release()  # Закрываем поток записи
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


# def decode(frame):
#     ret, jpeg = cv2.imencode('.jpg', frame)
#     return jpeg.tobytes()


def get_resource_usage():
    pid = os.getpid()
    py = psutil.Process(pid)

    memory_use = py.memory_info()[0] / 2. ** 30  # память в Гб
    cpu_use = py.cpu_percent(interval=1)  # процент использования процессора
    print(f'Memory: {memory_use}, cpu: {cpu_use}')
    return {
        "memory_use": memory_use,
        "cpu_use": cpu_use,
    }
