/**
 * frontend/src/App.js — Real-Time AI Study Focus Monitor
 * Streamlined, High-Accuracy Architecture:
 *   - Camera Stream & HUD Target Box Overlay
 *   - WebSocket bi-directional streaming with flow control
 *   - Single Authoritative Current Activity Display
 *   - Direct Multi-Modal Signal Diagnostics (Eyes, Head Pose, Phone, Duration)
 *   - Central Audio Alert Triggering
 */

import { CameraManager } from "./utils/camera_manager.js";
import { MonitorWebSocketClient } from "./services/websocket_client.js";
import { BrowserAudioController } from "./utils/audio_controller.js";

// Canonical eye landmark indices matching visual reference media_1793469479412_2be6ffaf.jpg
// Screen-Left Eye (User Right Eye)
const RIGHT_EYE_CONTOUR = [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7, 33];
const RIGHT_EYE_CORNERS = [33, 133];
const RIGHT_EYE_EYELIDS = [160, 159, 158, 144, 145, 153];
const RIGHT_IRIS_RING   = [469, 470, 471, 472];
const RIGHT_PUPIL_CENTER = 468;

// Screen-Right Eye (User Left Eye)
const LEFT_EYE_CONTOUR  = [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382, 362];
const LEFT_EYE_CORNERS  = [362, 263];
const LEFT_EYE_EYELIDS  = [385, 386, 387, 380, 374, 373];
const LEFT_IRIS_RING    = [474, 475, 476, 477];
const LEFT_PUPIL_CENTER  = 473;

export class StudyMonitorApp {
  constructor() {
    // 1. DOM Elements
    this.videoEl = document.getElementById("webcam-video");
    this.captureCanvas = document.getElementById("hidden-capture-canvas");
    this.hudCanvas = document.getElementById("hud-overlay-canvas");
    this.placeholderEl = document.getElementById("video-placeholder");
    this.errorBannerEl = document.getElementById("camera-error-banner");
    this.errorMessageEl = document.getElementById("camera-error-message");

    // Header Status Indicators
    this.topCameraStatus = document.getElementById("top-camera-status");
    this.topCameraDot = document.getElementById("top-camera-dot");
    this.sessionStatusText = document.getElementById("session-status-text");
    this.topWsDot = document.getElementById("top-ws-dot");

    // Video Resolution Badge
    this.videoResTag = document.getElementById("video-res-tag");

    // Controls
    this.startBtn = document.getElementById("start-btn");
    this.stopBtn = document.getElementById("stop-btn");
    this.audioToggleBtn = document.getElementById("audio-toggle-btn");
    this.audioBadge = document.getElementById("audio-badge");
    this.overlayToggleBtn = document.getElementById("overlay-toggle-btn");
    this.overlayBadge = document.getElementById("overlay-badge");

    // Current Activity Elements
    this.activityHeroBox = document.getElementById("activity-hero-box");
    this.activityLabel = document.getElementById("activity-label");
    this.activityDesc = document.getElementById("activity-desc");
    this.activityStatusTag = document.getElementById("activity-status-tag");

    // Diagnostic Signals
    this.sigEyesVal = document.getElementById("obs-eyes-val");
    this.sigHeadVal = document.getElementById("obs-pose-val");
    this.sigPhoneVal = document.getElementById("obs-phone-val");
    this.sigDurationVal = document.getElementById("obs-face-val");

    // Subsystems
    this.camera = new CameraManager(this.videoEl, this.captureCanvas);
    this.wsClient = new MonitorWebSocketClient();
    this.audioCtrl = new BrowserAudioController();

    // Ephemeral In-Memory State
    this.isMonitoring = false;
    this.showDebugOverlay = true;
    this.frameIntervalTimer = null;
    this.targetFps = 10;
    this.frameIntervalMs = 1000 / this.targetFps;

    // Initialize Event Handlers
    this.initEventListeners();
    this.initWebSocketCallbacks();
  }

  // =========================================================================
  // EVENT LISTENERS & CONTROLS
  // =========================================================================
  initEventListeners() {
    this.startBtn?.addEventListener("click", () => this.handleStartMonitoring());
    this.stopBtn?.addEventListener("click", () => this.handleStopMonitoring());
    this.audioToggleBtn?.addEventListener("click", () => this.handleToggleAudio());
    this.overlayToggleBtn?.addEventListener("click", () => this.handleToggleOverlay());
  }

  initWebSocketCallbacks() {
    this.wsClient.onStatusChange = (status) => {
      if (this.sessionStatusText) {
        this.sessionStatusText.textContent = status.connected ? "Active" : "Idle";
      }
      if (this.topWsDot) {
        this.topWsDot.className = status.connected ? "status-dot active" : "status-dot";
      }
    };

    this.wsClient.onEvent = (data) => {
      this.handleWebSocketMessage(data);
    };

    this.wsClient.onMessage = (data) => {
      this.handleWebSocketMessage(data);
    };

    this.wsClient.onError = (err) => {
      console.warn("[Monitor] WebSocket error:", err);
    };
  }

  // =========================================================================
  // MONITORING LIFECYCLE (START, STOP)
  // =========================================================================
  async handleStartMonitoring() {
    if (this.isMonitoring) return;

    // Immediately unlock browser audio on user gesture
    this.audioCtrl.unlockAudio();

    if (this.errorBannerEl) this.errorBannerEl.style.display = "none";
    this.setCameraStatus("Starting...", "warning");

    // 1. Request Webcam
    const camResult = await this.camera.startCamera();
    if (!camResult.success) {
      this.showCameraError(camResult.error || "Could not access webcam.");
      this.setCameraStatus("Error", "error");
      return;
    }

    if (this.placeholderEl) this.placeholderEl.style.display = "none";
    this.setCameraStatus("Active", "active");

    if (this.videoResTag && this.videoEl) {
      const w = this.videoEl.videoWidth || 640;
      const h = this.videoEl.videoHeight || 480;
      this.videoResTag.textContent = `${w}x${h}`;
    }

    // 2. Connect WebSocket Stream
    this.wsClient.connect();

    // 3. Mark Monitoring State & Toggle Buttons
    this.isMonitoring = true;
    if (this.startBtn) this.startBtn.style.display = "none";
    if (this.stopBtn) this.stopBtn.style.display = "inline-flex";

    // 4. Start Video Frame Capture Loop
    this.startStreamingLoop();
  }

  handleStopMonitoring() {
    if (!this.isMonitoring) return;

    this.isMonitoring = false;

    // 1. Stop Streaming Loop
    if (this.frameIntervalTimer) {
      clearInterval(this.frameIntervalTimer);
      this.frameIntervalTimer = null;
    }

    // 2. Stop Camera
    this.camera.stopCamera();
    this.setCameraStatus("Standby", "idle");

    // 3. Disconnect WebSocket
    this.wsClient.disconnect();

    // 4. Clear Video Canvas & Placeholder
    if (this.placeholderEl) this.placeholderEl.style.display = "flex";
    this.clearHudCanvas();

    // 5. Toggle Buttons
    if (this.startBtn) this.startBtn.style.display = "inline-flex";
    if (this.stopBtn) this.stopBtn.style.display = "none";

    // 6. Stop active audio alerts
    this.audioCtrl.stop();

    // 7. Reset UI Labels
    if (this.activityLabel) this.activityLabel.textContent = "STANDBY";
    if (this.activityDesc) this.activityDesc.textContent = "Monitoring stopped.";
    if (this.activityStatusTag) {
      this.activityStatusTag.textContent = "STANDBY";
      this.activityStatusTag.className = "activity-stability-tag";
    }
    if (this.activityHeroBox) this.activityHeroBox.className = "activity-hero-box";
  }

  handleToggleAudio() {
    const isEnabled = this.audioCtrl.toggleMute();
    if (this.audioBadge) {
      this.audioBadge.textContent = isEnabled ? "ON" : "OFF";
      this.audioBadge.className = isEnabled ? "badge-pill-on" : "badge-pill-off";
    }
  }

  handleToggleOverlay() {
    this.showDebugOverlay = !this.showDebugOverlay;
    if (this.overlayBadge) {
      this.overlayBadge.textContent = this.showDebugOverlay ? "ON" : "OFF";
      this.overlayBadge.className = this.showDebugOverlay ? "badge-pill-on" : "badge-pill-off";
    }
    if (!this.showDebugOverlay) {
      this.clearHudCanvas();
    }
  }

  setCameraStatus(text, status) {
    if (this.topCameraStatus) this.topCameraStatus.textContent = text;
    if (this.topCameraDot) {
      this.topCameraDot.className = "status-dot";
      if (status === "active") this.topCameraDot.classList.add("active");
      else if (status === "warning") this.topCameraDot.classList.add("warning");
      else if (status === "error") this.topCameraDot.classList.add("error");
    }
  }

  // =========================================================================
  // FRAME STREAMING WITH FLOW CONTROL
  // =========================================================================
  startStreamingLoop() {
    if (this.frameIntervalTimer) clearInterval(this.frameIntervalTimer);

    this.frameIntervalTimer = setInterval(async () => {
      if (!this.isMonitoring) return;

      try {
        // Flow control: wait for server ACK before transmitting next frame
        if (this.wsClient && typeof this.wsClient.canSendFrame === "function") {
          if (!this.wsClient.canSendFrame()) return;
        }

        const captureFn = this.camera.captureJpegBlob || this.camera.captureFrameBlob;
        if (!captureFn) return;

        const frameBlob = await captureFn.call(this.camera, 0.70);
        if (frameBlob && this.wsClient && this.isMonitoring) {
          this.wsClient.sendFrame(frameBlob);
        }
      } catch (err) {
        console.warn("[Monitor] Streaming loop capture error:", err);
      }
    }, this.frameIntervalMs);
  }

  // =========================================================================
  // WEBSOCKET MESSAGE HANDLER & STATE UPDATE
  // =========================================================================
  handleWebSocketMessage(data) {
    if (!data) return;
    this.updateUI(data);
  }

  updateUI(data) {
    const obs = data.observations || {};

    // 1. Primary Activity Label & Description
    const activityName = data.activity_label || data.state || "STUDYING";
    const confStatus = data.confirmation_status || "CONFIRMED";
    const reason = data.diagnostic_reason || (data.recommendation && data.recommendation.message) || "";

    if (this.activityLabel) this.activityLabel.textContent = activityName;
    if (this.activityDesc) this.activityDesc.textContent = reason;

    if (this.activityStatusTag) {
      this.activityStatusTag.textContent = confStatus;
      if (confStatus === "CONFIRMED") {
        this.activityStatusTag.className = "activity-stability-tag";
      } else if (confStatus === "POSSIBLE") {
        this.activityStatusTag.className = "activity-stability-tag possible";
      } else {
        this.activityStatusTag.className = "activity-stability-tag alert";
      }
    }

    // 2. Activity Hero Box Styling based on state category
    if (this.activityHeroBox) {
      this.activityHeroBox.className = "activity-hero-box";
      const upper = activityName.toUpperCase();
      if (upper.includes("STUDY") || upper.includes("READ") || upper.includes("WRITE")) {
        this.activityHeroBox.classList.add("state-studying");
      } else if (upper.includes("DROWS") || upper.includes("PHONE") || upper.includes("OCCLUD") || upper.includes("AWAY")) {
        this.activityHeroBox.classList.add("state-alert");
      } else {
        this.activityHeroBox.classList.add("state-warning");
      }
    }

    // 3. Compact Diagnostic Signals
    if (this.sigEyesVal) {
      this.sigEyesVal.textContent = obs.eye_state || "UNKNOWN";
    }

    if (this.sigHeadVal) {
      const hd = obs.head_direction || "Facing Screen";
      this.sigHeadVal.textContent = hd.replace(/_/g, " ");
    }

    if (this.sigPhoneVal) {
      if (obs.phone_status && obs.phone_status !== "NONE") {
        this.sigPhoneVal.textContent = obs.phone_status.replace(/_/g, " ");
      } else {
        this.sigPhoneVal.textContent = obs.phone_present ? "In Use" : "Not Detected";
      }
    }

    if (this.sigDurationVal) {
      const dur = typeof data.duration_seconds === "number" ? data.duration_seconds.toFixed(1) : "0.0";
      this.sigDurationVal.textContent = `${activityName} (${dur}s)`;
    }

    // 4. Draw HUD Overlay (green face bounding box with brackets)
    this.drawHudOverlay(obs);

    // 5. Audio Alert Evaluation
    if (data.alert) {
      this.audioCtrl.evaluateAlert(data.alert);
    }
  }

  // =========================================================================
  // HUD OVERLAY RENDERING (Target Bounding Box)
  // =========================================================================
  drawHudOverlay(obs) {
    if (!this.hudCanvas || !this.videoEl) return;
    const ctx = this.hudCanvas.getContext("2d");
    if (!ctx) return;

    const w = this.videoEl.videoWidth || 640;
    const h = this.videoEl.videoHeight || 480;

    if (this.hudCanvas.width !== w || this.hudCanvas.height !== h) {
      this.hudCanvas.width = w;
      this.hudCanvas.height = h;
    }

    ctx.clearRect(0, 0, w, h);

    // If overlay is disabled, skip all drawing
    if (!this.showDebugOverlay) return;

    // 1. Draw Eye-Only Landmarks matching visual reference media_1793469479412_2be6ffaf.jpg
    if (obs.face_landmarks && Array.isArray(obs.face_landmarks) && obs.face_landmarks.length >= 468) {
      const flm = obs.face_landmarks;
      const getPt = (idx) => [flm[idx][0] * w, flm[idx][1] * h];

      const drawEye = (contour, corners, eyelids, irisRing, pupilIdx) => {
        // A. Yellow eyelid contour boundary
        ctx.strokeStyle = "#facc15"; // Bright yellow
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        for (let i = 0; i < contour.length; i++) {
          if (contour[i] >= flm.length) continue;
          const pt = getPt(contour[i]);
          if (i === 0) ctx.moveTo(pt[0], pt[1]);
          else ctx.lineTo(pt[0], pt[1]);
        }
        ctx.stroke();

        // B. Pink/Magenta dots at inner & outer eye corners
        ctx.fillStyle = "#ec4899"; // Pink / Magenta
        for (const idx of corners) {
          if (idx >= flm.length) continue;
          const pt = getPt(idx);
          ctx.beginPath();
          ctx.arc(pt[0], pt[1], 3.0, 0, 2 * Math.PI);
          ctx.fill();
        }

        // C. Red dots along upper and lower eyelid margins
        ctx.fillStyle = "#ef4444"; // Vivid red
        for (const idx of eyelids) {
          if (idx >= flm.length) continue;
          const pt = getPt(idx);
          ctx.beginPath();
          ctx.arc(pt[0], pt[1], 2.2, 0, 2 * Math.PI);
          ctx.fill();
        }

        // D. Green iris boundary ring and Yellow pupil crosshair (when iris landmarks present)
        if (flm.length >= 478 && irisRing && pupilIdx !== undefined && pupilIdx < flm.length) {
          // Green iris ring
          ctx.strokeStyle = "#22c55e"; // Vivid green
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          for (let i = 0; i < irisRing.length; i++) {
            if (irisRing[i] >= flm.length) continue;
            const pt = getPt(irisRing[i]);
            if (i === 0) ctx.moveTo(pt[0], pt[1]);
            else ctx.lineTo(pt[0], pt[1]);
          }
          ctx.closePath();
          ctx.stroke();

          // Yellow '+' crosshair at pupil center
          const pupil = getPt(pupilIdx);
          ctx.strokeStyle = "#facc15";
          ctx.lineWidth = 1.8;
          const crossSize = 3.5;
          ctx.beginPath();
          ctx.moveTo(pupil[0] - crossSize, pupil[1]);
          ctx.lineTo(pupil[0] + crossSize, pupil[1]);
          ctx.moveTo(pupil[0], pupil[1] - crossSize);
          ctx.lineTo(pupil[0], pupil[1] + crossSize);
          ctx.stroke();
        }
      };

      ctx.save();
      // Render Screen-Left (User Right) Eye
      drawEye(RIGHT_EYE_CONTOUR, RIGHT_EYE_CORNERS, RIGHT_EYE_EYELIDS, RIGHT_IRIS_RING, RIGHT_PUPIL_CENTER);
      // Render Screen-Right (User Left) Eye
      drawEye(LEFT_EYE_CONTOUR, LEFT_EYE_CORNERS, LEFT_EYE_EYELIDS, LEFT_IRIS_RING, LEFT_PUPIL_CENTER);
      ctx.restore();
    }

    // 2. Draw Person Bounding Box if detected and face not yet isolated
    if (obs.person_box && Array.isArray(obs.person_box) && obs.person_box.length === 4) {
      const [px1, py1, px2, py2] = obs.person_box;
      const pbw = px2 - px1;
      const pbh = py2 - py1;
      if (pbw > 30 && pbh > 30) {
        ctx.save();
        ctx.strokeStyle = obs.face_box ? "rgba(59, 130, 246, 0.45)" : "#3b82f6"; // Blue/Cyan
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(px1, py1, pbw, pbh);
        ctx.setLineDash([]);
        if (!obs.face_box) {
          ctx.fillStyle = "rgba(59, 130, 246, 0.85)";
          ctx.fillRect(px1, Math.max(0, py1 - 22), 120, 20);
          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 11px -apple-system, sans-serif";
          ctx.fillText("[Person Detected]", px1 + 6, Math.max(14, py1 - 7));
        }
        ctx.restore();
      }
    }

    // 4. Draw Face Bounding Box if detected
    if (obs.face_box && Array.isArray(obs.face_box) && obs.face_box.length === 4) {
      const [x1, y1, x2, y2] = obs.face_box;
      const bw = x2 - x1;
      const bh = y2 - y1;
      const corner = Math.min(20, Math.floor(bw * 0.2));

      ctx.save();
      ctx.strokeStyle = "#10b981"; // Vibrant Emerald Green
      ctx.lineWidth = 2.5;

      // Outer bounding rectangle
      ctx.strokeRect(x1, y1, bw, bh);

      // Corner target brackets
      ctx.lineWidth = 4;
      ctx.beginPath();
      // Top-Left
      ctx.moveTo(x1, y1 + corner);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x1 + corner, y1);
      // Top-Right
      ctx.moveTo(x2 - corner, y1);
      ctx.lineTo(x2, y1);
      ctx.lineTo(x2, y1 + corner);
      // Bottom-Left
      ctx.moveTo(x1, y2 - corner);
      ctx.lineTo(x1, y2);
      ctx.lineTo(x1 + corner, y2);
      // Bottom-Right
      ctx.moveTo(x2 - corner, y2);
      ctx.lineTo(x2, y2);
      ctx.lineTo(x2, y2 - corner);
      ctx.stroke();

      // Badge tag above target box
      ctx.fillStyle = "rgba(16, 185, 129, 0.9)";
      ctx.fillRect(x1, Math.max(0, y1 - 24), Math.max(120, corner * 4), 22);

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px -apple-system, sans-serif";
      ctx.fillText("[Face Detected]", x1 + 8, Math.max(15, y1 - 8));

      ctx.restore();
    }

    // 5. Draw Mobile Phone Bounding Box if detected
    if (obs.phone_present && obs.phone_box && Array.isArray(obs.phone_box) && obs.phone_box.length === 4) {
      const [phx1, phy1, phx2, phy2] = obs.phone_box;
      const phw = phx2 - phx1;
      const phh = phy2 - phy1;
      if (phw > 10 && phh > 10) {
        ctx.save();
        ctx.strokeStyle = "#ef4444"; // Red / Amber alert
        ctx.lineWidth = 2.5;
        ctx.strokeRect(phx1, phy1, phw, phh);
        ctx.fillStyle = "rgba(239, 68, 68, 0.9)";
        ctx.fillRect(phx1, Math.max(0, phy1 - 22), 115, 20);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 11px -apple-system, sans-serif";
        ctx.fillText("[Phone Alert]", phx1 + 6, Math.max(14, phy1 - 7));
        ctx.restore();
      }
    }
  }

  clearHudCanvas() {
    if (!this.hudCanvas) return;
    const ctx = this.hudCanvas.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, this.hudCanvas.width, this.hudCanvas.height);
  }

  showCameraError(msg) {
    if (this.errorBannerEl) {
      this.errorBannerEl.style.display = "flex";
      if (this.errorMessageEl) this.errorMessageEl.textContent = msg;
    }
  }
}
