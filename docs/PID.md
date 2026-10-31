# Project Identity Document (PID) — AI Study Focus Monitor

## 1. Project Overview & Identity
* **Official Project Name:** AI Study Focus Monitor
* **Repository Name:** `modal-object`
* **Version:** 2.0.0-rc1
* **Primary Role:** Real-Time Upper-Body Study Behavior Recognition, Ergonomic & Fatigue Tracking, and Context-Aware Audio Coaching System.

---

## 2. Problem Statement
Traditional webcam-based study monitors and proctoring tools suffer from critical architectural and perceptual flaws:
1. **Binary & Naive Rule Engines:** Naive systems equate looking down (head pitch down) with sleeping or laziness, triggering false drowsiness alarms when the student is actually typing, taking notes, or reading a textbook.
2. **Detection-to-Action Disconnect:** Models often detect objects or face states, but timer resets on consecutive frames or stride intervals prevent alerts from firing.
3. **Audio Alert Chaos:** Alerts overlap simultaneously or repeat indefinitely after the student has resumed productive studying.
4. **Environment Rigidity:** Stiff geometric rules fail across varying desk heights, laptop angles, and camera fields-of-view without personal calibration.
5. **Privacy Concerns:** Heavy cloud upload of student video feeds compromises user privacy.

---

## 3. Core Objectives
1. **Context-Aware Study Perception:** Discriminate between legitimate study behaviors (typing, reading, writing, quiet reflection, mathematical problem solving) and off-task behaviors (prolonged idle staring, mobile phone browsing, repeated room scanning, deliberate face concealment).
2. **Accurate Fatigue Recognition:** Separate normal physiological blinks (100–400ms) and head tilts from genuine fatigue indicators (sustained eye closure > 1.8s, repeated head droops, yawning with wide mouth aspect ratio, eye-rubbing).
3. **Traceable Behavioral Pipeline:** Maintain an auditable event flow:
   `Camera Frame → Multi-Model Perception → Validated Observations → Temporal Tracker → State Decision → Alert Policy → Audio Controller → Live Dashboard`.
4. **Dual Execution Modes:**
   * **Mode A (Local OpenCV Mode):** Native terminal execution with OpenCV preview, on-screen diagnostic HUD, and local Pygame sound playback.
   * **Mode B (Web Dashboard Mode):** Modern browser dashboard connecting via low-latency WebSockets to a local FastAPI backend with browser-native camera handling and audio playback.
5. **Edge & Privacy First:** All inference runs 100% locally on localhost (CPU / CUDA GPU). No raw video or private webcam streams are transmitted to third-party cloud servers.

---

## 4. Main Features

### 4.1 Multi-Model Perception Subsystem
* **YOLOv8 Detection:** Detects `person`, `cell phone`, `book`, and `laptop` with persistent stride caching.
* **MediaPipe Dense Face Mesh (478 Landmarks):**
  * 3D head pose estimation (yaw, pitch, roll) via `cv2.solvePnP` with canonical 3D facial model points.
  * Eye Aspect Ratio (EAR) with downward head pitch foreshortening compensation.
  * Mouth Aspect Ratio (MAR) for automated yawn detection.
* **MediaPipe Lite Pose Estimation:** Tracks shoulders, neck posture, and upper-body lean baseline.
* **MediaPipe Hands Tracking:** Detects hand interactions near the lower border (typing/writing), hands resting at chin (thinking), eye-rubbing, and hands covering face.

### 4.2 Temporal Decision Engine & State Machine
* **Multi-Label Active Behaviors:** Tracks co-occurring behaviors rather than forcing mutually exclusive states prematurely.
* **Persistent Duration Timers:** Monotonic timestamps ensure timers never reset on single-frame detection dropouts or inference stride gaps.
* **Hysteresis & Recovery Stability:** Transitions out of alert states require configurable clean study persistence (`RECOVERY_STABILITY_SECS = 1.2s`) before returning to `STUDYING`.

### 4.3 Centralized Alert & Audio Management
* **Priority-Based Audio Arbitration:**
  1. Priority 1: `CAMERA_ERROR` (technical notification)
  2. Priority 2: `STUDENT_ABSENT` (presence reminder)
  3. Priority 3: `FACE_OCCLUDED` (face visibility audio)
  4. Priority 4: `POSSIBLE_DROWSINESS` (alertness reminder)
  5. Priority 5: `DISTRACTED` / `INACTIVITY_WARNING` (focus reminder)
* **Preemption & Recovery Stopping:** Higher-priority alerts interrupt lower-priority audio clips; returning to clean study immediately stops active alert sounds.

### 4.4 Live Intelligence Web Dashboard
* Real-time webcam video feed with WebRTC `getUserMedia()`.
* Authoritative primary state and confidence level.
* **"WHY DID THE AI MAKE THIS DECISION?"** reasoning breakdown exposing:
  * Primary Observation
  * Additional Multimodal Evidence
  * Primary Decision
  * Audio Action
* Independent behavioral signals indicators (face, occlusion, person, head direction, eye state, study activity, inactivity duration, hand position, camera health).
* Dynamic, constructive **"What should I do now?"** recommendations.
* Personal workspace calibration wizard to baseline natural sitting angle and head pitch.

---

## 5. Technology Stack
* **Language:** Python 3.11+
* **Backend Framework:** FastAPI, Uvicorn (ASGI), WebSockets, Pydantic v2
* **Computer Vision & ML:**
  * OpenCV (`opencv-python` / `opencv-contrib-python` 5.0+)
  * PyTorch 2.5.1 with CUDA 12.1 acceleration
  * Ultralytics YOLOv8 (`yolov8n.pt`)
  * Google MediaPipe (`face_landmarker.task`, `pose_landmarker.task`, `hand_landmarker.task`)
* **Audio Engine:** Pygame Mixer (Local Mode) / HTML5 Web Audio API (Web Mode)
* **Frontend:** Vanilla JavaScript (ES Modules), Modern Responsive CSS3 (Dark Theme), Vite 5.4 build tooling
* **Platform:** Windows 10/11 (with cross-platform Linux/macOS readiness)

---

## 6. Hardware & Environment Requirements
* **Minimum CPU:** Quad-core x86_64 processor (Intel Core i5 8th gen / AMD Ryzen 5).
* **Recommended GPU:** NVIDIA GeForce GTX 1650 or higher (CUDA support enabled).
* **RAM:** 8 GB minimum (16 GB recommended).
* **Camera:** USB Webcam or Integrated Laptop Camera (720p / 1080p, 15–30 FPS).
* **Audio:** Stereo speakers / headphones.

---

## 7. Current Project Maturity
* **Perception Engine:** Complete & Verified (MediaPipe + YOLOv8 + SolvePnP).
* **Temporal Decision Engine:** Complete & Verified with 19 critical regression suites passing.
* **Local Mode (OpenCV):** Operational via `python run_webcam_yolo.py` and `python run_app.py --mode local`.
* **Web Dashboard Mode:** Operational via FastAPI backend (`http://127.0.0.1:8000/`) and Vite frontend (`http://127.0.0.1:5173/`).
* **Evaluation Status:** 0.00 False Alarms/hr on baseline reading evaluation suite, 98.5% reading accuracy.

---

## 8. Non-Goals
* Cloud-hosted video recording or streaming to external servers.
* Surveillance, grading, punitive monitoring, or biometric identity authentication.
* Medical diagnosis of sleep disorders, attention deficit disorders, or cognitive conditions.

