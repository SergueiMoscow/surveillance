import time

from flask import Response, Flask, render_template, jsonify
from multiprocessing import Process, Manager
from flask_cors import CORS

import settings
from src.handlers.archive_handler import ArchiveHandler
from src.handlers.http_video_handler import HTTPVideoHandler
from src.handlers.video_handler import VideoHandler
from services import get_resource_usage, is_running_in_docker, get_container_resource_usage
from settings import cameras, additional_cameras


app: Flask = Flask(__name__)
CORS(app)


@app.route('/')
def index():
    return render_template(
        'main.html',
        cameras=cameras,
        additional=additional_cameras
    )


@app.route("/video_feed/<camera_key>")
def video_feed(camera_key) -> Response:
    camera_source = cameras.get(camera_key) # Получаем источник камеры
    if not camera_source:
        return "Camera not found", 404  # Если камера не найдена, возвращаем 404
    return Response(
        generate(camera_key, last_frame),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route('/resources')
def resources():
    if is_running_in_docker():
        return jsonify(get_container_resource_usage())
    else:
        resource_usage = get_resource_usage(processes)
    return jsonify(resource_usage)


def generate(camera_key, shared_last_frame: dict):
    frame_data = None
    while True:
        new_frame_data = shared_last_frame.get(camera_key)
        if frame_data != new_frame_data:
            frame_data = new_frame_data
            if frame_data:  # Проверяем, есть ли данные кадра
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        time.sleep(1 / 15)


if __name__ == '__main__':
    with Manager() as manager:
        last_frame = manager.dict()  # Используем словарь для кэширования последних кадров
        running = manager.Value('i', 1)
        # Запуск процесса проверки размера архива
        archive_handler = ArchiveHandler(settings.save_path, settings.max_archive_size_gb)
        archive_process = Process(
            # target=asyncio.run,
            # args=(archive_handler.check_archive(),),
            target=archive_handler.check_archive,
            name='Archive_Manager_Process'
        )
        archive_process.start()
        print(f"Started {archive_process.name}")

        processes = []
        # Old version before refactor (12.05.2024)
        # for camera_key, camera_source in cameras.items():
        #     # Для каждой камеры создаём отдельный процесс
        #     p = Process(
        #         target=cache_frames,
        #         args=(camera_key, camera_source, last_frame, running),
        #         name=f'Process_{camera_key}',
        #     )
        #     p.start()
        #     print(f'Started process {p.name}')
        #     processes.append(p)

        for camera_key, camera_source in cameras.items():
            # Создаем объект для каждой камеры
            if camera_source.startswith('rtsp'):
                video_processor = VideoHandler(camera_key, camera_source, last_frame, running)
            elif camera_source.startswith('http'):
                video_processor = HTTPVideoHandler(
                    camera_key,
                    camera_source,
                    last_frame,
                    running,
                    interval = settings.http_request_interval
                )

            # Для каждой камеры создаём отдельный процесс
            p = Process(
                target=video_processor.run,
                name=f'Process_{camera_key}',
            )
            p.start()
            print(f'Started process {p.name}')
            processes.append(p)

        try:
            app.run(host='0.0.0.0', port=settings.port, debug=False, threaded=True, use_reloader=False)
        except KeyboardInterrupt:
            pass  # Обработка выхода по Ctrl+C
        finally:
            running.value = 0  # Завершение процессов
            for p in processes:
                p.join()
                p.terminate()
