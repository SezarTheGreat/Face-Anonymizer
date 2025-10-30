import os
import cv2
import threading
import tempfile
import time
import logging
from flask import Flask, render_template, Response, request, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
import mediapipe as mp

UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi'}
BASE_DIR = os.path.dirname(__file__)

app = Flask(__name__)
app.secret_key = "replace-this-with-a-secret"
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # allow big uploads

# Face detection helper (kept global for reuse)
mp_face_detection = mp.solutions.face_detection

def process_image(img, face_detection):
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    out = face_detection.process(img_rgb)
    height_img, width_img, _ = img.shape

    if out.detections is not None:
        for detection in out.detections:
            bbox = detection.location_data.relative_bounding_box
            x1 = int(bbox.xmin * width_img)
            y1 = int(bbox.ymin * height_img)
            w = int(bbox.width * width_img)
            h = int(bbox.height * height_img)

            # clamp
            x1 = max(0, x1)
            y1 = max(0, y1)
            w = max(1, w)
            h = max(1, h)
            x2 = min(width_img, x1 + w)
            y2 = min(height_img, y1 + h)

            # heavy blur for anonymization
            roi = img[y1:y2, x1:x2]
            if roi.size != 0:
                k = (max(1, (w//3)|1), max(1, (h//3)|1))
                img[y1:y2, x1:x2] = cv2.blur(roi, k)
    return img

# Camera capture object (single shared camera)
class VideoCamera:
    def __init__(self, src=0):
        # open capture first, then verify it opened
        self.cap = cv2.VideoCapture(src)
        if not getattr(self, "cap", None) or not self.cap.isOpened():
            # try to clean up if partially opened
            try:
                if getattr(self, "cap", None):
                    self.cap.release()
            except Exception:
                pass
            raise RuntimeError("Could not start camera.")
        self.lock = threading.Lock()
        self.frame = None
        self.stopped = False
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while not self.stopped:
            # read() can block on some backends; check stopped between reads
            ret, frame = self.cap.read()
            if not ret:
                # small sleep to avoid busy loop when camera fails
                if self.stopped:
                    break
                continue
            with self.lock:
                self.frame = frame.copy()

    def get_frame(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def release(self):
        # mark stopped and release capture to allow _update to exit
        self.stopped = True
        try:
            if getattr(self, "cap", None):
                self.cap.release()
        except Exception:
            pass
        finally:
            # remove attribute so later recreations won't see stale state
            self.cap = None

camera = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/camera')
def camera_page():
    return render_template('camera.html')

def mjpeg_generator_raw(cam):
    try:
        while True:
            # stop if camera flagged stopped or capture closed
            if getattr(cam, "stopped", True):
                break
            frame = cam.get_frame()
            if frame is None:
                # yield a tiny pause to avoid 100% CPU
                time.sleep(0.01)
                continue
            _, jpeg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    except GeneratorExit:
        return
    except Exception:
        return

def mjpeg_generator_processed(cam):
    try:
        with mp_face_detection.FaceDetection(min_detection_confidence=0.5, model_selection=1) as face_detection:
            while True:
                # stop if camera flagged stopped or capture closed
                if getattr(cam, "stopped", True):
                    logging.info("Camera stopped, exiting processed generator")
                    break

                try:
                    frame = cam.get_frame()
                    if frame is None:
                        time.sleep(0.01)
                        continue

                    proc = process_image(frame.copy(), face_detection)
                    _, jpeg = cv2.imencode('.jpg', proc)
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                except Exception as e:
                    logging.exception("Error in processed frame loop: %s", e)
                    # break to let the client know the stream ended instead of silently hanging
                    break
    except GeneratorExit:
        logging.info("Processed generator closed by client")
        return
    except Exception as e:
        logging.exception("Unhandled exception in processed generator: %s", e)
        return

@app.route('/video_feed_raw')
def video_feed_raw():
    global camera
    if camera is None:
        try:
            camera = VideoCamera(0)
        except RuntimeError as e:
            return Response(f"Camera error: {e}", status=503, mimetype='text/plain')
    return Response(mjpeg_generator_raw(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_processed')
def video_feed_processed():
    global camera
    if camera is None:
        try:
            camera = VideoCamera(0)
        except RuntimeError as e:
            return Response(f"Camera error: {e}", status=503, mimetype='text/plain')
    return Response(mjpeg_generator_processed(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-cache'})

@app.route('/photo')
def photo_page():
    return render_template('photo.html')

@app.route('/process_photo', methods=['POST'])
def process_photo():
    if 'photo' not in request.files:
        flash("No file uploaded")
        return redirect(url_for('photo_page'))
    f = request.files['photo']
    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {'.jpg', '.jpeg', '.png'}:
        flash("Invalid image type")
        return redirect(url_for('photo_page'))

    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)  # close the OS handle so OpenCV / other code can open it on Windows
    try:
        f.save(path)
        img = cv2.imread(path)
        if img is None:
            flash("Could not read image")
            return redirect(url_for('photo_page'))

        with mp_face_detection.FaceDetection(min_detection_confidence=0.5, model_selection=1) as face_detection:
            out_img = process_image(img, face_detection)

        _, buffer = cv2.imencode('.jpg', out_img)
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    finally:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

@app.route('/video')
def video_page():
    return render_template('video.html')

@app.route('/process_video', methods=['POST'])
def process_video():
    if 'video' not in request.files:
        flash("No file uploaded")
        return redirect(url_for('video_page'))
    f = request.files['video']
    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {'.mp4', '.mov', '.avi'}:
        flash("Invalid video format")
        return redirect(url_for('video_page'))

    # create temp files safely on Windows (close fd right away)
    in_fd, in_path = tempfile.mkstemp(suffix=ext)
    os.close(in_fd)
    out_fd, out_path = tempfile.mkstemp(suffix='.mp4')
    os.close(out_fd)

    try:
        # save uploaded file to the closed temp path
        f.save(in_path)

        cap = cv2.VideoCapture(in_path)
        if not cap.isOpened():
            flash("Could not open uploaded video")
            try: os.unlink(in_path)
            except Exception: pass
            return redirect(url_for('video_page'))

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

        with mp_face_detection.FaceDetection(min_detection_confidence=0.5, model_selection=1) as face_detection:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                proc = process_image(frame, face_detection)
                out.write(proc)

        # make sure resources are released before deleting input
        cap.release()
        out.release()

        # schedule cleanup of output after download to avoid locking issues
        def remove_file_later(path, delay=30):
            def _remove():
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except Exception:
                    pass
            t = threading.Timer(delay, _remove)
            t.daemon = True
            t.start()

        # return file and remove input immediately
        try:
            os.unlink(in_path)
        except Exception:
            pass

        # remove output after 30s
        remove_file_later(out_path, delay=30)
        return send_file(out_path, as_attachment=True, download_name='anonymized_video.mp4')
    finally:
        # ensure input is removed if something failed
        try:
            if os.path.exists(in_path):
                os.unlink(in_path)
        except Exception:
            pass

@app.route('/shutdown_camera')
def shutdown_camera():
    global camera
    if camera is not None:
        try:
            camera.release()
        except Exception:
            pass
        camera = None
    return redirect(url_for('index'))

if __name__ == '__main__':
    # enable threaded so both raw and processed MJPEG streams can be served concurrently
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)