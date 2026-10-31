# Development Roadmap & Phases (PHASES) — AI Study Focus Monitor

This document tracks the phased development roadmap, current implementation milestones, and future production readiness goals.

---

## Roadmap Overview

```mermaid
gantt
    title AI Study Focus Monitor Development Roadmap
    dateFormat  YYYY-MM-DD
    section Core Perception & Engine
    Phase 1: Project Architecture & Organization       :done,    p1, 2026-10-25, 2026-10-27
    Phase 5: Detection Pipeline Improvements           :done,    p5, 2026-10-27, 2026-10-29
    Phase 6: State Machine & Temporal Decision         :done,    p6, 2026-10-28, 2026-10-29
    Phase 7: Audio Management Improvements             :done,    p7, 2026-10-28, 2026-10-29
    section Dual-Mode & Web Platform
    Phase 2: Backend Service Separation                :done,    p2, 2026-10-29, 2026-10-30
    Phase 3: Frontend Separation (Vite/HTML5)          :done,    p3, 2026-10-29, 2026-10-30
    Phase 4: WebSocket Reliability & Flow Control      :done,    p4, 2026-10-30, 2026-10-30
    Phase 8: Dashboard & Real-Time Analytics           :done,    p8, 2026-10-30, 2026-10-30
    section Optimization & Production
    Phase 9: Testing & Performance Optimization        :active,  p9, 2026-10-30, 2026-11-05
    Phase 10: Production Readiness & Packaging         :         p10, 2026-11-05, 2026-11-15
```

---

## Detailed Phase Status

### Phase 1: Project Architecture & Organization
* **Objective:** Establish modular upper-body detection, type definitions, and central configuration.
* **Tasks:**
  * Define `behavior_types.py` with multi-label enums and typed dataclasses.
  * Implement `config.py` for all timeouts, thresholds, and model weights.
  * Establish structured JSONL logging in `logger.py`.
* **Dependencies:** None.
* **Completion Criteria:** All core types defined; no circular dependencies.
* **Status:** **COMPLETED**

---

### Phase 2: Backend Service Separation
* **Objective:** Create a dedicated FastAPI backend decoupling the CV engine from the UI.
* **Tasks:**
  * Build `app/main.py` with REST endpoints (`/api/health`, `/api/config`).
  * Implement `app/yolo_service.py` as a thread-safe singleton.
  * Implement `app/session_pipeline.py` for session-isolated monitoring.
* **Dependencies:** Phase 1.
* **Completion Criteria:** Backend starts on `127.0.0.1:8000` and serves health checks.
* **Status:** **COMPLETED**

---

### Phase 3: Frontend Separation
* **Objective:** Create a modern, responsive browser frontend independent from OpenCV GUI.
* **Tasks:**
  * Implement `frontend/index.html` with responsive dark-theme CSS (`frontend/css/dashboard.css`).
  * Build `frontend/js/camera_manager.js` for clean WebRTC camera lifecycle and track stopping.
  * Build `frontend/js/audio_controller.js` for browser alert sound preloading and autoplay unlocking.
  * Configure Vite dev tooling (`frontend/package.json`, `frontend/vite.config.js`).
* **Dependencies:** Phase 2.
* **Completion Criteria:** Browser accesses camera with user consent; stops tracks on unload.
* **Status:** **COMPLETED**

---

### Phase 4: WebSocket Reliability & Flow Control
* **Objective:** Establish low-latency bi-directional video frame streaming and state synchronization.
* **Tasks:**
  * Implement `/ws/monitor` WebSocket endpoint in `app/main.py`.
  * Build `frontend/js/websocket_client.js` with ACK-based flow control to prevent frame buffer lag.
  * Enforce frame payload boundary checks (< 2.5 MB) and handle disconnects cleanly.
* **Dependencies:** Phase 2, Phase 3.
* **Completion Criteria:** Real-time state updates arrive in browser with < 150ms latency.
* **Status:** **COMPLETED**

---

### Phase 5: Detection Pipeline Improvements
* **Objective:** Eliminate detection blindspots and timer reset bugs.
* **Tasks:**
  * Implement YOLO detection caching across strides in `run_webcam_yolo.py` and `app/session_pipeline.py`.
  * Add anatomical head-box estimation fallback from shoulders when FaceMesh landmarks drop out.
  * Implement head-pose EAR compensation for downward reading/typing pitch.
  * Integrate Mouth Aspect Ratio (MAR) for automated yawn detection.
* **Dependencies:** Phase 1.
* **Completion Criteria:** Reading does not trigger sleep alarms; intense face concealment is 100% detected.
* **Status:** **COMPLETED**

---

### Phase 6: State Machine & Temporal Decision Improvements
* **Objective:** Enforce persistent duration timers, hysteresis, and recovery stabilization.
* **Tasks:**
  * Implement independent timers (`_inactivity_start`, `_phone_start`, `_head_down_start`, etc.) in `temporal_decision_engine.py`.
  * Add `RECOVERY_STABILITY_SECS` window before transitioning back to `STUDYING`.
  * Discriminate thinking postures (`face_resting_on_hand`) from idle distraction.
* **Dependencies:** Phase 5.
* **Completion Criteria:** 0.00 false alarms/hour on benchmark evaluation suite.
* **Status:** **COMPLETED**

---

### Phase 7: Audio Management Improvements
* **Objective:** Centralize alert arbitration, priority preemption, and recovery audio stopping.
* **Tasks:**
  * Implement priority hierarchy (P1 `CAMERA_ERROR` > P2 `STUDENT_ABSENT` > P3 `FACE_OCCLUDED` > P4 `POSSIBLE_DROWSINESS` > P5 `DISTRACTED`).
  * Implement preemption logging and stop-on-recovery behavior in `audio_alerts.py` and `app/session_pipeline.py`.
  * Integrate custom user audio clips (`InShot_...`, `uth jaa...`, `IAS...`).
* **Dependencies:** Phase 6.
* **Completion Criteria:** Only one alert plays at a time; higher priority preempts lower; audio stops on focus resumption.
* **Status:** **COMPLETED**

---

### Phase 8: Dashboard & Real-Time Analytics
* **Objective:** Upgrade dashboard with explainable AI reasoning and personal workspace calibration.
* **Tasks:**
  * Add **"WHY DID THE AI MAKE THIS DECISION?"** section exposing observation, evidence, decision, and audio action.
  * Implement dynamic "What should I do now?" recommendations.
  * Add Personal Calibration wizard to adapt to individual camera angles and sitting heights.
* **Dependencies:** Phase 3, Phase 4, Phase 6.
* **Completion Criteria:** All HUD values populate from actual detectors in real time; calibration saves baseline.
* **Status:** **COMPLETED**

---

### Phase 9: Testing & Performance Optimization
* **Objective:** Comprehensive unit test coverage, load testing, and multi-session profiling.
* **Tasks:**
  * Automate regression tests for all Section 8 and Section 11 behavioral scenarios.
  * Profile CUDA VRAM usage and CPU thermal load under extended runs.
  * Fix Starlette TestClient websocket disconnect handling in async tests.
* **Dependencies:** Phases 1–8.
* **Completion Criteria:** 100% pass rate across `tests/` discovery suite without hardware dependencies.
* **Status:** **IN PROGRESS**
* **Known Blockers:** Starlette TestClient async websocket context timeout requires explicit mock disconnects in unit testing.

---

### Phase 10: Production Readiness & Packaging
* **Objective:** Package the application for one-click installation on student laptops.
* **Tasks:**
  * Create standalone executable or Windows desktop installer (PyInstaller / Electron wrapper).
  * Build Docker container for headless server deployment.
  * Add optional user authentication and session export analytics (PDF/CSV focus report).
* **Dependencies:** Phase 9.
* **Completion Criteria:** Single double-click launcher boots desktop application without manual terminal commands.
* **Status:** **PLANNED**

