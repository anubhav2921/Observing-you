# Development Changelog (CHANGELOG) — AI Study Focus Monitor

This document maintains a chronological record of all architectural updates, bug fixes, features, and test outcomes.

## [2.8.0] — 2026-10-31

### Changed & Optimized
- **Eye-Only Landmark Visualization (Matching Visual Reference media_1793469479412_2be6ffaf.jpg):**
  - Removed full-body skeleton visualization (shoulders, elbows, wrists, hips) and face mesh wireframe triangles.
  - Implemented eye-only landmark overlays in both Frontend (drawHudOverlay in App.js) and OpenCV local mode (FocusMonitor in ocus_monitor.py):
    - Yellow contour boundary (#facc15, thickness 1.8px) outlining eyelids.
    - Magenta/pink landmark dots (#ec4899, r=3.0) at inner and outer eye corners (landmarks 33, 133 and 362, 263).
    - Vivid red dots (#ef4444, r=2.2) along upper and lower eyelid margins (landmarks 160, 159, 158, 144, 145, 153 and 385, 386, 387, 380, 374, 373).
    - Green iris boundary circle (#22c55e, thickness 1.6px) encompassing iris perimeter (landmarks 469-472 and 474-477).
    - Yellow/cyan pupil center '+' crosshair at landmark 468 (right eye) and 473 (left eye).
  - Preserves essential person bounding box, face bracket, and phone detection box overlays.

- **CPU & GPU Performance Optimization:**
  - Disabled CPU-intensive MediaPipe PoseLandmarker by default (ENABLE_POSE_DETECTION = False in config.py), bypassing redundant 35-40ms CPU inference overhead per frame.
  - Achieved smooth 30+ FPS capture loop on Intel i5-12500H + RTX 3050 Ti systems.

- **Drowsiness & Eye State Inconsistency Fixes:**
  - Fixed left/right eye anatomical cross-wiring bug between MediaPipe blendshapes (eyeBlinkRight mapped to screen-left user right eye; eyeBlinkLeft mapped to screen-right user left eye).
  - Replaced trivial coordinate check with physical iris tracking based on eyelid aperture ($\ge 4.0\text{px}$) and blink score ($< 0.50$).
  - Added independent 8-state eye tracking (LEFT_EYE_OPEN, LEFT_EYE_CLOSED, RIGHT_EYE_OPEN, RIGHT_EYE_CLOSED, BLINK, EYES_PARTIALLY_CLOSED, EYES_CLOSED, EYE_STATE_UNKNOWN).
  - Added fast eye reopening reset: $\ge 2$ consecutive open frames immediately cancel closure timer.
  - Added downward pitch protection: note-writing and reading downward head pitches do not trigger fatigue alerts when irises are tracked or aperture is open.

## [2.7.0] — 2026-10-31

### Added & Improved
- **Full Visual Debug Landmark Overlay (Matching Visual Reference `media_1793466279822_e3417f17.jpg`):**
  - Rendered dense 468-point face mesh Delaunay wireframe in clean grey lines.
  - Color-coded left eye and eyebrow in vivid emerald green (`#10b981`).
  - Color-coded right eye and eyebrow in vivid red (`#ef4444`).
  - Added left iris green diamond and right iris red diamond with pupil center dots.
  - Rendered face oval perimeter and inner/outer lips in smooth crisp white (`#f8fafc`).
  - Added upper-body pose skeleton (cyan lines) connecting shoulders, elbows, wrists, and hips.
  - Added hand skeletons (yellow lines) tracking finger joints and fingertips.
  - Added dynamic Debug Overlay toggle (`ON` / `OFF`) in both the Web UI and native OpenCV window (`'d'` / `'D'` key).
- **Downward Note-Taking vs False Drowsiness Resolution:**
  - Implemented dynamic pitch foreshortening compensation ($\\text{EAR}_{\\text{comp}}$): looking down writing or reading notes expands effective eye aspect ratio, preventing depressed 2D eyelid projections from triggering false sleep alerts.
  - Integrated iris tracking: physical tracking of pupils/irises provides ground-truth proof that eyes are open, preventing drowsiness triggers during note-taking.
  - Added independent 5-state eye tracking (`EYES_OPEN`, `EYES_PARTIALLY_CLOSED`, `BLINK`, `EYES_CLOSED`, `EYE_STATE_UNKNOWN`) for left and right eyes.
- **Fast Phone Detection & Spatial Hand Overlap:**
  - Added class-specific YOLO thresholds (`YOLO_CONF_PERSON = 0.40`, `YOLO_CONF_PHONE = 0.28`, `YOLO_CONF_BOOK = 0.35`, `YOLO_CONF_LAPTOP = 0.38`).
  - Stored `phone_box`, `phone_conf`, `person_box`, `book_box` across YOLO inference strides.
  - Verified hand-phone spatial overlap and gaze direction for rapid 0.6s phone distraction confirmation.
- **Rapid Student Absence & Frame-1 Return Recovery:**
  - Decreased absence confirmation window to 3.0s (`STUDENT_ABSENT_SECS = 3.0`).
  - Implemented instant frame-1 recovery upon student reappearance.
- **Automated Verification:**
  - 94/94 automated tests passing (100% test suite success).
  - Clean Vite frontend production build with zero warnings or errors.

## [2.6.1] - 2026-10-31

### Fixed
- **Windows DirectShow OpenCV Capture**: Switched default Windows capture backend to cv2.CAP_DSHOW in 
un_webcam.py with 6-frame sensor warmup, resolving MSMF buffer lockouts, device contention errors, and frame freezing.
- **MediaPipe Landmark Dropout vs False Occlusion**: Corrected ace_occluded logic in upper_body_detector.py and 	emporal_decision_engine.py so that missing face mesh frames are not falsely classified as FACE_OCCLUDED unless physical occlusion (hands/objects covering face) is positively observed.
- **YOLO Head-Region Crop Fallback**: Added automatic upper-body crop fallback in upper_body_detector.py for face mesh inference when full-frame detection confidence dips below threshold.
- **Confidence Tuning**: Optimized FaceLandmarker detection/presence thresholds to 0.30 and pose/hands to 0.35 for reliable tracking under indoor lighting shadows.

## [2.6.0] — 2026-10-31
### Added & Improved
- **Detection Accuracy Overhaul & Unified Pipeline (Phases 1–6):**
  - **Single Authoritative Eye Closure Tracker:** Consolidated competing timers between `upper_body_detector.py` and `temporal_decision_engine.py`. Fixed the bug where the first 0.5s of eye closure was continuously reset by `normal_blinking=True`.
  - **4 Explicit Eye States:** Introduced `EYES_OPEN`, `BLINK` (<=0.45s), `EYES_CLOSED` (>0.45s), and `EYE_STATE_UNKNOWN` (missing/occluded landmarks).
  - **0.35s Noise Gap Tolerance:** Prevents a single dropped landmark frame from aborting an ongoing 1.7s closure while requiring 2 consecutive open frames for confirmed eye reopening.
  - **Context-Aware Head Movement vs Distraction:** Downward head tilt while studying books, notes, or typing is strictly protected from false distraction classification.
  - **Active Phone Usage Enforcement:** Distinguishes mere phone presence on the desk from active handling (`PHONE_IN_USE` / `PHONE_HELD`), requiring temporal confirmation.
  - **Confirmation Status Lifecycle:** Added `ConfirmationStatus` (`CONFIRMED`, `POSSIBLE`, `UNKNOWN`, `RECOVERING`) to `UpperBodyDecision` and WebSocket `StateUpdateEvent`.
  - **Centralized Diagnostic Mode:** Enhanced `StructuredLogger.log_diagnostic` logging Left EAR, Right EAR, Avg EAR, face visibility, head pose (yaw/pitch), hand detection, phone detection, confirmed activity, duration, and audio trigger rationale.

- **Simplified Minimal Dashboard (Phase 7):**
  - Stripped away unnecessary cognitive clutter: removed stock-market graphs, sparklines, quad percentage cards, radial gauge SVG meters, and checklist panels.
  - Streamlined dashboard to ONLY 3 essential areas:
    1. **Header:** Product brand, Camera connection status (`Active` / `Standby`), Session status (`Active` / `Idle`), and Audio Alerts toggle (`ON` / `OFF`).
    2. **Camera:** Live webcam feed, clean emerald target bounding box overlay (`[Face Detected]`), resolution badge (`640x480`), and Start / Stop monitoring controls.
    3. **Current Activity:** Prominent, high-contrast authoritative activity card (`STUDYING`, `READING`, `WRITING`, `LOOKING AWAY`, `PHONE INTERACTION`, `DROWSINESS`, `IDLE`, `FACE OCCLUDED`), with confirmation status tag and compact signal diagnostics.
  - Verified Vite production build (`vite build` in 229ms, JS bundle reduced from 32kB to 18.8kB) and passed 94/94 regression tests.

---

## [2.5.0] — 2026-10-31
### Added
- **Real-Time AI Study Focus Monitoring Dashboard Overhaul:**
  - Redesigned and implemented the monitoring dashboard based on the visual reference:
    - **Live Camera Feed HUD:** Real-time green target bounding box (`[Face Detected]`), landmarks overlay, live resolution (`640x480`), and FPS indicator.
    - **5 Compact Independent Signal Pills:** Face (`Detected`/`Absent`), Eyes (`Open`/`Closed`), Pose (`Normal`/`Tilted`), Phone (`Not Detected`/`In Use`), and Activity (`Reading`/`Writing`/`Screen`).
    - **Current Behaviour Card:** Prominent state label, subcategory description, SVG dynamic radial confidence gauge (0–100%), and stability badge (`Stable State` / `Transitioning`).
    - **Real-Time AI Analysis Checklist:** 5 dynamic checklist items confirming verified observations (face visible, eyes focused, head orientation, hand position, phone absent/present).
    - **Quad Real-Time Metric Cards:** Focus Level, Attention, Distraction, and Drowsiness with animated mini sparkline canvases.
    - **Stock-Market-Style Continuous Focus Graph:** 60–120s rolling canvas graph with cubic bezier curve smoothing, vertical gradients, glowing boundary, live leading head dot, metric selector dropdown, and dynamic time-axis labels.
    - **Live In-Memory Events Panel:** Real-time timeline recording up to 20 recent state transitions with timestamps, color badges, duration markers, and clear log action.
    - **Top Control Bar & Sine Wave Visualizer:** Live session timer, camera/model/socket status badges, real-time FPS counter, and animated ambient sine waveform canvas.
  - **Zero Persistent Storage Architecture:**
    - Strictly non-database, non-user session model. All metrics, sparkline history, and event transitions remain strictly ephemeral in temporary browser memory and are wiped when monitoring stops.
  - **Backend Pipeline & Event Telemetry:**
    - Added derived telemetry fields in `ObservationData`: `face_box`, `focus_level`, `attention_level`, `distraction_level`, and `drowsiness_level`.
  - **Build & Quality Assurance:**
    - Verified Vite production build (`vite build` in 249ms) with 0 errors.
    - Ran complete backend test suite: 94/94 tests passing (100% OK).

---

## [2.4.0] — 2026-10-31
### Added
- **Cinematic Zoom-In Intro Animation Sequence:**
  - Implemented 3.4s cinematic fullscreen opening experience with deep space indigo radial gradient and ambient floating neon particles.
  - Logo scales up from `0.2` to `1.0` with glowing cyan/electric blue halo and unblur effect.
  - Staggered typography reveal displaying `AI STUDY` and `FOCUS MONITOR` with wide letter-spacing and tagline `INTELLIGENCE • FOCUS • PERFORMANCE`.
  - Added cinematic blue light sweep and camera expansion transition zooming smoothly into the landing page hero section.
  - Integrated "Skip Intro" button, "↺ Replay Intro" trigger in navigation, session replay arbitration, and reduced-motion graceful fallback.
  - Fully verified with Vite production build (`vite build` in 225ms) and 94/94 passing tests.

---

## [2.3.0] — 2026-10-31
### Added
- **Futuristic AI SaaS Landing Page Redesign:**
  - Implemented cinematic SaaS hero section inspired by the visual reference image with dark navy `#060814` backdrop, deep indigo/violet ambient gradients, and electric neon lighting.
  - Added dual SVG layered 3D pedestal sculptures framing the hero viewport with smooth floating hovering animations.
  - Created interactive 3D perspective dashboard preview mockup showcasing live study feed simulation, 3D FaceMesh landmark points, confidence meters, and explainable AI reasoning.
  - Designed 8 feature capability cards with neon hover effects, 4-step horizontal workflow with glowing connector line, 8-card technology stack, privacy transparency section, and full product footer.
  - Built isolated stylesheet `frontend/src/styles/landing.css` and client router `frontend/src/landing.js`.
  - Preserved 100% of existing monitoring dashboard structure, IDs, and WebSocket/camera logic untouched.
  - Verified frontend production build (`vite build` in 223ms) and passed all 94 backend regression tests.

---

## [2.2.0] — 2026-10-31
### Added
- **Comprehensive Student Behaviour Policy & Taxonomy (`BehaviorCategory`):**
  - Integrated 11 parent categories: `PRODUCTIVE_STUDYING`, `DIGITAL_DISTRACTION`, `VISUAL_DISTRACTION`, `PHYSICAL_DISENGAGEMENT`, `DROWSINESS`, `PHYSICAL_DISTRACTION`, `SOCIAL_DISTRACTION`, `STUDY_AVOIDANCE`, `FACE_OCCLUSION`, `STUDENT_ABSENT`, `ACTIVITY_UNCONFIRMED`.
- **Granular Mobile Phone Interaction Pipeline (`PhoneInteractionStatus`):**
  - Distinguishes `PHONE_VISIBLE` (phone on desk), `PHONE_HELD` (hand-phone IoU overlap), `PHONE_IN_USE` (phone held + downward pitch/gaze), and `PHONE_CONFIRMED` (fast 0.8s confirmation window).
- **Ongoing Alert Audio Persistence:**
  - Prevented premature alert cancellation by maintaining `alert.active = True` during continuous incidents while enforcing cooldown deduplication.
- **New 18-Scenario Regression Test Suite (`test_behavior_policy_suite.py`):**
  - Added 12 new automated test cases covering phone presence vs usage, brief vs sustained look-aways, natural blinks vs fatigue, and material transitions. Total test suite expanded to 94 tests (100% PASS).
- **Live UI Observation Badges:**
  - Added real-time Phone Status and Behavioral Category indicators on the Web Dashboard.

---

## [2026-10-31] — Complete Accuracy & Reliability Overhaul (Phases 1 - 10)

### What Changed
1. **Safe Diagnostic Mode (Phase 1):**
   * Added `DIAGNOSTIC_MODE` flag in `config.py` and `--diagnostic` / `--diag` flag in `run_app.py`.
   * When enabled, runs all perception pipelines, logging, and HUD overlays while muting all audio alerts across Mode A and Mode B.
2. **Eye Detection & Blendshapes Overhaul (Phase 2):**
   * Enabled MediaPipe `output_face_blendshapes=True` to extract 3D neural blink probabilities (`eyeBlinkLeft`, `eyeBlinkRight`).
   * Integrated adaptive pitch compensation for downward gaze foreshortening (`head_pitch > 8.0` deg).
   * Distinguish brief natural blinks (< 0.5s) from sustained fatigue eye closures (> 2.0s).
   * Never classify missing, occluded, or low-confidence face landmarks as closed eyes.
   * Added support for calibrating user baseline open EAR via `set_calibrated_ear()`.
3. **Drowsiness & Fatigue Multi-Evidence Arbitration (Phase 3):**
   * Drowsiness requires verified sustained eye closure (> 2.0s), cyclic head drooping with low EAR, or forward head collapse without hands.
   * Looking down typing or reading with downward pitch is protected from false drowsiness classification.
4. **Distraction & Looking-Away Overhaul (Phase 4):**
   * Widened room-scanning yaw swing threshold (`HEAD_TURN_ROOM_SCAN_YAW_DEG = 30.0` deg) to prevent normal dual-monitor / screen reading from triggering distraction.
   * Require sustained phone detection (> 4.0s) near hands/torso before distraction alert eligibility.
5. **Unified Productive Study Activity (Phase 5):**
   * Screen study (`STUDYING_SCREEN`) and desk reading/writing (`STUDYING_READING_WRITING`) are aggregated under continuous productive studying.
   * Switching between them does not wipe cumulative study time, trigger recovery, or fire state transitions.
6. **State Machine Stabilization & Category Recovery (Phase 6):**
   * Implemented independent recovery conditions and stability windows:
     * Drowsiness recovery requires verified open eyes and upright posture.
     * Distraction recovery requires gaze facing workspace without phone.
     * Occlusion recovery requires face clearly visible.
     * Absence recovery requires student present in chair.
7. **Strict Audio Alert Gating (Phase 7):**
   * Gated audio playback strictly behind confirmed states, valid landmarks, non-diagnostic mode, and per-incident deduplication.
   * Fixed duplicate alert trigger bug where temporary 1-frame state flickers reset active alert cooldown.
8. **Real-Time Debug HUD Panel (Phase 9 & 10):**
   * Added live debug HUD panel displaying Left/Right/Avg EAR, Blendshape Blink score, Eye Status, Mesh validity, Head Pose, Drowsiness Evidence, and Alert Eligibility.
9. **Automated Validation Suite (Phase 8):**
   * Created [`backend/tests/integration/test_accuracy_overhaul.py`](file:///c:/Users/vinu/modal-object/backend/tests/integration/test_accuracy_overhaul.py) covering all 10 core audit tests (TEST A to TEST J) + Diagnostic Mode.
   * Total test count expanded from 71 to **82 tests with 100% pass rate**.

## [2.4.0] — 2026-10-31
### Added
- **Cinematic Zoom-In Intro Animation Sequence:**
  - Implemented 3.4s cinematic fullscreen opening experience with deep space indigo radial gradient and ambient floating neon particles.
  - Logo scales up from `0.2` to `1.0` with glowing cyan/electric blue halo and unblur effect.
  - Staggered typography reveal displaying `AI STUDY` and `FOCUS MONITOR` with wide letter-spacing and tagline `INTELLIGENCE • FOCUS • PERFORMANCE`.
  - Added cinematic blue light sweep and camera expansion transition zooming smoothly into the landing page hero section.
  - Integrated "Skip Intro" button, "↺ Replay Intro" trigger in navigation, session replay arbitration, and reduced-motion graceful fallback.
  - Fully verified with Vite production build (`vite build` in 225ms) and 94/94 passing tests.

---

## [2.3.0] — 2026-10-31
### Added
- **Futuristic AI SaaS Landing Page Redesign:**
  - Implemented cinematic SaaS hero section inspired by the visual reference image with dark navy `#060814` backdrop, deep indigo/violet ambient gradients, and electric neon lighting.
  - Added dual SVG layered 3D pedestal sculptures framing the hero viewport with smooth floating hovering animations.
  - Created interactive 3D perspective dashboard preview mockup showcasing live study feed simulation, 3D FaceMesh landmark points, confidence meters, and explainable AI reasoning.
  - Designed 8 feature capability cards with neon hover effects, 4-step horizontal workflow with glowing connector line, 8-card technology stack, privacy transparency section, and full product footer.
  - Built isolated stylesheet `frontend/src/styles/landing.css` and client router `frontend/src/landing.js`.
  - Preserved 100% of existing monitoring dashboard structure, IDs, and WebSocket/camera logic untouched.
  - Verified frontend production build (`vite build` in 223ms) and passed all 94 backend regression tests.

---

## [2.2.0] — 2026-10-31
### Added
- **Comprehensive Student Behaviour Policy & Taxonomy (`BehaviorCategory`):**
  - Integrated 11 parent categories: `PRODUCTIVE_STUDYING`, `DIGITAL_DISTRACTION`, `VISUAL_DISTRACTION`, `PHYSICAL_DISENGAGEMENT`, `DROWSINESS`, `PHYSICAL_DISTRACTION`, `SOCIAL_DISTRACTION`, `STUDY_AVOIDANCE`, `FACE_OCCLUSION`, `STUDENT_ABSENT`, `ACTIVITY_UNCONFIRMED`.
- **Granular Mobile Phone Interaction Pipeline (`PhoneInteractionStatus`):**
  - Distinguishes `PHONE_VISIBLE` (phone on desk), `PHONE_HELD` (hand-phone IoU overlap), `PHONE_IN_USE` (phone held + downward pitch/gaze), and `PHONE_CONFIRMED` (fast 0.8s confirmation window).
- **Ongoing Alert Audio Persistence:**
  - Prevented premature alert cancellation by maintaining `alert.active = True` during continuous incidents while enforcing cooldown deduplication.
- **New 18-Scenario Regression Test Suite (`test_behavior_policy_suite.py`):**
  - Added 12 new automated test cases covering phone presence vs usage, brief vs sustained look-aways, natural blinks vs fatigue, and material transitions. Total test suite expanded to 94 tests (100% PASS).
- **Live UI Observation Badges:**
  - Added real-time Phone Status and Behavioral Category indicators on the Web Dashboard.

---

## [2026-10-31] — Fix Local Mode Runtime Errors (Error 1 & Error 2) & Regression Suite

### What Changed
1. **Error 1 Fixed (`CentralAudioManager` missing `stop_alert`):**
   * Added `stop_alert()` alias on `CentralAudioManager` delegating to `stop()`.
   * Added `update_audio(state, now, cooldown)` alias on `CentralAudioManager` delegating to `update_state()`.
   * Added `process_frame()` and `last_observation` property on `FocusMonitor`.
2. **Error 2 Fixed (`tuple indices must be integers or slices, not str`):**
   * Identified root cause in [`backend/scripts/run_webcam.py`](file:///c:/Users/vinu/modal-object/backend/scripts/run_webcam.py#L30-L36): `draw_hud` attempted dictionary indexing (`disp["color"]`, `disp["label"]`) on `STATE_DISPLAY[state]`, which stores 2-tuples `(label_str, bgr_tuple)`.
   * Refactored `draw_hud` to unpack tuples safely: `label, color = disp[0], disp[1]`.
3. **Automated Regression Test Suite Added:**
   * Created [`backend/tests/regression/test_runtime_error_fixes.py`](file:///c:/Users/vinu/modal-object/backend/tests/regression/test_runtime_error_fixes.py) with 10 unit and regression tests:
     * `TestError1_StopAlertAttribute`: validates existence and behavior of `stop_alert()`, `update_audio()`, and `stop()`.
     * `TestError2_StateDisplayTupleAccess`: validates structure of `STATE_DISPLAY` tuples and tuple-access logic across all states.
     * `TestFocusMonitorProcessFrame`: validates `process_frame()` and `last_observation` contracts.
4. **End-to-End Local Mode & Full Suite Validation:**
   * Local native mode verified running continuously without errors on physical camera, processing YOLO and MediaPipe with diagnostic HUD and audio manager.
   * All 71 tests passing (61 existing + 10 new regression tests).

## [2.4.0] — 2026-10-31
### Added
- **Cinematic Zoom-In Intro Animation Sequence:**
  - Implemented 3.4s cinematic fullscreen opening experience with deep space indigo radial gradient and ambient floating neon particles.
  - Logo scales up from `0.2` to `1.0` with glowing cyan/electric blue halo and unblur effect.
  - Staggered typography reveal displaying `AI STUDY` and `FOCUS MONITOR` with wide letter-spacing and tagline `INTELLIGENCE • FOCUS • PERFORMANCE`.
  - Added cinematic blue light sweep and camera expansion transition zooming smoothly into the landing page hero section.
  - Integrated "Skip Intro" button, "↺ Replay Intro" trigger in navigation, session replay arbitration, and reduced-motion graceful fallback.
  - Fully verified with Vite production build (`vite build` in 225ms) and 94/94 passing tests.

---

## [2.3.0] — 2026-10-31
### Added
- **Futuristic AI SaaS Landing Page Redesign:**
  - Implemented cinematic SaaS hero section inspired by the visual reference image with dark navy `#060814` backdrop, deep indigo/violet ambient gradients, and electric neon lighting.
  - Added dual SVG layered 3D pedestal sculptures framing the hero viewport with smooth floating hovering animations.
  - Created interactive 3D perspective dashboard preview mockup showcasing live study feed simulation, 3D FaceMesh landmark points, confidence meters, and explainable AI reasoning.
  - Designed 8 feature capability cards with neon hover effects, 4-step horizontal workflow with glowing connector line, 8-card technology stack, privacy transparency section, and full product footer.
  - Built isolated stylesheet `frontend/src/styles/landing.css` and client router `frontend/src/landing.js`.
  - Preserved 100% of existing monitoring dashboard structure, IDs, and WebSocket/camera logic untouched.
  - Verified frontend production build (`vite build` in 223ms) and passed all 94 backend regression tests.

---

## [2.2.0] — 2026-10-31
### Added
- **Comprehensive Student Behaviour Policy & Taxonomy (`BehaviorCategory`):**
  - Integrated 11 parent categories: `PRODUCTIVE_STUDYING`, `DIGITAL_DISTRACTION`, `VISUAL_DISTRACTION`, `PHYSICAL_DISENGAGEMENT`, `DROWSINESS`, `PHYSICAL_DISTRACTION`, `SOCIAL_DISTRACTION`, `STUDY_AVOIDANCE`, `FACE_OCCLUSION`, `STUDENT_ABSENT`, `ACTIVITY_UNCONFIRMED`.
- **Granular Mobile Phone Interaction Pipeline (`PhoneInteractionStatus`):**
  - Distinguishes `PHONE_VISIBLE` (phone on desk), `PHONE_HELD` (hand-phone IoU overlap), `PHONE_IN_USE` (phone held + downward pitch/gaze), and `PHONE_CONFIRMED` (fast 0.8s confirmation window).
- **Ongoing Alert Audio Persistence:**
  - Prevented premature alert cancellation by maintaining `alert.active = True` during continuous incidents while enforcing cooldown deduplication.
- **New 18-Scenario Regression Test Suite (`test_behavior_policy_suite.py`):**
  - Added 12 new automated test cases covering phone presence vs usage, brief vs sustained look-aways, natural blinks vs fatigue, and material transitions. Total test suite expanded to 94 tests (100% PASS).
- **Live UI Observation Badges:**
  - Added real-time Phone Status and Behavioral Category indicators on the Web Dashboard.

---

## [2026-10-31] — Target Modular Architecture Reorganization & Unified Validation

### What Changed
1. **Full Workspace Target Restructuring:**
   * Restructured repository into decoupled, enterprise-grade architecture:
     * `backend/app/`: `api/` (`routes/`, `websocket/`), `core/`, `schemas/`, `models/`, `services/` (`detection/`, `behavior/`, `decision/`, `audio/`, `session/`, `recommendation/`, `analytics/`), `pipelines/`, `utils/`, `main.py`.
     * `backend/tests/`: `unit/`, `integration/`, `websocket/`.
     * `frontend/`: `public/`, `src/` (`components/`, `pages/`, `services/`, `hooks/`, `styles/`, `utils/`, `assets/`, `App.js`, `main.js`), `index.html`, `package.json`, `vite.config.js`.
     * `assets/`: `audio/`, `models/`, `icons/`.
     * `infrastructure/`: `docker/`, `deployment/`, `scripts/`.
     * `shared/contracts/`: JSON schema contracts for cross-language validation.
     * Root configuration: `AGENTS.md`, `README.md`, `.env.example`, `.gitignore`, `docker-compose.yml`, `run_app.py`.
2. **Perception & Pipeline Bug Fixes:**
   * Fixed `UnboundLocalError: yawn_detected` in `upper_body_detector.py` by ensuring defaults initialize in frames without face landmarks.
   * Fixed Pydantic type error in `session_pipeline.py` by converting `observable_study_activity` and `hand_near_face` into compliant primitives.
   * Implemented `reset()` method in `TemporalDecisionEngine` and `FocusMonitor` for clean state clearance.
   * Fixed Mode A Local Engine (`backend/scripts/run_webcam.py`):
     * Added `stop_alert()` and `update_audio()` method aliases on `CentralAudioManager` for backward-compatible lifecycle control.
     * Added `process_frame()` and `last_observation` properties to `FocusMonitor`.
     * Added stride-cached YOLO object detection overlay and safe HUD rendering to `run_webcam.py`.
3. **Frontend Vite & Static Asset Alignment:**
   * Replaced legacy HTML script tags with Vite module entrypoint (`/src/main.js`).
   * Configured static mounting and fallback for both production build (`dist/`) and dev server (`5173`).
4. **All 61 Automated Tests Passing 100%:**
   * 22 State Machine tests passed.
   * 8 Upper Body Detector tests passed.
   * 19 Critical Fixes tests passed.
   * 12 WebSocket and REST API tests passed.

## [2.4.0] — 2026-10-31
### Added
- **Cinematic Zoom-In Intro Animation Sequence:**
  - Implemented 3.4s cinematic fullscreen opening experience with deep space indigo radial gradient and ambient floating neon particles.
  - Logo scales up from `0.2` to `1.0` with glowing cyan/electric blue halo and unblur effect.
  - Staggered typography reveal displaying `AI STUDY` and `FOCUS MONITOR` with wide letter-spacing and tagline `INTELLIGENCE • FOCUS • PERFORMANCE`.
  - Added cinematic blue light sweep and camera expansion transition zooming smoothly into the landing page hero section.
  - Integrated "Skip Intro" button, "↺ Replay Intro" trigger in navigation, session replay arbitration, and reduced-motion graceful fallback.
  - Fully verified with Vite production build (`vite build` in 225ms) and 94/94 passing tests.

---

## [2.3.0] — 2026-10-31
### Added
- **Futuristic AI SaaS Landing Page Redesign:**
  - Implemented cinematic SaaS hero section inspired by the visual reference image with dark navy `#060814` backdrop, deep indigo/violet ambient gradients, and electric neon lighting.
  - Added dual SVG layered 3D pedestal sculptures framing the hero viewport with smooth floating hovering animations.
  - Created interactive 3D perspective dashboard preview mockup showcasing live study feed simulation, 3D FaceMesh landmark points, confidence meters, and explainable AI reasoning.
  - Designed 8 feature capability cards with neon hover effects, 4-step horizontal workflow with glowing connector line, 8-card technology stack, privacy transparency section, and full product footer.
  - Built isolated stylesheet `frontend/src/styles/landing.css` and client router `frontend/src/landing.js`.
  - Preserved 100% of existing monitoring dashboard structure, IDs, and WebSocket/camera logic untouched.
  - Verified frontend production build (`vite build` in 223ms) and passed all 94 backend regression tests.

---

## [2.2.0] — 2026-10-31
### Added
- **Comprehensive Student Behaviour Policy & Taxonomy (`BehaviorCategory`):**
  - Integrated 11 parent categories: `PRODUCTIVE_STUDYING`, `DIGITAL_DISTRACTION`, `VISUAL_DISTRACTION`, `PHYSICAL_DISENGAGEMENT`, `DROWSINESS`, `PHYSICAL_DISTRACTION`, `SOCIAL_DISTRACTION`, `STUDY_AVOIDANCE`, `FACE_OCCLUSION`, `STUDENT_ABSENT`, `ACTIVITY_UNCONFIRMED`.
- **Granular Mobile Phone Interaction Pipeline (`PhoneInteractionStatus`):**
  - Distinguishes `PHONE_VISIBLE` (phone on desk), `PHONE_HELD` (hand-phone IoU overlap), `PHONE_IN_USE` (phone held + downward pitch/gaze), and `PHONE_CONFIRMED` (fast 0.8s confirmation window).
- **Ongoing Alert Audio Persistence:**
  - Prevented premature alert cancellation by maintaining `alert.active = True` during continuous incidents while enforcing cooldown deduplication.
- **New 18-Scenario Regression Test Suite (`test_behavior_policy_suite.py`):**
  - Added 12 new automated test cases covering phone presence vs usage, brief vs sustained look-aways, natural blinks vs fatigue, and material transitions. Total test suite expanded to 94 tests (100% PASS).
- **Live UI Observation Badges:**
  - Added real-time Phone Status and Behavioral Category indicators on the Web Dashboard.

---

## [2026-10-30] — Release 2.0.0-rc1: Dual-Mode Platform, Reasoning Engine & Calibration

### What Changed
1. **Added Explainable AI Decision Rationale (Part 8):**
   * Added `DecisionRationale` Pydantic model to `app/schemas.py`.
   * Added `_build_decision_rationale()` in `app/session_pipeline.py`.
   * Added high-contrast reasoning card to `frontend/index.html` displaying:
     * Observation (Head direction, gaze, face)
     * Additional Evidence (Desk activity, EAR, posture, motion)
     * Decision (Authoritative state)
     * Audio Action (Alert status and priority)
2. **Added Personal Workspace Calibration (Part 9):**
   * Added `calibrate` action handling in `app/main.py` and `app/session_pipeline.py`.
   * Created interactive calibration wizard in `frontend/index.html` and `frontend/js/app.js` with progress animation and baseline posture capture.
3. **Enhanced Fatigue & Downward Pitch Perception (Part 1 & 5):**
   * Integrated Mouth Aspect Ratio (MAR) in `upper_body_detector.py` for automated yawn candidate detection.
   * Applied head pitch compensation to Eye Aspect Ratio (EAR) in `upper_body_detector.py` and `temporal_decision_engine.py` so looking down typing or reading does not trigger false drowsiness alarms.
4. **Resolved FastAPI Type Annotation & WebSocket Lifecycle:**
   * Added missing `typing.Any` import in `app/main.py`.
   * Fixed Starlette disconnect handling in `app/main.py` by breaking on `message.get("type") == "websocket.disconnect"`.
   * Updated `app/main.py` to reference existing `face_landmarker.task` files directly instead of missing `config.FACE_LANDMARKER_MODEL`.

### Modified Files
* `app/schemas.py`
* `app/session_pipeline.py`
* `app/main.py`
* `upper_body_detector.py`
* `behavior_types.py`
* `temporal_decision_engine.py`
* `frontend/index.html`
* `frontend/css/dashboard.css`
* `frontend/js/app.js`

### Verification & Tests Executed
* Backend unit health check: Verified `/api/health` and `/api/config`.
* Automated regression test suite: `tests/test_critical_fixes.py` (19/19 tests passed).
* Upper body monitor test suite: `tests/test_upper_body_monitor.py` (16/16 tests passed).
* Study monitor test suite: `tests/test_study_monitor.py` (14/14 tests passed).

## [2.4.0] — 2026-10-31
### Added
- **Cinematic Zoom-In Intro Animation Sequence:**
  - Implemented 3.4s cinematic fullscreen opening experience with deep space indigo radial gradient and ambient floating neon particles.
  - Logo scales up from `0.2` to `1.0` with glowing cyan/electric blue halo and unblur effect.
  - Staggered typography reveal displaying `AI STUDY` and `FOCUS MONITOR` with wide letter-spacing and tagline `INTELLIGENCE • FOCUS • PERFORMANCE`.
  - Added cinematic blue light sweep and camera expansion transition zooming smoothly into the landing page hero section.
  - Integrated "Skip Intro" button, "↺ Replay Intro" trigger in navigation, session replay arbitration, and reduced-motion graceful fallback.
  - Fully verified with Vite production build (`vite build` in 225ms) and 94/94 passing tests.

---

## [2.3.0] — 2026-10-31
### Added
- **Futuristic AI SaaS Landing Page Redesign:**
  - Implemented cinematic SaaS hero section inspired by the visual reference image with dark navy `#060814` backdrop, deep indigo/violet ambient gradients, and electric neon lighting.
  - Added dual SVG layered 3D pedestal sculptures framing the hero viewport with smooth floating hovering animations.
  - Created interactive 3D perspective dashboard preview mockup showcasing live study feed simulation, 3D FaceMesh landmark points, confidence meters, and explainable AI reasoning.
  - Designed 8 feature capability cards with neon hover effects, 4-step horizontal workflow with glowing connector line, 8-card technology stack, privacy transparency section, and full product footer.
  - Built isolated stylesheet `frontend/src/styles/landing.css` and client router `frontend/src/landing.js`.
  - Preserved 100% of existing monitoring dashboard structure, IDs, and WebSocket/camera logic untouched.
  - Verified frontend production build (`vite build` in 223ms) and passed all 94 backend regression tests.

---

## [2.2.0] — 2026-10-31
### Added
- **Comprehensive Student Behaviour Policy & Taxonomy (`BehaviorCategory`):**
  - Integrated 11 parent categories: `PRODUCTIVE_STUDYING`, `DIGITAL_DISTRACTION`, `VISUAL_DISTRACTION`, `PHYSICAL_DISENGAGEMENT`, `DROWSINESS`, `PHYSICAL_DISTRACTION`, `SOCIAL_DISTRACTION`, `STUDY_AVOIDANCE`, `FACE_OCCLUSION`, `STUDENT_ABSENT`, `ACTIVITY_UNCONFIRMED`.
- **Granular Mobile Phone Interaction Pipeline (`PhoneInteractionStatus`):**
  - Distinguishes `PHONE_VISIBLE` (phone on desk), `PHONE_HELD` (hand-phone IoU overlap), `PHONE_IN_USE` (phone held + downward pitch/gaze), and `PHONE_CONFIRMED` (fast 0.8s confirmation window).
- **Ongoing Alert Audio Persistence:**
  - Prevented premature alert cancellation by maintaining `alert.active = True` during continuous incidents while enforcing cooldown deduplication.
- **New 18-Scenario Regression Test Suite (`test_behavior_policy_suite.py`):**
  - Added 12 new automated test cases covering phone presence vs usage, brief vs sustained look-aways, natural blinks vs fatigue, and material transitions. Total test suite expanded to 94 tests (100% PASS).
- **Live UI Observation Badges:**
  - Added real-time Phone Status and Behavioral Category indicators on the Web Dashboard.

---

## [2026-10-29] — Critical Pipeline Fixes & Dual-Mode Integration

### What Changed
1. **YOLO Stride Caching Bug Fixed:**
   * Added `cached_yolo_info` and `cached_yolo_results` in `run_webcam_yolo.py` so skipped frames (`YOLO_INFERENCE_STRIDE > 1`) do not clear object detections or reset timers.
2. **Missing Face Bounding Box Blindspot Fixed:**
   * Added head coordinate estimation from shoulders/person box when MediaPipe FaceMesh drops out during deliberate face concealment.
3. **Swallowed Exceptions Fixed:**
   * Caught and logged MediaPipe inference exceptions, setting `features.inference_error = True` to transition to `CAMERA_ERROR` instead of silently assuming attentiveness.
4. **Micro-Glance Timer Resets Fixed:**
   * Added persistent `_repeated_turns_start` and `_inactivity_start` timers in `temporal_decision_engine.py`.
5. **Thinking Posture Discrimination:**
   * Separated `face_resting_on_hand` while facing screen (contemplation/lecture watching) from idle distraction.
6. **Built Dual-Mode Execution Architecture:**
   * Created unified CLI entrypoint `run_app.py` supporting `--mode local`, `--mode web`, and `--mode dev`.
   * Created FastAPI backend (`app/main.py`, `app/session_pipeline.py`, `app/yolo_service.py`).
   * Created browser dashboard (`frontend/index.html`, `frontend/css/dashboard.css`, `frontend/js/`).

### Modified Files
* `run_app.py`
* `run_webcam_yolo.py`
* `config.py`
* `behavior_types.py`
* `upper_body_detector.py`
* `temporal_decision_engine.py`
* `focus_monitor.py`
* `state_machine.py`
* `audio_alerts.py`
* `logger.py`
* `tests/test_critical_fixes.py`

### Verification & Tests Executed
* `python evaluate_study_monitor.py`: 0.00 False Alarms/hr, 98.5% reading accuracy, 100% occlusion accuracy.
* `python evaluate_upper_body.py`: `POSSIBLE_DISTRACTION` precision 0.987, `POSSIBLE_DROWSINESS` precision 0.958, `CAMERA_ERROR` precision 0.968.

