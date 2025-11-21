import cv2
import asyncio
import time

import numpy as np

import settings
from video_writer import AsyncVideoWriter
from real_time_object_detection import object_detection


class VideoHandler:
    def __init__(self, camera_key: str, camera_source: str, last_frame: dict, running):
        self.camera_key = camera_key
        self.camera_source = camera_source
        self.last_frame = last_frame
        self.running = running

        self.frame_count = 0
        self.capture = None
        self.fps = 0
        self.previous_gray_frame = None
        self.video_writer = None
        self.frames_recorded = 0
        self.motion_detected = False

    def _create_capture(self):
        """ Создание объекта VideoCapture """
        self.capture = cv2.VideoCapture(self.camera_source)

    def _setup_frame(self):
        if not self.capture.isOpened():
            print(f"Не удается открыть поток камеры {self.camera_key}. Попытка переподключения через 60 секунд.")
            self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        else:
            print(f'Камера {self.camera_key} подключена')
        self.previous_gray_frame = None
        self.previous_color_frame = None
        self.video_writer = None
        self.frames_recorded = 0
        self.counter_equal_frames = 0

    def _retrieve_frame(self):
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # избавляемся от старых кадров
        ret, frame = self.capture.read()  # Чтение кадра
        if np.array_equal(frame, self.previous_color_frame):
            if self.counter_equal_frames > 20:
                print(f'Equal: {self.counter_equal_frames}')
            self.counter_equal_frames += 1
        else:
            self.counter_equal_frames = 0
        self.previous_color_frame = frame
        return ret, frame

    def _frame_to_gray(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        return gray

    def _motion_detected(self, frame):
        gray = self._frame_to_gray(frame)

        # В первый раз устанавливаем доминантный кадр
        if self.previous_gray_frame is None:
            self.previous_gray_frame = gray
            return frame

        frame_delta = cv2.absdiff(self.previous_gray_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.motion_detected = False
        if contours is not None:
            for contour in contours:
                contour_area = cv2.contourArea(contour)
                if contour_area < settings.min_detection_aria:  # можно регулировать размер области детектирования
                    return frame
                if settings.display_frame_change_zones:
                    # Рисуем прямоугольники зон изменения кадра
                    (x, y, w, h) = cv2.boundingRect(contour)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                self.motion_detected = True
        self.previous_gray_frame = gray
        return frame

    def _manage_recording(self, objects_detected, new_frame):
        if self.motion_detected and self.frames_recorded <= 500:  # Если обнаружено движение
            # detect objects:
            if objects_detected:
                if self.video_writer is None:  # Инициализировать записывающее устройство, если его нет
                    self.video_writer = AsyncVideoWriter(self.camera_key)
                    asyncio.run(self.video_writer.write_frame(new_frame))

                asyncio.run(self.video_writer.write_frame(new_frame))  # Запись кадра
                self.frames_recorded += 1

        else:  # Если нет движения
            if self.video_writer is not None:  # Если записывающее устройство инициализировано
                asyncio.run(self.video_writer.stop_recording())
                self.video_writer = None
                self.frames_recorded = 0

    def run(self):
        self._create_capture()
        self._setup_frame()

        print('services.py, cache_frames, source:', self.camera_source)
        # while self.running.value:

        while self.running.value:
            ret, frame = self._retrieve_frame()

            self.frame_count += 1
            if ret:  # Если кадр считан
                if self.frame_count % (settings.number_of_skip_frames + 1) != 0:  # пропуск кадров
                    continue
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
            else:
                print(f"Потеряно соединение с камерой {self.camera_key}. Попытка переподключения через 60 секунд.")
                self.capture.release()  # Высвобождаем захват перед тем, как пытаться переподключиться
                time.sleep(60)
                self._create_capture()
                self._setup_frame()
            time.sleep(1 / (self.fps + 1))  # Интервал между кадрами
        self.capture.release()
