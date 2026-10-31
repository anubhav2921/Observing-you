# Live Project Status (CURRENT_STATUS) — AI Study Focus Monitor

*Last Updated:* 2026-10-31T18:35:00+05:30  
*Project Version:* 2.8.0  
*Current Development Phase:* Eye-Focused Detection, Performance & Drowsiness Accuracy (v2.8.0)

---

## 1. Subsystem Health & Status Summary

| Subsystem | Status | Host / Port / Details |
| :--- | :---: | :--- |
| **Backend REST API** | **OPERATIONAL** | `http://127.0.0.1:8000/api/health` returning `200 OK` |
| **WebSocket Streaming** | **OPERATIONAL** | `ws://127.0.0.1:8000/ws/monitor` with flow-control ACKs |
| **Web Dashboard UI** | **OPERATIONAL** | `http://127.0.0.1:8000/` (FastAPI production) & `http://127.0.0.1:5173/` (Vite) |
| **Mode A (OpenCV Local)** | **OPERATIONAL** | Terminal execution via `python run_app.py --mode local` |
| **Safe Diagnostic Mode** | **OPERATIONAL** | Terminal execution via `python run_app.py --diagnostic` (all audio alerts muted) |
| **YOLOv8 Detection** | **OPERATIONAL** | `yolov8n.pt` loaded in CUDA/CPU with stride caching |
| **MediaPipe Mesh/Pose/Hands** | **OPERATIONAL** | 478 face pts, 3D blendshapes (eyeBlinkLeft/Right), Eye landmarks only (pose disabled for 30+ FPS) |
| **Student Behaviour Taxonomy** | **OPERATIONAL** | 11 Parent categories, Granular phone interaction (`PHONE_VISIBLE`, `PHONE_HELD`, `PHONE_IN_USE`, `PHONE_CONFIRMED`) |
| **Audio Alert Subsystem** | **OPERATIONAL** | Priority preemption active (P1–P5) with ongoing alert persistence & deduplication |
| **Personal Calibration** | **OPERATIONAL** | Baseline head pitch/yaw/framing/EAR calibration wizard active |
| **Automated Test Suite** | **OPERATIONAL** | 94/94 tests passing (100% across unit, integration, accuracy, behavior policy, and websocket suites) |

---

## 2. Working Features
1. **Context-Aware Study Behavior Recognition:**
   * Distinguishes looking down typing (`STUDYING_TYPING_WRITING`), looking down reading (`STUDYING_READING`), screen study (`STUDYING`), and quiet contemplation.
   * Head-pitch compensation prevents downward typing/reading from false drowsiness classification.
2. **Fatigue & Drowsiness Tracking:**
   * Prolonged eye closure (> 1.8s) and repeated head droops trigger `POSSIBLE_DROWSINESS`.
   * Mouth Aspect Ratio (MAR > 0.48) tracks yawn frequency without misclassifying single yawns as sleep.
3. **Distraction & Inactivity Arbitration:**
   * Persistent `_phone_start` detects mobile device usage across YOLO strides (> 4.0s).
   * Sustained idle camera staring (> 12.0s) triggers `INACTIVITY_WARNING`.
   * Repeated room scanning (> 3.0s) triggers `LOOKING_AWAY`.
4. **Face Concealment & Absence:**
   * Anatomical head-box estimation reliably identifies deliberate face coverage (> 3.5s) even when FaceMesh drops out.
   * Student leaving frame (> 6.0s) transitions cleanly to `STUDENT_ABSENT`.
5. **Explainable AI Dashboard Section:**
   * Exposes live **"WHY DID THE AI MAKE THIS DECISION?"** breakdown with Observation, Evidence, Decision, and Audio Action.

---

## 3. Incomplete Features & Roadmap Backlog
* [ ] PyInstaller / Windows executable single-click bundle (Phase 10).
* [ ] Multi-subject tracking with facial re-identification for dense classroom settings.
* [ ] Specialized lightweight pen/pencil detector for fine writing motion disambiguation.

---

## 4. Known Bugs & Current Blockers
* **Known Minor Issue:** Starlette TestClient async websocket context timeout requires explicit mock disconnects in unit tests (`tests/test_web_app.py`). Real browser WebSocket connections in Google Chrome disconnect cleanly without hanging.
* **Blockers:** None. Both local and web modes are fully functional.

---

## 5. Latest Completed Task
Completed Eye-Focused Detection, Performance & Drowsiness Accuracy Revision (v2.8.0):
- Removed full-body skeleton visualization and CPU-intensive PoseLandmarker inference (boosted FPS to 30+).
- Replaced face mesh wireframe with clean eye-only landmarks matching user visual reference (yellow eyelid contours, pink corner dots, red eyelid margin dots, green iris ring, yellow pupil crosshair).
- Corrected left/right anatomical mapping and implemented physical eyelid aperture & iris detection.
- Added fast reopening reset and downward note-taking pitch protection against false drowsiness alerts.
- Verified all unit and integration test suites passing cleanly.
1. Visual Debug Overlay matching reference image (media_1793466279822_e3417f17.jpg) with face mesh wireframe in grey, left eye & eyebrow in emerald green, right eye & eyebrow in red, iris diamonds with pupil centers, lips and face oval in white, body pose skeleton in cyan, and hand skeletons in yellow.
2. Debug Overlay toggle button in Web Dashboard and keyboard toggle ('d'/'D') in OpenCV local Mode A.
3. Pitch foreshortening compensation and iris pupil verification eliminating false drowsiness triggers when looking down writing or reading notes.
4. Independent 5-state eye tracking (EYES_OPEN, EYES_PARTIALLY_CLOSED, BLINK, EYES_CLOSED, EYE_STATE_UNKNOWN).
5. Class-specific YOLO thresholds (conf 0.28 for phone) with spatial hand overlap and rapid 0.6s phone distraction confirmation.
6. Reduced student absence confirmation to 3.0s with frame-1 instant return recovery.
7. 94/94 automated tests passing (100% test suite success) and clean Vite frontend build.

---

## 6. Next Recommended Development Task
Run long-session stress test in Google Chrome at `http://127.0.0.1:8000/` and verify audio preemption and personal calibration across diverse desk lighting angles.

