import cv2
import os
import mediapipe as mp
import argparse

def process_image(img,face_detection):
    img_rgb = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    out = face_detection.process(img_rgb)
    
    height_img, width_img, _ = img.shape

    if out.detections is not None:
        for detection in out.detections:
            location_data = detection.location_data
            bbox = location_data.relative_bounding_box

            x1 , y1, w, h = bbox.xmin,bbox.ymin,bbox.width,bbox.height

            x1 = int(x1*width_img)
            y1 = int(y1*height_img)
            w = int(w*width_img)
            h = int(h*height_img)

            # img = cv2.rectangle(img,(x1,y1),(x1+w,y1+h),(0,255,0),10)
            img[y1:y1+h,x1:x1+w,:] = cv2.blur(img[y1:y1+h,x1:x1+w,:],(1000,1000))
    return img

image_name = "Face_video.jpg"
parser = argparse.ArgumentParser(description="Choose mode: image, video or webcam")
parser.add_argument("--mode", choices=["image", "video", "webcam"], help="mode to run")
parser.add_argument("--filePath", help="path to image or video file (required for image/video)")
parsed = parser.parse_args()

# If no mode provided on CLI, ask interactively
if not parsed.mode:
    print("Select mode:")
    print("  1) image")
    print("  2) video")
    print("  3) webcam")
    choice = input("Enter 1/2/3: ").strip()
    mode_map = {"1": "image", "2": "video", "3": "webcam"}
    mode = mode_map.get(choice)
    if not mode:
        print("Invalid choice, exiting.")
        raise SystemExit(1)
else:
    mode = parsed.mode

# For image/video ask for file path if not provided
filePath = parsed.filePath
if mode in ("image", "video"):
    if not filePath:
        filePath = input("Enter path to the file: ").strip()
    # normalize relative to script directory
    if not os.path.isabs(filePath):
        filePath = os.path.join(os.path.dirname(__file__), filePath)
    if not os.path.exists(filePath):
        print(f"Error: file not found: {filePath}")
        raise SystemExit(1)

# attach back to args-like names used later
args = argparse.Namespace(mode=mode, filePath=filePath)

output_dir = "./output"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

#Face detection
mp_face_detection = mp.solutions.face_detection

with mp_face_detection.FaceDetection(min_detection_confidence = 0.5,model_selection = 1) as face_detection:
    
    if args.mode in ["image"]:
        # read image
        img = cv2.imread(args.filePath)
        if img is None:
            print(f"Error: could not load image '{args.filePath}'")
            raise SystemExit(1)
        img = process_image(img,face_detection)

        cv2.imshow("img", img)
        cv2.imwrite(os.path.join(output_dir, f"Anonymized_{image_name}"),img)
        cv2.waitKey(0)

    elif args.mode in ['video']:
        cap = cv2.VideoCapture(args.filePath)
        if not cap.isOpened():
            print(f"Error: cannot open video/file '{args.filePath}'")
            raise SystemExit(1)

        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"Error: can't read first frame from '{args.filePath}'")
            cap.release()
            raise SystemExit(1)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output_path = os.path.join(output_dir, "Output.mp4")
        out = cv2.VideoWriter(output_path, fourcc, fps, (frame.shape[1], frame.shape[0]))

        while ret:
            proc = process_image(frame.copy(), face_detection)
            out.write(proc)
            cv2.imshow("Anonymized", proc)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            ret, frame = cap.read()

        cap.release()
        out.release()
    
    elif args.mode in ['webcam']:
        cap = cv2.VideoCapture(0)

        ret, frame = cap.read()

        while ret:
            frame = process_image(frame,face_detection)

            cv2.imshow('frame',frame)
            cv2.waitKey(25)

            ret,frame = cap.read()
            if cv2.waitKey(40) & 0xFF == ord('q'):
                break

            cap.release()

cv2.destroyAllWindows()