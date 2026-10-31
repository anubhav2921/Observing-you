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

      // Flow control: wait for server ACK before transmitting next frame
      if (!this.wsClient.canSendFrame()) return;

      const frameBlob = await this.camera.captureJpegBlob(0.70);
      if (frameBlob) {
        this.wsClient.sendFrame(frameBlob);
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

    // Draw Face Bounding Box if detected
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
      ctx.fillRect(x1, y1 - 24, Math.max(120, corner * 4), 22);

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px -apple-system, sans-serif";
      ctx.fillText("[Face Detected]", x1 + 8, y1 - 8);

      ctx.restore();
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
