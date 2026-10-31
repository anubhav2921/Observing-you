# Development Rulebook (RULES) — AI Study Focus Monitor

This document establishes the mandatory rules and architectural standards for modifying, extending, or maintaining the AI Study Focus Monitor codebase.

---

## 1. Golden Development Axioms

1. **Never Rewrite Working Modules Without Empirical Justification:**
   * Improve and refine existing working logic in place. Do not discard working perception algorithms or state transitions for speculative rewrites.
2. **Never Duplicate Existing Services:**
   * Use `YOLOService.get_instance()` for YOLO inference. Never instantiate a second YOLO model or load weights again.
   * Use `CentralAudioManager` (Mode A) or `BrowserAudioController` (Mode B). Never write one-off audio players.
3. **Never Initialize Hardware Multiple Times:**
   * In local mode, only `run_webcam_yolo.py` opens `cv2.VideoCapture`.
   * In web mode, only `CameraManager` in the browser accesses `navigator.mediaDevices.getUserMedia()`.
4. **Never Bypass the Central State Machine:**
   * All behavioral states must flow through `TemporalDecisionEngine` and `FocusMonitor`. Never hardcode state overrides or direct audio triggers outside the pipeline.
5. **Never Silently Ignore or Swallow Exceptions:**
   * Never write empty `except: pass` blocks in detector code. Log the exception, set `inference_error = True`, and route technical faults to `StudyState.CAMERA_ERROR`.
6. **Never Invent Unsupported APIs or Claims:**
   * Every field in `ObservationData` and `StateUpdateEvent` must reflect actual detector outputs. Never fabricate mock demo data when real detections are unavailable.
7. **Keep Documentation Synchronized:**
   * Any change to endpoints, config parameters, or state transitions must be accompanied by an update to the corresponding `/docs/` file.

---

## 2. Python Code Standards

* **Type Safety:** All Python functions, methods, and classes must use type annotations (`from __future__ import annotations`, `typing.Optional`, `typing.Dict`, `typing.List`, etc.).
* **Dataclasses & Schemas:**
  * Internal pipeline signals must use `@dataclass` (defined in `behavior_types.py`).
  * External API and WebSocket event payloads must use Pydantic `BaseModel` (defined in `app/schemas.py`).
* **Circular Import Prevention:**
  * Core types and enums live in `behavior_types.py` and `state_machine.py`.
  * Detectors import types, not vice-versa.
  * `config.py` must never import other project modules.
* **Resource Cleanup:**
  * All classes handling native resources (`FocusMonitor`, `UpperBodyDetector`, `SessionPipeline`) must implement a `close()` method that releases C++ model buffers and camera handles.

---

## 3. JavaScript & Frontend Standards

* **Vanilla ES Modules:** Frontend code is written in clean, modern vanilla JavaScript modules without heavy frontend framework bloat.
* **Component Encapsulation:**
  * `js/camera_manager.js` owns the `getUserMedia()` stream, track stopping, and canvas capture.
  * `js/websocket_client.js` owns WebSocket connection, reconnection, and flow-control ACKs.
  * `js/audio_controller.js` owns audio preloading, browser autoplay unlocking, and alert audio.
  * `js/app.js` is the coordinator. It does not contain low-level WebRTC or WebSocket logic.
* **Camera Safety:**
  * Always release browser media tracks (`track.stop()`) on window unload or when monitoring stops.
  * Never claim the webcam is active if `videoWidth === 0`.
* **Dark Theme UI:** Maintain accessibility, clean CSS custom properties, and avoid hardcoding inline styles in HTML.

---

## 4. API & WebSocket Standards

* **Port Standards:**
  * Backend runs on `127.0.0.1:8000`.
  * Frontend dev server runs on `127.0.0.1:5173` with proxy routing to `8000`.
* **WebSocket Flow Control:**
  * Binary messages sent from client to `/ws/monitor` must be valid JPEG blobs under 2.5 MB.
  * Client must not send the next frame until the server responds with the JSON `StateUpdateEvent` for the previous frame.
* **Session Isolation:**
  * Every WebSocket connection generates a unique `session_id`.
  * Sessions must never share `FocusMonitor` or temporal state engines. Only the underlying `YOLOService` model weights are shared.

---

## 5. Configuration & Threshold Standards

* All temporal durations, confidence thresholds, and model paths must reside in `config.py`.
* Never hardcode magic numbers (e.g. `3.5`, `12.0`, `0.20`) inside detector loops.
* If a threshold needs to be adjusted, update `config.py` and document the rationale in `docs/CHANGELOG.md`.

---

## 6. Testing & Quality Assurance

* **Harness Independence:** Unit and regression tests must run without requiring a physical webcam or hardware audio device attached.
* **Mocking:** Tests in `tests/test_study_monitor.py` and `tests/test_critical_fixes.py` use mocked `UpperBodyFeatures` and synthetic image buffers.
* **Discovery Command:** The standard test execution command is:
  ```powershell
  .venv\Scripts\python.exe -m unittest discover tests
  ```
* Before declaring any bug fixed, write an automated test case that asserts the exact state, duration, and alert decision.

---

## 7. Version Control & File Organization

* **Directory Structure:**
  * `/app/`: FastAPI backend, schemas, services, and session pipelines.
  * `/frontend/`: Web dashboard UI, CSS, and ES modules.
  * `/docs/`: Persistent project memory and documentation.
  * `/tests/`: Automated unit and regression test suites.
  * `/assets/audio/`: Alert audio assets.
  * `/logs/`: JSONL structured diagnostic traces.
* **Prohibited Files:** Do not commit temporary test video files, raw screen recordings, or giant virtual environments to git.

