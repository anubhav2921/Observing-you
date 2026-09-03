import cv2
import time
import torch
import sys

# ==========================================
# Evil Eye: Live Object Detection Module
# Configuration
# ==========================================
CAMERA_INDEX = 0  # Change to 1 or other indices if default camera fails

print("Loading YOLO model...")
try:
    from ultralytics import YOLO
except ImportError:
    print("\n[ERROR] The 'ultralytics' library is not installed in this environment.")
    print("Please install it by running the following command in your terminal:")
    print("  .venv\\Scripts\\pip.exe install ultralytics\n")
    sys.exit(1)

# Check if CUDA (GPU) is available for PyTorch
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {device.upper()}")

# Load the lightweight pretrained YOLOv8 Nano model (weights will download automatically)
model = YOLO("yolov8n.pt").to(device)

print("Opening camera...")
cap = cv2.VideoCapture(CAMERA_INDEX)

# Handle camera-access failure with clear instructions
if not cap.isOpened():
    print(f"\n[ERROR] Could not open camera. Try camera index 1 or check Windows camera permissions.")
    print(f"Currently attempted index: CAMERA_INDEX = {CAMERA_INDEX}")
    sys.exit(1)

# Query and display camera input resolution
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera resolution: {width}x{height}")
print("Press Q to quit\n")

# Variables for tracking real-time FPS
prev_time = 0
fps = 0.0

# Live frame-processing loop
while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Failed to capture frame from webcam.")
        break

    # Calculate real-time FPS using simple moving average
    curr_time = time.time()
    time_diff = curr_time - prev_time if prev_time > 0 else 0
    prev_time = curr_time
    if time_diff > 0:
        fps = 0.9 * fps + 0.1 * (1.0 / time_diff) if fps > 0 else (1.0 / time_diff)

    # Run YOLO inference
    # stream=True processes generator results iteratively (avoids building a huge list in memory)
    # verbose=False prevents console spam during execution
    results = model(frame, verbose=False, stream=True)

    # Annotate frame with detections
    for result in results:
        boxes = result.boxes
        for box in boxes:
            # Box corners (xmin, ymin, xmax, ymax)
            x1, y1, x2, y2 = box.xyxy[0]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

            # Class label and confidence
            conf = float(box.conf[0])
            class_id = int(box.cls[0])
            label = model.names[class_id]

            # Draw bounding box (Bright green, width 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw text label background and score text above box
            caption = f"{label} {conf:.2f}"
            (text_w, text_h), baseline = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - text_h - 6), (x1 + text_w, y1), (0, 255, 0), cv2.FILLED)
            cv2.putText(frame, caption, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    # Render FPS counter (Cyan text, top-left corner)
    fps_text = f"FPS: {fps:.1f}"
    cv2.putText(frame, fps_text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)

    # Show video window
    cv2.imshow("Evil Eye Live Object Detection (YOLOv8)", frame)

    # Break loop cleanly if 'q' or 'Q' is pressed
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == ord('Q'):
        print("Quitting live detection feed...")
        break

# Release system resources
cap.release()
cv2.destroyAllWindows()
print("Camera released. Exited cleanly.")
