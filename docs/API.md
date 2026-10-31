# API & Communication Contract (API) — AI Study Focus Monitor

This document is the authoritative specification for all REST endpoints, WebSocket message schemas, error protocols, and frontend-backend contracts.

---

## 1. Base URL & Protocol Information
* **Default Host:** `127.0.0.1`
* **Backend Port:** `8000`
* **REST Base URL:** `http://127.0.0.1:8000/api`
* **WebSocket URL:** `ws://127.0.0.1:8000/ws/monitor`
* **CORS Policy:** Allowed origins: `*` (configured for local development in `app/main.py`).

---

## 2. REST Endpoints

### 2.1 Health Check
* **Endpoint:** `GET /api/health`
* **Description:** Returns server health, uptime, active sessions count, CUDA/device status, and MediaPipe model task file availability.
* **Response `200 OK`:**
```json
{
  "status": "healthy",
  "uptime_seconds": 142.5,
  "device": "cuda",
  "yolo_loaded": true,
  "active_sessions_count": 1,
  "media_pipe_tasks": {
    "face_landmarker": true,
    "pose_landmarker": true,
    "hand_landmarker": true
  }
}
```

---

### 2.2 System Configuration
* **Endpoint:** `GET /api/config`
* **Description:** Exposes active detection thresholds, timeouts, and cooldown durations from `config.py`.
* **Response `200 OK`:**
```json
{
  "distraction_threshold_sec": 4.0,
  "inactivity_threshold_sec": 12.0,
  "occlusion_threshold_sec": 3.5,
  "drowsiness_threshold_sec": 1.8,
  "absence_threshold_sec": 6.0,
  "recovery_threshold_sec": 1.2,
  "alert_cooldown_sec": 15.0,
  "ear_threshold": 0.20
}
```

---

### 2.3 Reset Monitoring Session
* **Endpoint:** `POST /api/session/reset`
* **Description:** Resets internal state machines, duration timers, and frame counters for an active session.
* **Request Body:**
```json
{
  "action": "reset",
  "session_id": "9b1deb4d3b7d4bad9bdd2b0d7b3dcb6d"
}
```
* **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "Session 9b1deb4d3b7d4bad9bdd2b0d7b3dcb6d reset."
}
```
* **Response `404 Not Found`:**
```json
{
  "status": "error",
  "message": "Session not found or unspecified."
}
```

---

## 3. WebSocket Real-Time Stream

### 3.1 Endpoint Overview
* **Endpoint:** `WS /ws/monitor`
* **Handshake:** Standard WebSocket upgrade over HTTP.
* **Session Lifecycle:**
  1. **Connect:** Server generates a unique `session_id`, allocates an isolated `SessionPipeline`, and immediately sends an initial `StateUpdateEvent`.
  2. **Streaming:** Client sends binary JPEG frame blobs (~7.5–10 FPS). Server replies with `StateUpdateEvent` JSON.
  3. **Control:** Client sends text JSON commands (`reset`, `ping`, `calibrate`).
  4. **Disconnect:** Server cleans up the session and removes it from `active_sessions`.

---

### 3.2 Client-to-Server Messages

#### A. Video Frame Message (Binary)
* **Payload Type:** `Blob` / `ArrayBuffer` (JPEG encoded bytes).
* **Constraints:** Max size 2.5 MB (`MAX_FRAME_BYTES`). Recommended capture dimensions: 640x480 at quality 0.70.

#### B. Text Control Commands (JSON String)
* **Ping:**
  ```json
  { "action": "ping" }
  ```
  *Server Response:* `{"type": "pong", "timestamp": 1730198000.12}`
* **Reset Session:**
  ```json
  { "action": "reset" }
  ```
  *Server Response:* `{"type": "info", "message": "Session reset successful."}`
* **Apply Personal Calibration:**
  ```json
  {
    "action": "calibrate",
    "calibration_data": {
      "calibrated": true,
      "pitch_offset": -3.2,
      "yaw_offset": 1.1,
      "timestamp": 1730198000.12
    }
  }
  ```
  *Server Response:* `{"type": "info", "message": "Calibration profile applied successfully."}`

---

### 3.3 Server-to-Client Messages: `StateUpdateEvent`
Emitted immediately upon processing each received frame. Serves as both data update and flow control acknowledgment.

```json
{
  "session_id": "a1b2c3d4e5f67890",
  "timestamp": 1730198005.42,
  "frame_id": 142,
  "state": "STUDYING_READING",
  "state_display": "[READ] READING / NOTES",
  "state_color": [0, 220, 140],
  "confidence": 0.94,
  "duration_seconds": 4.2,
  "observations": {
    "face_present": true,
    "face_occluded": false,
    "person_present": true,
    "head_direction": "TILTED_DOWN",
    "eye_state": "OPEN",
    "ear": 0.24,
    "observable_study_activity": "READING",
    "inactivity_duration": 0.0,
    "hand_near_face": false,
    "camera_health": "OK",
    "detection_confidence": 0.95,
    "mouth_open_yawn": false,
    "head_pitch_deg": 18.4,
    "head_yaw_deg": 2.1,
    "posture_name": "UPRIGHT",
    "book_present": true,
    "phone_present": false,
    "laptop_present": false
  },
  "active_behaviors": [
    "STUDYING_READING_WRITING"
  ],
  "diagnostic_reason": "State: STUDYING_READING_WRITING (0.94) | Reading book/notes",
  "alert": {
    "active": false,
    "name": null,
    "priority": null,
    "audio_file": null,
    "reason": "Clean study activity or recovery in progress."
  },
  "recommendation": {
    "title": "Great Study Flow!",
    "message": "Consistent reading focus detected. You're in a great concentration rhythm—keep it up!",
    "reason": "Attentive posture, active eye gaze, and study engagement verified.",
    "severity": "positive"
  },
  "decision_rationale": {
    "primary_observation": "Head direction = Tilted Down",
    "additional_evidence": [
      "Book/Notebook = Visible on desk",
      "Eyes = Open (EAR: 0.24)",
      "Body posture = Upright",
      "Motion score = Normal motion (0.04)"
    ],
    "decision": "STUDYING_READING",
    "audio_action": "No alert (Clean study activity or recovery in progress.)"
  }
}
```

---

## 4. Error Handling Protocol
* **Corrupt Image Decoding:** Server does not crash; returns `StateUpdateEvent` with `state="CAMERA_ERROR"`, `observations.camera_health="FAULT"`, and `recommendation.severity="critical"`.
* **Payload > 2.5 MB:** Rejected with `CAMERA_ERROR` and diagnostic reason `"Payload size exceeded maximum allowed limit (2.5MB)"`.
* **WebSocket Unexpected Disconnect:** Caught gracefully in `finally:` block of `app/main.py`; invokes `session.close()` to release all native C++ models and memory immediately.

