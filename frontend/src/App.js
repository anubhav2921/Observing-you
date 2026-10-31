/**
 * frontend/js/app.js — Main Web Application Controller
 * Coordinates CameraManager, WebSocketClient, AudioController, and UI rendering.
 */

import { CameraManager } from "./utils/camera_manager.js";
import { MonitorWebSocketClient } from "./services/websocket_client.js";
import { BrowserAudioController } from "./utils/audio_controller.js";

class StudyMonitorApp {
  constructor() {
    // DOM Elements
    this.videoEl = document.getElementById("webcam-video");
    this.captureCanvas = document.getElementById("hidden-capture-canvas");
    this.hudCanvas = document.getElementById("hud-overlay-canvas");
    this.placeholderEl = document.getElementById("video-placeholder");
    this.errorBannerEl = document.getElementById("camera-error-banner");
    this.errorMessageEl = document.getElementById("camera-error-message");

    // Controls
    this.startBtn = document.getElementById("start-btn");
    this.stopBtn = document.getElementById("stop-btn");
    this.cameraPermBtn = document.getElementById("camera-perm-btn");
    this.resetBtn = document.getElementById("reset-btn");
    this.audioToggleBtn = document.getElementById("audio-toggle-btn");
    this.audioIcon = document.getElementById("audio-icon");
    this.audioText = document.getElementById("audio-text");
    this.clearHistoryBtn = document.getElementById("clear-history-btn");

    // Status & Header
    this.connectionBadge = document.getElementById("connection-badge");
    this.connectionText = document.getElementById("connection-text");
    this.cameraInfoBar = document.getElementById("camera-info-bar");
    this.cameraStatusText = document.getElementById("camera-status-text");
    this.sessionDurationEl = document.getElementById("session-duration");
    this.fpsValueEl = document.getElementById("fps-value");

    // State & Cards
    this.stateCard = document.getElementById("state-card");
    this.stateNameEl = document.getElementById("state-name");
    this.stateDurationBadge = document.getElementById("state-duration-badge");
    this.confidenceBar = document.getElementById("confidence-bar");
    this.confidenceValue = document.getElementById("confidence-value");

    // Recommendation Panel
    this.recCard = document.getElementById("recommendation-card");
    this.recTitle = document.getElementById("recommendation-title");
    this.recMessage = document.getElementById("recommendation-message");
    this.recReason = document.getElementById("recommendation-reason");
    this.recSeverity = document.getElementById("recommendation-severity");

    // Observations
    this.obsFacePresent = document.getElementById("obs-face-present-val");
    this.obsFaceOccluded = document.getElementById("obs-face-occluded-val");
    this.obsPersonPresent = document.getElementById("obs-person-present-val");
    this.obsHeadDirection = document.getElementById("obs-head-direction-val");
    this.obsEyeState = document.getElementById("obs-eye-state-val");
    this.obsStudyActivity = document.getElementById("obs-study-activity-val");
    this.obsInactivity = document.getElementById("obs-inactivity-val");
    this.obsHandNearFace = document.getElementById("obs-hand-near-face-val");
    this.obsCameraHealth = document.getElementById("obs-camera-health-val");
    this.obsPhoneStatus = document.getElementById("obs-phone-status-val");
    this.obsBehaviorCategory = document.getElementById("obs-behavior-category-val");

    // Alert Card
    this.alertCard = document.getElementById("alert-card");
    this.alertIcon = document.getElementById("alert-icon");
    this.alertName = document.getElementById("alert-name");
    this.alertReason = document.getElementById("alert-reason");
    this.alertPriorityBadge = document.getElementById("alert-priority-badge");

    // Decision Rationale (WHY DID THE AI MAKE THIS DECISION?)
    this.rationaleObs = document.getElementById("rationale-obs");
    this.rationaleEvidenceList = document.getElementById("rationale-evidence-list");
    this.rationaleDecision = document.getElementById("rationale-decision");
    this.rationaleAudio = document.getElementById("rationale-audio");

    // History Timeline
    this.historyTimeline = document.getElementById("history-timeline");
    this.historyEmpty = document.getElementById("history-empty");

    // Modals
    this.modalEl = document.getElementById("permission-modal");
    this.modalCloseBtn = document.getElementById("modal-close-btn");
    this.modalDismissBtn = document.getElementById("modal-dismiss-btn");
    this.modalRetryBtn = document.getElementById("modal-retry-btn");

    this.calibrateBtn = document.getElementById("calibrate-btn");
    this.calibModal = document.getElementById("calibration-modal");
    this.calibCloseBtn = document.getElementById("calib-close-btn");
    this.calibCancelBtn = document.getElementById("calib-cancel-btn");
    this.calibStartBtn = document.getElementById("calib-start-btn");
    this.calibProgressBar = document.getElementById("calib-progress-bar");
    this.calibStatusText = document.getElementById("calib-status-text");

    // Subsystems
    this.camera = new CameraManager(this.videoEl, this.captureCanvas);
    this.wsClient = new MonitorWebSocketClient();
    this.audioCtrl = new BrowserAudioController();

    // App state
    this.isMonitoring = false;
    this.frameIntervalTimer = null;
    this.sessionTimer = null;
    this.sessionStartSec = 0;
    this.lastState = null;

    this.initEventListeners();
    this.initWebSocketCallbacks();
  }

  initEventListeners() {
    this.startBtn.addEventListener("click", () => this.handleStartMonitoring());
    this.stopBtn.addEventListener("click", () => this.handleStopMonitoring());
    this.cameraPermBtn.addEventListener("click", () => this.handleRequestCameraOnly());
    this.resetBtn.addEventListener("click", () => this.handleResetSession());
    this.audioToggleBtn.addEventListener("click", () => this.handleAudioToggle());
    this.clearHistoryBtn.addEventListener("click", () => this.clearHistory());

    // Calibration modal events
    if (this.calibrateBtn) {
      this.calibrateBtn.addEventListener("click", () => this.showCalibrationModal());
    }
    if (this.calibCloseBtn) {
      this.calibCloseBtn.addEventListener("click", () => this.hideCalibrationModal());
    }
    if (this.calibCancelBtn) {
      this.calibCancelBtn.addEventListener("click", () => this.hideCalibrationModal());
    }
    if (this.calibStartBtn) {
      this.calibStartBtn.addEventListener("click", () => this.runCalibrationRoutine());
    }

    // Modal events
    this.modalCloseBtn.addEventListener("click", () => this.hideModal());
    this.modalDismissBtn.addEventListener("click", () => this.hideModal());
    this.modalRetryBtn.addEventListener("click", () => {
      this.hideModal();
      this.handleStartMonitoring();
    });
  }

  initWebSocketCallbacks() {
    this.wsClient.onStatusChange = ({ connected, statusText }) => {
      if (connected) {
        this.connectionBadge.className = "connection-status-badge status-connected";
        this.connectionText.textContent = "Connected";
      } else {
        this.connectionBadge.className = "connection-status-badge status-disconnected";
        this.connectionText.textContent = statusText || "Disconnected";
      }
    };

    this.wsClient.onEvent = (eventData) => {
      this.handleStateUpdate(eventData);
    };

    this.wsClient.onError = () => {
      this.showCameraError("WebSocket connection to AI backend failed.");
    };
  }

  async handleStartMonitoring() {
    this.audioCtrl.unlockAudio();
    this.hideCameraError();

    this.cameraStatusText.textContent = "Camera: Initializing...";
    const camResult = await this.camera.startCamera();

    if (!camResult.success) {
      this.showCameraError(camResult.error);
      this.showModal();
      this.cameraStatusText.textContent = "Camera: Error";
      return;
    }

    this.placeholderEl.style.display = "none";
    this.cameraStatusText.textContent = `Camera: Active (${this.videoEl.videoWidth}x${this.videoEl.videoHeight})`;

    // Connect WebSocket
    this.wsClient.connect();

    this.isMonitoring = true;
    this.startBtn.disabled = true;
    this.stopBtn.disabled = false;
    this.resetBtn.disabled = false;

    // Start Session duration timer
    this.sessionStartSec = Date.now();
    this.sessionTimer = setInterval(() => this.updateSessionTimer(), 1000);

    // Frame transmission loop (~7-8 FPS = 130ms)
    this.frameIntervalTimer = setInterval(async () => {
      if (!this.isMonitoring) return;
      const blob = await this.camera.captureFrameBlob(0.7);
      if (blob) {
        this.wsClient.sendFrame(blob);
      }
    }, 130);
  }

  handleStopMonitoring() {
    this.isMonitoring = false;
    if (this.frameIntervalTimer) {
      clearInterval(this.frameIntervalTimer);
      this.frameIntervalTimer = null;
    }

    if (this.sessionTimer) {
      clearInterval(this.sessionTimer);
      this.sessionTimer = null;
    }

    this.wsClient.disconnect();
    this.camera.stopCamera();
    this.audioCtrl.stopAll();

    this.startBtn.disabled = false;
    this.stopBtn.disabled = true;
    this.placeholderEl.style.display = "flex";
    this.cameraStatusText.textContent = "Camera: Standby";
    this.fpsValueEl.textContent = "0.0 FPS";

    // Set UI to paused/stopped
    this.stateNameEl.textContent = "MONITORING STOPPED";
    this.stateCard.style.borderLeftColor = "var(--color-neutral)";
    this.recCard.className = "card recommendation-card severity-info";
    this.recTitle.textContent = "Monitoring Stopped";
    this.recMessage.textContent = "Monitoring session has been paused. Click 'Start Monitoring' to resume.";
    this.recReason.textContent = "User stopped monitoring.";
    this.recSeverity.textContent = "STOPPED";
  }

  async handleRequestCameraOnly() {
    this.hideCameraError();
    this.cameraStatusText.textContent = "Camera: Requesting permission...";
    const res = await this.camera.startCamera();
    if (!res.success) {
      this.showCameraError(res.error);
      this.showModal();
      this.cameraStatusText.textContent = "Camera: Permission Denied";
    } else {
      this.placeholderEl.style.display = "none";
      this.cameraStatusText.textContent = `Camera: Preview Ready (${this.videoEl.videoWidth}x${this.videoEl.videoHeight})`;
    }
  }

  handleResetSession() {
    this.wsClient.sendCommand({ action: "reset" });
    this.sessionStartSec = Date.now();
    this.updateSessionTimer();
    this.audioCtrl.stopAll();
    this.logHistoryEvent("SESSION_RESET", "Session timers and metrics reset by user.", [59, 130, 246]);
  }

  handleAudioToggle() {
    const enabled = this.audioCtrl.toggleMute();
    if (enabled) {
      this.audioIcon.textContent = "🔊";
      this.audioText.textContent = "Audio Alerts: ON";
      this.audioToggleBtn.classList.remove("audio-muted");
    } else {
      this.audioIcon.textContent = "🔇";
      this.audioText.textContent = "Audio Alerts: OFF";
      this.audioToggleBtn.classList.add("audio-muted");
    }
  }

  handleStateUpdate(eventData) {
    if (!eventData || !eventData.state) return;

    // 1. Authoritative State & Confidence
    const stateName = eventData.state_display || eventData.state;
    this.stateNameEl.textContent = stateName;
    this.stateDurationBadge.textContent = `${eventData.duration_seconds || 0.0}s`;

    const confPct = Math.round((eventData.confidence || 1.0) * 100);
    this.confidenceBar.style.width = `${confPct}%`;
    this.confidenceValue.textContent = `${confPct}%`;

    // Apply color styling from backend state_color [R, G, B]
    if (eventData.state_color && eventData.state_color.length === 3) {
      const [r, g, b] = eventData.state_color;
      const rgbStr = `rgb(${r}, ${g}, ${b})`;
      this.stateCard.style.borderLeftColor = rgbStr;
      this.confidenceBar.style.backgroundColor = rgbStr;
    }

    // 2. Recommendations Panel
    if (eventData.recommendation) {
      const rec = eventData.recommendation;
      this.recTitle.textContent = rec.title;
      this.recMessage.textContent = rec.message;
      this.recReason.textContent = rec.reason;
      this.recSeverity.textContent = (rec.severity || "info").toUpperCase();
      this.recCard.className = `card recommendation-card severity-${rec.severity || "info"}`;
    }

    // 3. Independent Behavioral Signals
    if (eventData.observations) {
      const obs = eventData.observations;

      this.updateBadge(this.obsFacePresent, obs.face_present ? "YES" : "NO", obs.face_present ? "success" : "danger");
      this.updateBadge(this.obsFaceOccluded, obs.face_occluded ? "OCCLUDED" : "NO", obs.face_occluded ? "danger" : "success");
      this.updateBadge(this.obsPersonPresent, obs.person_present ? "YES" : "NO", obs.person_present ? "success" : "danger");
      this.updateBadge(this.obsHeadDirection, obs.head_direction || "—", "neutral");

      const earText = obs.eye_state === "CLOSED" ? `CLOSED (${(obs.ear || 0).toFixed(2)})` : `OPEN (${(obs.ear || 0).toFixed(2)})`;
      this.updateBadge(this.obsEyeState, earText, obs.eye_state === "CLOSED" ? "warning" : "success");

      this.updateBadge(this.obsStudyActivity, obs.observable_study_activity || "UNCONFIRMED", obs.observable_study_activity === "UNCONFIRMED" ? "warning" : "info");
      this.updateBadge(this.obsInactivity, `${(obs.inactivity_duration || 0).toFixed(1)}s`, (obs.inactivity_duration || 0) > 8 ? "warning" : "neutral");
      this.updateBadge(this.obsHandNearFace, obs.hand_near_face ? "YES" : "NO", obs.hand_near_face ? "warning" : "neutral");
      this.updateBadge(this.obsCameraHealth, obs.camera_health || "OK", obs.camera_health === "OK" ? "success" : "danger");

      const phStatus = obs.phone_status || (obs.phone_present ? "VISIBLE" : "NONE");
      const phCat = phStatus.includes("CONFIRM") || phStatus.includes("USE") ? "danger" : (obs.phone_present ? "warning" : "neutral");
      this.updateBadge(this.obsPhoneStatus, phStatus, phCat);

      const behCat = obs.behavior_category || "STUDYING";
      const catColor = behCat.includes("STUDY") ? "success" : (behCat.includes("UNCONFIRM") ? "warning" : "danger");
      this.updateBadge(this.obsBehaviorCategory, behCat, catColor);
    }

    // 3.5 WHY DID THE AI MAKE THIS DECISION? (Part 8)
    if (eventData.decision_rationale) {
      const rat = eventData.decision_rationale;
      if (this.rationaleObs) this.rationaleObs.textContent = rat.primary_observation;
      if (this.rationaleDecision) this.rationaleDecision.textContent = rat.decision;
      if (this.rationaleAudio) this.rationaleAudio.textContent = rat.audio_action;
      if (this.rationaleEvidenceList && rat.additional_evidence) {
        this.rationaleEvidenceList.innerHTML = rat.additional_evidence
          .map((item) => `<li>${item}</li>`)
          .join("");
      }
    }

    // 4. Alert & Audio Controller
    if (eventData.alert) {
      const alert = eventData.alert;
      this.audioCtrl.handleAlertEvent(alert);

      if (alert.active) {
        this.alertIcon.textContent = "🔔";
        this.alertName.textContent = alert.name || "ACTIVE ALERT";
        this.alertReason.textContent = alert.reason || "Alert threshold met.";
        this.alertPriorityBadge.textContent = `P${alert.priority || 5} ALERT`;
        this.alertPriorityBadge.className = "badge badge-danger";
      } else {
        this.alertIcon.textContent = "🔇";
        this.alertName.textContent = "No Active Alert";
        this.alertReason.textContent = alert.reason || "Monitoring conditions normal.";
        this.alertPriorityBadge.textContent = "STANDBY";
        this.alertPriorityBadge.className = "badge badge-neutral";
      }
    }

    // 5. Transition History Logging
    if (this.lastState !== eventData.state) {
      this.logHistoryEvent(eventData.state_display || eventData.state, eventData.diagnostic_reason || "State transition", eventData.state_color);
      this.lastState = eventData.state;
    }
  }

  updateBadge(element, text, category) {
    if (!element) return;
    element.textContent = text;
    element.className = `obs-badge badge-${category}`;
  }

  logHistoryEvent(stateName, reason, rgbColor = [100, 100, 100]) {
    if (this.historyEmpty) {
      this.historyEmpty.style.display = "none";
    }

    const timeStr = new Date().toLocaleTimeString();
    const item = document.createElement("div");
    item.className = "history-item";
    const borderCol = rgbColor && rgbColor.length === 3 ? `rgb(${rgbColor[0]}, ${rgbColor[1]}, ${rgbColor[2]})` : "var(--border-color)";
    item.style.borderLeftColor = borderCol;

    item.innerHTML = `
      <div class="history-left">
        <span class="history-time">${timeStr}</span>
        <span class="history-state" style="color: ${borderCol};">${stateName}</span>
      </div>
      <div class="history-reason">${reason}</div>
    `;

    this.historyTimeline.insertBefore(item, this.historyTimeline.firstChild);

    // Limit history to 50 items
    while (this.historyTimeline.children.length > 51) {
      this.historyTimeline.removeChild(this.historyTimeline.lastChild);
    }
  }

  clearHistory() {
    this.historyTimeline.innerHTML = '<div class="history-empty" id="history-empty">No events logged yet.</div>';
    this.historyEmpty = document.getElementById("history-empty");
  }

  updateSessionTimer() {
    if (!this.sessionStartSec) return;
    const elapsedSec = Math.floor((Date.now() - this.sessionStartSec) / 1000);
    const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, "0");
    const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, "0");
    const secs = String(elapsedSec % 60).padStart(2, "0");
    this.sessionDurationEl.textContent = `${hrs}:${mins}:${secs}`;
  }

  showCameraError(message) {
    this.errorBannerEl.style.display = "flex";
    this.errorMessageEl.textContent = message;
  }

  hideCameraError() {
    this.errorBannerEl.style.display = "none";
  }

  showModal() {
    this.modalEl.style.display = "flex";
  }

  hideModal() {
    this.modalEl.style.display = "none";
  }

  showCalibrationModal() {
    if (this.calibModal) this.calibModal.style.display = "flex";
  }

  hideCalibrationModal() {
    if (this.calibModal) this.calibModal.style.display = "none";
  }

  async runCalibrationRoutine() {
    if (this.calibStartBtn) this.calibStartBtn.disabled = true;
    if (this.calibStatusText) this.calibStatusText.textContent = "Connecting camera for calibration...";

    if (!this.camera.isActive) {
      await this.camera.startCamera();
      this.placeholderEl.style.display = "none";
    }

    if (!this.wsClient.isConnected) {
      this.wsClient.connect();
    }

    let progress = 0;
    const interval = setInterval(async () => {
      progress += 10;
      if (this.calibProgressBar) this.calibProgressBar.style.width = `${progress}%`;

      const blob = await this.camera.captureFrameBlob(0.7);
      if (blob) {
        this.wsClient.sendFrame(blob);
      }

      if (progress >= 100) {
        clearInterval(interval);
        if (this.calibStatusText) this.calibStatusText.textContent = "Calibration complete! Baseline saved.";
        this.wsClient.sendCommand({
          action: "calibrate",
          calibration_data: { calibrated: true, timestamp: Date.now() },
        });
        setTimeout(() => {
          this.hideCalibrationModal();
          if (this.calibStartBtn) this.calibStartBtn.disabled = false;
          if (this.calibProgressBar) this.calibProgressBar.style.width = "0%";
          this.logHistoryEvent("CALIBRATED", "Personal workspace posture calibrated.", [16, 185, 129]);
        }, 1000);
      }
    }, 250);
  }
}

// Instantiate and initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  if (!window.studyMonitorApp) {
    window.studyMonitorApp = new StudyMonitorApp();
  }
});

export { StudyMonitorApp };

