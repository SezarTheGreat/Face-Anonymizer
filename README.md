# Face Anonymizer

A lightweight tool to anonymize faces in images, videos and live webcam using MediaPipe for face detection and OpenCV for image/video processing.

This repository contains:
- `main.py` — core CLI program (image / video / webcam modes). Focus of this README.
- `app.py` — optional Flask web UI (live side‑by‑side camera, upload pages).
- `templates/`, `static/` — web UI assets.
- `requirements.txt` — Python dependencies.
- `package.json`, `testsprite.json` — visual test config (optional).

Repository: https://github.com/SezarTheGreat/Face-Anonymizer

---

## Quick summary / scope

The project provides:
- Real‑time anonymization of a webcam feed (blurred faces).
- Side‑by‑side raw vs processed camera (in the Flask UI).
- Server‑side image and video anonymization for uploaded files.
- Snapshot download of the current processed camera frame.
- Windows-safe temp file handling and basic visual test scaffolding.

This README focuses on running `main.py` locally (the core program).

---

## Technologies used

- Python (3.8–3.11 recommended)
- OpenCV (cv2) — capture, encode, blur
- MediaPipe — face detection
- Flask — web UI (optional)
- HTML / CSS / JavaScript — UI
- Node.js + testsprite — visual testing (optional)
- git

---

## Requirements

Install dependencies (recommended in a virtual environment):

requirements.txt example:
```
flask
opencv-python
mediapipe
werkzeug
numpy
```

Install via pip:
```powershell
pip install -r requirements.txt
```
Or individually:
```powershell
pip install flask opencv-python mediapipe werkzeug numpy
```

Node (for testsprite):
- Node.js v14+ and npm (optional)

---

## Setup (Windows PowerShell)

1. Clone the repo and enter project folder:
```powershell
cd "C:\Users\user\Desktop"
git clone https://github.com/SezarTheGreat/Face-Anonymizer.git
cd Face-Anonymizer
```

2. Create & activate a Python virtual environment:
```powershell
python -m venv myenv
.\myenv\Scripts\Activate.ps1
```

3. Install Python deps:
```powershell
pip install -r requirements.txt
```

4. (Optional) Install Node deps for visual tests:
```powershell
npm install
```

---

## main.py — usage (core CLI)

`main.py` supports three modes: `image`, `video`, `webcam`.

General form:
```powershell
python main.py --mode <image|video|webcam> [--filePath <path>]
```

Examples:

- Image
```powershell
python main.py --mode image --filePath ./Input/example.jpg
```
Behavior:
- Reads the image, detects faces via MediaPipe and blurs each detected face region with OpenCV.
- Displays the result window and saves output to `./output/Anonymized_<image_name>`.

- Video
```powershell
python main.py --mode video --filePath ./Input/example.mp4
```
Behavior:
- Opens the video file, reads the first frame to determine size & FPS, creates a VideoWriter, processes each frame and writes anonymized frames to `./output/Output.mp4`.
- Press `q` (when window focused) to stop early.

- Webcam (device 0)
```powershell
python main.py --mode webcam
```
Behavior:
- Opens system camera (device 0), processes frames in real time and shows processed frames.
- Press `q` to quit and release the camera.

Notes:
- If you run without `--mode`, the script prompts to select mode interactively.
- If filePath is omitted for image/video, the script will prompt for a file path.

---

## How the anonymization works (main.py internals)

Core function: `process_image(img, face_detection)`

Steps:
1. Convert BGR → RGB (MediaPipe expects RGB).
2. Run `face_detection.process(img_rgb)` to get detections.
3. For each detection:
   - Convert relative bounding box coordinates to pixel coordinates using image width/height.
   - Clamp coordinates to image bounds.
   - Apply a strong blur (OpenCV `cv2.blur`) to the region-of-interest (ROI) to anonymize the face.
4. Return the modified BGR image.

Important details implemented in `main.py`:
- Validates file paths and successful reads (avoids cv2.imread returning `None`).
- In video mode, reads the first frame to set output size and FPS, checks `cap.isOpened()`.
- In webcam mode, checks `cap.isOpened()` and uses a single `cv2.waitKey(1)` loop; releases the camera on exit.
- Uses MediaPipe FaceDetection with `min_detection_confidence=0.5` and `model_selection=1` (configurable).

---

## Output locations

- Processed images: `./output/Anonymized_<image_name>` (image_name is defined in `main.py`).
- Processed videos: `./output/Output.mp4`.

---

## Troubleshooting

- MediaPipe import error:
  - Ensure `mediapipe` is installed in the active Python environment: `pip install mediapipe`.
  - Check Python version compatibility if install fails.

- cv2.imread returns None:
  - Verify the path; use absolute paths or ensure relative path is correct w.r.t. `main.py` folder.

- PermissionError on Windows (temp files / uploads):
  - Use `tempfile.mkstemp()` + `os.close(fd)` pattern (used in the Flask app) to avoid files locked by Python handles.
  - Ensure the app closes/release VideoCapture/VideoWriter objects before deleting files.

- Camera can't open (webcam):
  - Ensure no other application is using the camera (browser tabs, Zoom, other apps).
  - If multiple cameras exist, adjust `cv2.VideoCapture(0)` index.

- Processed feed not showing in Flask UI:
  - Start Flask with `threaded=True` to allow concurrent MJPEG streams.
  - Check server logs for exceptions from the processed generator (they are logged).

---

## Flask UI & snapshot (optional)

Run the Flask app (if included in repo):

```powershell
python app.py
```

Open: `http://127.0.0.1:5000`

Pages:
- `/camera` — side‑by‑side raw and processed streams, Save Snapshot button downloads current anonymized frame.
- `/photo` — upload image, receive anonymized image.
- `/video` — upload video, receive anonymized video.

Stop camera: use Stop Camera button (releases camera and redirects home).

---

## Visual testing (testsprite) — optional

1. Ensure Node.js + npm installed.
2. Install deps:
```powershell
npm install
```
3. Start Flask app (so pages are reachable).
4. Create baseline:
```powershell
npm run testsprite:baseline
```
5. Compare:
```powershell
npm run testsprite:compare
```

---

## File structure (important files)

- `main.py` — core CLI program (focus of this README)
- `app.py` — Flask UI server (optional)
- `templates/`, `static/` — web UI
- `requirements.txt`
- `package.json`, `testsprite.json`

---

## Contributing

- Create a branch: `git checkout -b feat/your-change`
- Commit changes, push and open a PR.
- Follow existing patterns: safe temp handling, proper resource release, logging exceptions.

---

## License

MIT (add LICENSE file if not present).

---

## Contact / Issues

Report issues on the repository Issues page:
https://github.com/SezarTheGreat/Face-Anonymizer/issues

---