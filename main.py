import time

from flask import Response, Flask, render_template, abort, jsonify
from multiprocessing import Process, Manager

from services import cache_frames, get_resource_usage
from settings import cameras


app: Flask = Flask(__name__)


@app.route('/')
def index():
    return render_template('main.html', cameras=cameras)


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
    resource_usage = get_resource_usage()
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
        last_frame = manager.dict()  # Теперь используем словарь для кэширования последних кадров
        running = manager.Value('i', 1)

        processes = []
        for camera_key, camera_source in cameras.items():
            # Для каждой камеры создаём отдельный процесс
            p = Process(target=cache_frames, args=(camera_key, camera_source, last_frame, running))
            p.start()
            processes.append(p)

        try:
            app.run(host='0.0.0.0', port=8000, debug=False, threaded=True, use_reloader=False)
        except KeyboardInterrupt:
            pass  # Обработка выхода по Ctrl+C
        finally:
            running.value = 0  # Завершение процессов
            for p in processes:
                p.join()
                p.terminate()
