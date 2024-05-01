""" Рабочий файл. Не трогать код. Можно менять камеры (source) """
import datetime

from flask import Response, Flask, render_template
from multiprocessing import Process, Manager
import time
import cv2

app: Flask = Flask(__name__)
# Road1
# source: str = 'rtsp://192.168.12.88:554/user=admin&password=17321111&channel=1&stream=1.sdp'
# Road2
source: str = "rtsp://admin:17321111@192.168.12.191:554/live/ch0"
# Balkon north
# source: str = 'rtsp://admin:admin@192.168.12.36/ch0_0.h264 admin/ss1732'
# Веранда
# source: str = 'rtsp://admin:17321111@192.168.12.52:554/live/ch1'
# Smart:
# source: str = 'http://admin:17321111@192.168.12.96/cgi-bin/video.cgi?camera=1&mode=1'


def get_filename():
    now = datetime.datetime.now()
    current_time = now.strftime('%Y-%m-%d_%H:%M:%S')
    return f'm_{current_time}.avi'


def cache_frames(source: str, last_frame: list, running) -> None:
    """ Кэширование кадров """
    cap = cv2.VideoCapture(source)
    # cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) #в некоторых случаях это позволяет избавится от старых кадров
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
                    filename = get_filename()
                    video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (fwidth, fheight))

                video_writer.write(frame)  # Запись кадра
                frames_recorded += 1

            else:  # Если нет движения
                if video_writer is not None:  # Если записывающее устройство инициализировано
                    video_writer.release()  # Закрываем поток записи
                    video_writer = None
                    frames_recorded = 0
            # Конец записи в файл
            last_frame[0] = buffer.tobytes()  # Кэширование кадра
        else:
            # Здесь можно обрабатывать ошибки захвата кадра
            break  # Если не удалось захватить кадр
        time.sleep(1 / (fps + 1))  # Интервал между кадрами
    cap.release()


def generate(shared_last_frame: list):
    """ Генератор кадров """
    frame_data = None
    while True:
        if frame_data != shared_last_frame[0]:  # Если кадр изменился
            frame_data = shared_last_frame[0]
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')  # HTTP ответ для потоковой передачи
        time.sleep(1 / 15)  # Задержка


@app.route("/")
def index() -> str:
    # Возвращаем отрендеренный шаблон
    return render_template("index.html")


@app.route("/video_feed")
def video_feed() -> Response:
    return Response(
        generate(last_frame),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )  # Запуск генератора


if __name__ == '__main__':
    with Manager() as manager:
        last_frame = manager.list([None])  # Кэш последнего кадра
        running = manager.Value('i', 1)  # Управляемый флаг для контроля выполнения процесса

        # Создаём процесс для кэширования кадров
        p = Process(target=cache_frames, args=(source, last_frame, running))
        p.start()

        # Запуск Flask-приложения в блоке try/except
        try:
            app.run(host='0.0.0.0', port=8000, debug=False, threaded=True, use_reloader=False)
        except KeyboardInterrupt:
            p.join()  # Ожидаем завершения процесса
        finally:
            running.value = 0  # Устанавливаем флаг в 0, сигнализируя процессу о необходимости завершения

        p.terminate()  # Принудительно завершаем процесс, если он все еще выполняется
        p.join()  # Убедимся, что процесс завершился
