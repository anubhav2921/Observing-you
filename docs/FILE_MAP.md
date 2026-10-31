# Project File Registry (FILE_MAP) — AI Study Focus Monitor

This registry maps every important file in the project, documenting its responsibility, exported symbols, internal dependencies, and implementation status.

---

## 1. Backend AI Engine & Services (`backend/app`)

| File Path | Responsibility | Main Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :---: |
| [`backend/app/services/behavior/behavior_types.py`](file:///C:/Users/vinu/modal-object/backend/app/services/behavior/behavior_types.py) | Canonical enums, dataclasses, and behavioral types. | `BehaviorLabel`, `HeadDirection`, `EyeState`, `ShoulderPosture`, `HandActivity`, `ObservablePoseFeatures`, `Observation`, `IndependentObservations`, `UpperBodyFeatures`, `UpperBodyDecision` | None (Standard library) | **Implemented** |
| [`backend/app/services/detection/upper_body_detector.py`](file:///C:/Users/vinu/modal-object/backend/app/services/detection/upper_body_detector.py) | Multimodal feature extraction (MediaPipe Face, Pose, Hands, SolvePnP head pose, EAR, MAR). | `UpperBodyDetector`, `_compute_ear()`, `_compute_box_iou()` | `mediapipe`, `cv2`, `numpy`, `backend.app.core.config`, `behavior_types` | **Implemented** |
| [`backend/app/services/decision/temporal_decision_engine.py`](file:///C:/Users/vinu/modal-object/backend/app/services/decision/temporal_decision_engine.py) | Monotonic temporal duration tracking, hysteresis, multi-label arbitration. | `TemporalDecisionEngine`, `reset()` | `config`, `behavior_types`, `state_machine`, `logging` | **Implemented** |
| [`backend/app/services/detection/focus_monitor.py`](file:///C:/Users/vinu/modal-object/backend/app/services/detection/focus_monitor.py) | High-level orchestrator binding `UpperBodyDetector` and `TemporalDecisionEngine`. | `FocusMonitor`, `_BEHAVIOR_TO_STUDY_STATE`, `reset()` | `upper_body_detector`, `temporal_decision_engine`, `state_machine`, `config` | **Implemented** |
| [`backend/app/services/decision/state_machine.py`](file:///C:/Users/vinu/modal-object/backend/app/services/decision/state_machine.py) | Legacy state definitions, display colors, labels, and transition rules. | `StudyState`, `STATE_DISPLAY`, `STATE_RESPONSES`, `ALERT_STATES` | `config`, `logging` | **Implemented** |
| [`backend/app/services/audio/audio_alerts.py`](file:///C:/Users/vinu/modal-object/backend/app/services/audio/audio_alerts.py) | Native Pygame sound player with priority preemption and stop-on-recovery. | `CentralAudioManager`, `STATE_PRIORITY` | `pygame`, `config`, `state_machine` | **Implemented** |
| [`backend/app/services/session/session_manager.py`](file:///C:/Users/vinu/modal-object/backend/app/services/session/session_manager.py) | Multi-session lifecycle manager for concurrent WebSocket streams. | `SessionManager` | `session_pipeline` | **Implemented** |
| [`backend/app/services/recommendation/recommendation_engine.py`](file:///C:/Users/vinu/modal-object/backend/app/services/recommendation/recommendation_engine.py) | Rules-based, non-shaming coaching guidance generator. | `RecommendationEngine` | `schemas.events`, `state_machine` | **Implemented** |
| [`backend/app/services/analytics/logger.py`](file:///C:/Users/vinu/modal-object/backend/app/services/analytics/logger.py) | Structured JSONL event logging for transitions and diagnostic frames. | `StructuredLogger` | Standard library (`json`, `time`, `os`) | **Implemented** |
| [`backend/app/core/config.py`](file:///C:/Users/vinu/modal-object/backend/app/core/config.py) | Centralized timeouts, thresholds, paths, model weights, and toggles. | `_find_audio_file()`, `REPO_ROOT`, `ASSETS_DIR` | Standard library (`os`, `glob`, `pathlib`) | **Implemented** |
| [`backend/app/core/logging.py`](file:///C:/Users/vinu/modal-object/backend/app/core/logging.py) | Structured logger implementation. | `StructuredLogger` | Standard library | **Implemented** |
| [`backend/app/models/loader.py`](file:///C:/Users/vinu/modal-object/backend/app/models/loader.py) | Model asset file existence verification. | `verify_model_files()` | `config` | **Implemented** |
| [`backend/app/pipelines/session_pipeline.py`](file:///C:/Users/vinu/modal-object/backend/app/pipelines/session_pipeline.py) | Per-client monitoring session pipeline and decision rationale builder. | `SessionPipeline` | `cv2`, `numpy`, `focus_monitor`, `yolo_service`, `recommendation_engine` | **Implemented** |
| [`backend/app/utils/geometry.py`](file:///C:/Users/vinu/modal-object/backend/app/utils/geometry.py) | Bounding box IoU and distance calculations. | `compute_box_iou()`, `compute_distance_2d()` | Standard library | **Implemented** |
| [`backend/app/main.py`](file:///C:/Users/vinu/modal-object/backend/app/main.py) | FastAPI server hosting REST endpoints, `/ws/monitor` WebSocket, and static files. | `create_app()`, `app`, `lifespan()` | `fastapi`, `uvicorn`, `api_router`, `ws_router` | **Implemented** |

---

## 2. Execution Entry Points

| File Path | Responsibility | Main Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :---: |
| [`run_app.py`](file:///C:/Users/vinu/modal-object/run_app.py) | Unified CLI launcher supporting `--mode local`, `--mode web`, and `--mode dev`. | `run_local_mode()`, `run_web_mode()`, `run_dev_mode()`, `main()` | `argparse`, `uvicorn`, `webbrowser`, `subprocess` | **Implemented** |
| [`backend/scripts/run_webcam.py`](file:///C:/Users/vinu/modal-object/backend/scripts/run_webcam.py) | Standalone local OpenCV native execution script with diagnostic HUD overlay. | `main()`, `draw_hud()` | `cv2`, `focus_monitor`, `audio_alerts`, `config` | **Implemented** |

---

## 3. Frontend Web Application (`frontend/`)

| File Path | Responsibility | Main Classes / Functions | Dependencies | Status |
| :--- | :--- | :--- | :--- | :---: |
| [`frontend/index.html`](file:///C:/Users/vinu/modal-object/frontend/index.html) | Single-page responsive dark theme dashboard. | HTML structure, modals, HUD container, reasoning card | None | **Implemented** |
| [`frontend/src/styles/dashboard.css`](file:///C:/Users/vinu/modal-object/frontend/src/styles/dashboard.css) | Accessible modern styles, badges, progress bars, and modal overlays. | CSS variables, responsive grid | None | **Implemented** |
| [`frontend/src/styles/landing.css`](file:///C:/Users/vinu/modal-object/frontend/src/styles/landing.css) | Futuristic AI SaaS landing page visual styling, 3D shapes, and animations. | Hero styling, 3D neon shapes, feature grid | None | **Implemented** |
| [`frontend/src/landing.js`](file:///C:/Users/vinu/modal-object/frontend/src/landing.js) | Client controller managing landing page view routing, smooth anchors, and dashboard launches. | `initLandingPage()` | ES Modules | **Implemented** |
| [`frontend/src/utils/camera_manager.js`](file:///C:/Users/vinu/modal-object/frontend/src/utils/camera_manager.js) | WebRTC camera acquisition, track stopping, and canvas JPEG capture. | `CameraManager` | Native Web APIs (`getUserMedia`) | **Implemented** |
| [`frontend/src/services/websocket_client.js`](file:///C:/Users/vinu/modal-object/frontend/src/services/websocket_client.js) | Flow-controlled bi-directional WebSocket client. | `MonitorWebSocketClient` | Native WebSocket API | **Implemented** |
| [`frontend/src/utils/audio_controller.js`](file:///C:/Users/vinu/modal-object/frontend/src/utils/audio_controller.js) | Browser audio alert manager with preemption, muting, and autoplay unlock. | `BrowserAudioController` | HTML5 Audio API | **Implemented** |
| [`frontend/src/App.js`](file:///C:/Users/vinu/modal-object/frontend/src/App.js) | Main UI coordinator binding camera, WebSocket, audio, rationale, and calibration. | `StudyMonitorApp` | ES Modules | **Implemented** |
| [`frontend/src/main.js`](file:///C:/Users/vinu/modal-object/frontend/src/main.js) | Vite entrypoint loading styles and instantiating StudyMonitorApp. | Vite entry | ES Modules | **Implemented** |
| [`frontend/vite.config.js`](file:///C:/Users/vinu/modal-object/frontend/vite.config.js) | Vite development configuration with API/WebSocket proxy rules. | Vite config | `vite` | **Implemented** |
| [`frontend/package.json`](file:///C:/Users/vinu/modal-object/frontend/package.json) | Frontend NPM package dependencies and dev scripts. | `dev`, `build`, `preview` | `npm` | **Implemented** |

---

## 4. Test Suites (`backend/tests/`)

| File Path | Responsibility | Scenarios Covered | Status |
| :--- | :--- | :--- | :---: |
| [`backend/tests/unit/test_state_machine.py`](file:///C:/Users/vinu/modal-object/backend/tests/unit/test_state_machine.py) | Base state machine transitions, reading posture, and recovery latency. | 22 test cases | **Passed (100%)** |
| [`backend/tests/unit/test_upper_body_detector.py`](file:///C:/Users/vinu/modal-object/backend/tests/unit/test_upper_body_detector.py) | Upper-body detector keypoints, SolvePnP pose, EAR, and shoulder angles. | 8 test cases | **Passed (100%)** |
| [`backend/tests/integration/test_critical_fixes.py`](file:///C:/Users/vinu/modal-object/backend/tests/integration/test_critical_fixes.py) | 16 Section 8 scenarios: sustained inactivity, camera staring, phone, occlusion, drowsiness. | 19 test cases | **Passed (100%)** |
| [`backend/tests/integration/test_accuracy_overhaul.py`](file:///C:/Users/vinu/modal-object/backend/tests/integration/test_accuracy_overhaul.py) | Complete accuracy audit: TEST A through TEST J (blinking, study switching, fatigue, gating, diag mode). | 11 test cases | **Passed (100%)** |
| [`backend/tests/regression/test_runtime_error_fixes.py`](file:///C:/Users/vinu/modal-object/backend/tests/regression/test_runtime_error_fixes.py) | Regression verification for Error 1 (`stop_alert` alias) and Error 2 (`STATE_DISPLAY` tuple unpack). | 10 test cases | **Passed (100%)** |
| [`backend/tests/websocket/test_websocket_stream.py`](file:///C:/Users/vinu/modal-object/backend/tests/websocket/test_websocket_stream.py) | REST health check, config endpoint, static assets, session isolation, payload validation. | 12 test cases | **Passed (100%)** |

---

## 5. Shared Contracts & Infrastructure

| File Path | Responsibility | Content | Status |
| :--- | :--- | :--- | :---: |
| `shared/contracts/state_update_event.json` | Cross-language JSON schema for StateUpdateEvent. | JSON Schema Draft 2020-12 | **Implemented** |
| `shared/contracts/client_command.json` | Cross-language JSON schema for ClientCommand. | JSON Schema Draft 2020-12 | **Implemented** |
| `infrastructure/docker/Dockerfile.backend` | Multi-stage Docker container for FastAPI backend. | Python 3.11-slim + OpenCV/MediaPipe | **Implemented** |
| `infrastructure/docker/Dockerfile.frontend` | Multi-stage Docker container for Vite frontend. | Node 18 build + Nginx alpine | **Implemented** |
| `infrastructure/deployment/supervisord.conf` | Process supervisor configuration. | Uvicorn manager | **Implemented** |
| `infrastructure/deployment/nginx.conf` | Reverse proxy and static routing configuration. | HTTP + WebSocket proxy | **Implemented** |
| `infrastructure/scripts/start_all.ps1` | Unified PowerShell startup script. | Cross-platform runner | **Implemented** |
| `infrastructure/scripts/start_all.sh` | Unified Bash startup script. | Linux/macOS runner | **Implemented** |
