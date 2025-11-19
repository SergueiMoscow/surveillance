import time

import cv2
import numpy as np
import requests

from src.handlers.video_handler import VideoHandler
from src.real_time_object_detection import object_detection


class HTTPVideoHandler(VideoHandler):
    """
    Для камер, которые отдают только картинку
    """
    # Запрос к камере в секундах
    interval = 1

    def __init__(self, camera_key: str, camera_source: str, last_frame: dict, running, interval):
        super().__init__(camera_key, camera_source, last_frame, running)
        self.interval = interval

    def _setup_frame(self):
        self.previous_gray_frame = None
        self.previous_color_frame = None
        self.video_writer = None
        self.frames_recorded = 0
        self.counter_equal_frames = 0

    def _retrieve_frame(self):
        try:
            response = requests.get(self.camera_source, stream=True)
            response.raise_for_status()

            # Конвертируем ответ в массив numpy
            arr = np.asarray(bytearray(response.content), dtype=np.uint8)
            # Декодируем изображение из массива
            frame = cv2.imdecode(arr, -1)
            if np.array_equal(frame, self.previous_color_frame):
                if self.counter_equal_frames > 20:
                    print(f'Equal: {self.counter_equal_frames}')
                self.counter_equal_frames += 1
            else:
                self.counter_equal_frames = 0
            self.previous_color_frame = frame

            return frame

        except requests.RequestException as e:
            print(f'Error retrieving frame: {e}')
            return None

    def run(self):
        print('Running camera with HTTPVideoSource')
        self._setup_frame()
        while self.running.value:
            time.sleep(self.interval)
            frame = self._retrieve_frame()

            # Если не удалось извлечь кадр, пропустить оставшуюся часть цикла
            if frame is None:
                continue

            self.frame_count += 1
            # Тут остается логика детекции движения/объектов из метода run() родительского класса,
            # но теперь с кадром, полученным через HTTP

            # Реализация детекции движения
            frame = self._motion_detected(frame)
            # конец детекции
            frame = cv2.resize(frame, (640, 360))  # Изменение размера кадра, по необходимости
            objects_detected, new_frame = object_detection(frame)
            _, buffer = cv2.imencode(
                '.jpg',
                new_frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )  # Кодирование кадра в JPEG
            self._manage_recording(objects_detected, new_frame)
            self.last_frame[self.camera_key] = buffer.tobytes()  # Кэширование кадра
