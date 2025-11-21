import datetime
import os

import cv2
from settings import save_path


class AsyncVideoWriter:
    def __init__(self, camera_key, fourcc=cv2.VideoWriter_fourcc(*'MJPG')):
        self.fourcc = fourcc
        self.camera_key = camera_key
        self.filename = self.get_filename(camera_key)
        self.video_writer = None
        self.frames_recorded = 0

    async def write_frame(self, frame):
        if self.video_writer is None:
            fshape = frame.shape
            fheight = fshape[0]
            fwidth = fshape[1]
            print(f'Пишем файл {self.filename}')
            self.video_writer = cv2.VideoWriter(self.filename, self.fourcc, 20.0, (fwidth, fheight))

        self.video_writer.write(frame)  # Запись кадра
        self.frames_recorded += 1

    async def stop_recording(self):
        if self.video_writer is not None:
            # If we're writing a file, close it
            self.video_writer.release()
            self.video_writer = None
            self.frames_recorded = 0
            print(f'Закрываем файл {self.filename}')

    @staticmethod
    def get_filename(camera_key: str):
        now = datetime.datetime.now()
        current_time = now.strftime('%Y-%m-%d_%H:%M:%S')
        path = os.path.join(save_path, camera_key, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, f'm_{current_time}.avi')
