from VideoHandler import VideoHandler
from settings import cameras


for camera_key, camera_source in cameras.items():
    camera_key = camera_key
    camera_source = camera_source
    break

last_frame = {}


class Running:
    def __init__(self):
        self.value = True


running = Running()
video_processor = VideoHandler(camera_key, camera_source, last_frame, running)
video_processor.run()
