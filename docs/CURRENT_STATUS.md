# Live Project Status (CURRENT_STATUS) — AI Study Focus Monitor

*Last Updated:* 2026-10-31T14:45:00+05:30  
*Project Version:* 2.3.0  
*Current Development Phase:* Premium Futuristic AI SaaS Landing Page Redesign Verified

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
| **MediaPipe Mesh/Pose/Hands** | **OPERATIONAL** | 478 face pts, 3D blendshapes (eyeBlinkLeft/Right), 33 pose, 21 hands |
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
Completed Complete AI Study Focus Monitor Accuracy Overhaul across all 10 execution phases: safe diagnostic mode, MediaPipe 3D blendshapes eye blink integration, pitch-compensated EAR, natural blink vs sustained closure separation, distraction yaw threshold refinement, non-disruptive study switching, category-specific recovery, audio alert gating & deduplication, real-time diagnostic HUD overlay, and 82/82 automated tests passing (including 11 new accuracy audit tests covering TEST A through TEST K).

---

## 6. Next Recommended Development Task
Run long-session stress test in Google Chrome at `http://127.0.0.1:8000/` and verify audio preemption and personal calibration across diverse desk lighting angles.

