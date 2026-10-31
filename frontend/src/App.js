/**
 * frontend/src/App.js — Real-Time AI Study Focus Monitoring Dashboard Controller
 * Powers:
 *   - Live WebRTC camera ingestion & HUD canvas overlay (face box, mesh landmarks, FPS)
 *   - WebSocket bi-directional streaming with flow-control ACKs
 *   - Stock-market-style continuous real-time focus graph with dynamic glowing trail
 *   - 4 Mini live sparkline canvases (Focus, Attention, Distraction, Drowsiness)
 *   - AI Analysis real-time checklist and radial confidence meter
 *   - In-memory live events timeline feed (strictly zero persistent storage)
 *   - Complete monitoring controls (Start, Pause, Stop, Audio Toggle, Settings)
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

    // Top Status Indicators
    this.topCameraStatus = document.getElementById("top-camera-status");
    this.topCameraDot = document.getElementById("top-camera-dot");
    this.topModelsStatus = document.getElementById("top-models-status");
    this.topWsStatus = document.getElementById("top-ws-status");
    this.topWsDot = document.getElementById("top-ws-dot");
    this.topFpsVal = document.getElementById("top-fps-val");
    this.topSessionTime = document.getElementById("top-session-time");
    this.topWaveCanvas = document.getElementById("top-audio-wave");

    // Video HUD Overlays
    this.videoFpsTag = document.getElementById("video-fps-tag");
    this.videoResTag = document.getElementById("video-res-tag");

    // Compact Signal Indicators
    this.obsFaceVal = document.getElementById("obs-face-val");
    this.obsFacePill = document.getElementById("obs-face-pill");
    this.obsEyesVal = document.getElementById("obs-eyes-val");
    this.obsEyesPill = document.getElementById("obs-eyes-pill");
    this.obsPoseVal = document.getElementById("obs-pose-val");
    this.obsPosePill = document.getElementById("obs-pose-pill");
    this.obsPhoneVal = document.getElementById("obs-phone-val");
    this.obsPhonePill = document.getElementById("obs-phone-pill");
    this.obsActivityVal = document.getElementById("obs-activity-val");
    this.obsActivityPill = document.getElementById("obs-activity-pill");

    // Current Behaviour Card
    this.behaviourIcon = document.getElementById("behaviour-icon");
    this.behaviourTitle = document.getElementById("behaviour-title");
    this.behaviourSubtitle = document.getElementById("behaviour-subtitle");
    this.radialConfidenceText = document.getElementById("radial-confidence-text");
    this.radialConfidenceFill = document.getElementById("radial-confidence-fill");
    this.behaviourStabilityPill = document.getElementById("behaviour-stability-pill");
    this.stabilityText = document.getElementById("stability-text");

    // AI Analysis Checklist
    this.checkFace = document.getElementById("check-face");
    this.checkEyes = document.getElementById("check-eyes");
    this.checkHead = document.getElementById("check-head");
    this.checkHands = document.getElementById("check-hands");
    this.checkPhone = document.getElementById("check-phone");

    // Metric Cards
    this.metricFocusVal = document.getElementById("metric-focus-val");
    this.metricAttentionVal = document.getElementById("metric-attention-val");
    this.metricDistractionVal = document.getElementById("metric-distraction-val");
    this.metricDrowsinessVal = document.getElementById("metric-drowsiness-val");

    // Sparklines Canvases
    this.sparkFocusCanvas = document.getElementById("sparkline-focus");
    this.sparkAttentionCanvas = document.getElementById("sparkline-attention");
    this.sparkDistractionCanvas = document.getElementById("sparkline-distraction");
    this.sparkDrowsinessCanvas = document.getElementById("sparkline-drowsiness");

    // Stock Market Chart Elements
    this.stockChartCanvas = document.getElementById("realtime-stock-graph");
    this.graphMetricSelect = document.getElementById("graph-metric-select");

    // Live Events Feed
    this.liveEventsFeed = document.getElementById("live-events-feed");

    // Controls
    this.startBtn = document.getElementById("start-btn");
    this.stopBtn = document.getElementById("stop-btn");
    this.pauseBtn = document.getElementById("pause-btn");
    this.pauseIcon = document.getElementById("pause-icon");
    this.pauseText = document.getElementById("pause-text");
    this.audioToggleBtn = document.getElementById("audio-toggle-btn");
    this.audioBadge = document.getElementById("audio-badge");
    this.settingsBtn = document.getElementById("settings-btn");

    // Settings Modal
    this.settingsModal = document.getElementById("settings-modal");
    this.settingsCloseBtn = document.getElementById("settings-close-btn");
    this.cameraSelect = document.getElementById("camera-select");
    this.audioVolSlider = document.getElementById("audio-volume-slider");
    this.resetSessionModalBtn = document.getElementById("reset-session-modal-btn");

    // Subsystems
    this.camera = new CameraManager(this.videoEl, this.captureCanvas);
    this.wsClient = new MonitorWebSocketClient();
    this.audioCtrl = new BrowserAudioController();

    // 2. Ephemeral In-Memory State (Strictly zero persistent database or local storage)
    this.isMonitoring = false;
    this.isPaused = false;
    this.sessionStartSec = 0;
    this.sessionTimer = null;
    this.frameIntervalTimer = null;
    this.lastState = null;
    this.lastStateTimestamp = 0;
    this.fpsCounter = 0;
    this.lastFpsTimestamp = performance.now();
    this.currentFps = 0.0;
    this.lastObs = null;

    // Rolling In-Memory Buffers for Sparklines (max 30 points)
    this.sparklineData = {
      focus: [],
      attention: [],
      distraction: [],
      drowsiness: [],
    };

    // Rolling In-Memory Buffer for Stock Market Graph (max 100 points ~ 60-120 seconds)
    this.stockGraphBuffer = [];
    this.activeMetric = "focus"; // "focus", "attention", "distraction", "drowsiness"

    // Rolling In-Memory List of Live Events (max 20)
    this.eventsList = [];

    // Animation Loops
    this.waveAnimFrame = null;
    this.chartAnimFrame = null;

    // Initialize
    this.initEventListeners();
    this.initWebSocketCallbacks();
    this.startWaveformAnimation();
    this.startStockChartRenderLoop();
  }

  // =========================================================================
  // EVENT LISTENERS & CONTROLS
  // =========================================================================
  initEventListeners() {
    this.startBtn?.addEventListener("click", () => this.handleStartMonitoring());
    this.stopBtn?.addEventListener("click", () => this.handleStopMonitoring());
    this.pauseBtn?.addEventListener("click", () => this.handleTogglePause());
    this.audioToggleBtn?.addEventListener("click", () => this.handleToggleAudio());

    this.settingsBtn?.addEventListener("click", () => {
      this.populateCameraOptions();
      if (this.settingsModal) this.settingsModal.style.display = "flex";
    });
    this.settingsCloseBtn?.addEventListener("click", () => {
      if (this.settingsModal) this.settingsModal.style.display = "none";
    });

    this.audioVolSlider?.addEventListener("input", (e) => {
      this.audioCtrl.setVolume(parseFloat(e.target.value) / 100);
    });

    this.graphMetricSelect?.addEventListener("change", (e) => {
      this.activeMetric = e.target.value;
    });

    this.resetSessionModalBtn?.addEventListener("click", () => {
      this.wsClient.sendReset();
      this.clearSessionData();
      if (this.settingsModal) this.settingsModal.style.display = "none";
    });
  }

  initWebSocketCallbacks() {
    this.wsClient.onStatusChange = (status) => {
      if (this.topWsStatus) {
        this.topWsStatus.textContent = status.connected ? "Connected" : "Disconnected";
      }
      if (this.topWsDot) {
        this.topWsDot.className = status.connected ? "dot-indicator active" : "dot-indicator error";
      }
    };

    this.wsClient.onEvent = (data) => {
      this.handleServerEvent(data);
    };

    this.wsClient.onError = (err) => {
      console.warn("[Dashboard] WebSocket error:", err);
    };
  }

  // =========================================================================
  // MONITORING LIFECYCLE (START, PAUSE, STOP)
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

    // Update Video Resolution Tag
    if (this.videoResTag && this.videoEl) {
      const w = this.videoEl.videoWidth || 640;
      const h = this.videoEl.videoHeight || 480;
      this.videoResTag.textContent = `${w}x${h}`;
    }

    // 2. Connect WebSocket
    this.wsClient.connect();

    // 3. Update State
    this.isMonitoring = true;
    this.isPaused = false;
    this.sessionStartSec = Date.now();
    if (this.topModelsStatus) this.topModelsStatus.textContent = "Running";

    // 4. Session Elapsed Timer
    this.startSessionTimer();

    // 5. Frame Transmission Loop (~10 FPS with backpressure ACK)
    this.startFrameCaptureLoop();

    // Add Initial Live Event
    this.addLiveEvent("Monitoring Session Started", "info", "0s");
  }

  handleTogglePause() {
    if (!this.isMonitoring) return;

    this.isPaused = !this.isPaused;
    if (this.isPaused) {
      if (this.pauseText) this.pauseText.textContent = "Resume";
      if (this.pauseIcon) this.pauseIcon.textContent = "▶";
      this.setCameraStatus("Paused", "warning");
      this.addLiveEvent("Monitoring Paused", "warning", "");
    } else {
      if (this.pauseText) this.pauseText.textContent = "Pause";
      if (this.pauseIcon) this.pauseIcon.textContent = "⏸";
      this.setCameraStatus("Active", "active");
      this.addLiveEvent("Monitoring Resumed", "info", "");
    }
  }

  handleStopMonitoring() {
    if (!this.isMonitoring) return;

    this.isMonitoring = false;
    this.isPaused = false;

    // 1. Stop Camera & Timers
    this.camera.stopCamera();
    if (this.frameIntervalTimer) clearInterval(this.frameIntervalTimer);
    if (this.sessionTimer) clearInterval(this.sessionTimer);

    // 2. Disconnect WebSocket
    this.wsClient.disconnect();

    // 3. Clear Video Canvas & Placeholder
    if (this.placeholderEl) this.placeholderEl.style.display = "flex";
    this.clearHudCanvas();

    // 4. Reset Ephemeral In-Memory Buffers
    this.clearSessionData();

    // 5. Reset Status Indicators
    this.setCameraStatus("Standby", "neutral");
    if (this.topModelsStatus) this.topModelsStatus.textContent = "Standby";
    if (this.topFpsVal) this.topFpsVal.textContent = "0.0";
    if (this.videoFpsTag) this.videoFpsTag.textContent = "FPS: 0.0";
    if (this.pauseText) this.pauseText.textContent = "Pause";
    if (this.pauseIcon) this.pauseIcon.textContent = "⏸";

    // Stop active audio alerts
    this.audioCtrl.stop();

    this.addLiveEvent("Session Stopped & Cleared", "neutral", "");
  }

  handleToggleAudio() {
    const isEnabled = this.audioCtrl.toggleMute();
    if (this.audioBadge) {
      this.audioBadge.textContent = isEnabled ? "ON" : "OFF";
      this.audioBadge.className = isEnabled ? "badge-pill-on" : "badge-pill-off";
    }
  }

  // =========================================================================
  // FRAME CAPTURE & WEBSOCKET STREAMING LOOP
  // =========================================================================
  startFrameCaptureLoop() {
    if (this.frameIntervalTimer) clearInterval(this.frameIntervalTimer);

    // Target ~10 FPS capture interval (100ms) with flow control
    this.frameIntervalTimer = setInterval(async () => {
      if (!this.isMonitoring || this.isPaused) return;

      // Respect server backpressure (await ACK from previous frame)
      if (this.wsClient.isAwaitingAck) return;

      const blob = await this.camera.captureFrameBlob(0.68);
      if (blob && this.wsClient.isConnected) {
        this.wsClient.sendFrame(blob);
      }
    }, 100);
  }

  // =========================================================================
  // SERVER EVENT HANDLER & DASHBOARD RENDERER
  // =========================================================================
  handleServerEvent(data) {
    if (!data || !this.isMonitoring) return;

    // Calculate Live FPS
    this.fpsCounter++;
    const now = performance.now();
    if (now - this.lastFpsTimestamp >= 1000) {
      this.currentFps = (this.fpsCounter / ((now - this.lastFpsTimestamp) / 1000)).toFixed(1);
      this.fpsCounter = 0;
      this.lastFpsTimestamp = now;

      if (this.topFpsVal) this.topFpsVal.textContent = this.currentFps;
      if (this.videoFpsTag) this.videoFpsTag.textContent = `FPS: ${this.currentFps}`;
    }

    const obs = data.observations || {};
    this.lastObs = obs;

    // 1. Update Current Behaviour Card
    this.updateBehaviourCard(data);

    // 2. Update Compact 5-Signals Row
    this.updateCompactSignals(obs);

    // 3. Update AI Analysis Checklist
    this.updateAiAnalysisChecklist(obs);

    // 4. Update Metric Cards & Rolling Sparklines
    this.updateMetricsAndSparklines(obs, data);

    // 5. Update Stock Market Graph Buffer
    this.updateStockGraphBuffer(obs, data);

    // 6. Draw Live HUD Overlay (bounding box, landmarks, corners)
    this.drawHudOverlay(obs);

    // 7. Track State Transition Events
    this.trackSessionEvents(data);

    // 8. Audio Alerts Evaluation
    if (data.alert) {
      this.audioCtrl.evaluateAlert(data.alert);
    }
  }

  // =========================================================================
  // COMPONENT UPKEEP: BEHAVIOUR, RADIAL GAUGE & SIGNALS
  // =========================================================================
  updateBehaviourCard(data) {
    const state = data.state || "MONITORING";
    const conf = Math.round((data.confidence || 0.9) * 100);

    let titleText = "STUDYING";
    let subText = "Screen Concentration";
    let icon = "📖";

    if (state.includes("READING")) {
      titleText = "STUDYING";
      subText = "Reading Study Materials";
      icon = "📖";
    } else if (state.includes("WRITING")) {
      titleText = "STUDYING";
      subText = "Writing / Desk Study";
      icon = "✍️";
    } else if (state === "LOOKING_AWAY") {
      titleText = "LOOKING AWAY";
      subText = "Attention turned away from desk";
      icon = "👁️";
    } else if (state === "POSSIBLE_DROWSINESS") {
      titleText = "DROWSINESS";
      subText = "Prolonged eye closure / Head droop";
      icon = "⚡";
    } else if (state === "DISTRACTED") {
      titleText = "DISTRACTED";
      subText = "Mobile phone interaction detected";
      icon = "📱";
    } else if (state === "STUDENT_ABSENT") {
      titleText = "ABSENT";
      subText = "No student visible in camera view";
      icon = "👤";
    } else if (state === "FACE_OCCLUDED") {
      titleText = "FACE OCCLUDED";
      subText = "Face obscured or covered";
      icon = "🙈";
    } else if (state === "RECOVERING") {
      titleText = "RECOVERING";
      subText = "Resuming focused study rhythm";
      icon = "🔄";
    }

    if (this.behaviourTitle) this.behaviourTitle.textContent = titleText;
    if (this.behaviourSubtitle) this.behaviourSubtitle.textContent = subText;
    if (this.behaviourIcon) this.behaviourIcon.textContent = icon;

    // Update Radial Confidence Meter
    if (this.radialConfidenceText) this.radialConfidenceText.textContent = `${conf}%`;
    if (this.radialConfidenceFill) {
      // Circumference of r=32 is 2 * PI * 32 ~= 201
      const offset = 201 - (201 * conf) / 100;
      this.radialConfidenceFill.style.strokeDashoffset = offset;
      if (conf < 50) {
        this.radialConfidenceFill.style.stroke = "#ef4444";
      } else if (conf < 75) {
        this.radialConfidenceFill.style.stroke = "#f59e0b";
      } else {
        this.radialConfidenceFill.style.stroke = "#10b981";
      }
    }

    // Stability Pill
    const isStable = (data.duration_seconds || 0) > 1.5;
    if (this.stabilityText) this.stabilityText.textContent = isStable ? "Stable State" : "Transitioning";
  }

  updateCompactSignals(obs) {
    // Face
    if (this.obsFaceVal) {
      if (obs.face_occluded) {
        this.obsFaceVal.textContent = "Occluded";
        this.setSignalPillClass(this.obsFacePill, "danger");
      } else if (obs.face_present) {
        this.obsFaceVal.textContent = "Detected";
        this.setSignalPillClass(this.obsFacePill, "positive");
      } else {
        this.obsFaceVal.textContent = "Unknown";
        this.setSignalPillClass(this.obsFacePill, "neutral");
      }
    }

    // Eyes
    if (this.obsEyesVal) {
      const earVal = obs.ear !== undefined ? ` (${obs.ear.toFixed(2)})` : "";
      if (obs.eye_state === "EYES_CLOSED" || obs.eye_state === "CLOSED") {
        this.obsEyesVal.textContent = `Closed${earVal}`;
        this.setSignalPillClass(this.obsEyesPill, "danger");
      } else {
        this.obsEyesVal.textContent = `Open${earVal}`;
        this.setSignalPillClass(this.obsEyesPill, "positive");
      }
    }

    // Pose
    if (this.obsPoseVal) {
      const postName = obs.posture_name || "UPRIGHT";
      this.obsPoseVal.textContent = postName === "UPRIGHT" ? "Normal" : postName.replace("_", " ").toLowerCase();
      this.setSignalPillClass(this.obsPosePill, postName === "UPRIGHT" ? "positive" : "warning");
    }

    // Phone
    if (this.obsPhoneVal) {
      const isPhone = obs.phone_present || (obs.phone_status && obs.phone_status !== "NONE");
      this.obsPhoneVal.textContent = isPhone ? "Detected" : "Not Detected";
      this.setSignalPillClass(this.obsPhonePill, isPhone ? "danger" : "positive");
    }

    // Activity
    if (this.obsActivityVal) {
      let act = obs.observable_study_activity || "SCREEN";
      if (act === "SCREEN" || act === "NONE") act = "Screen Study";
      this.obsActivityVal.textContent = act.replace("_", " ");
      this.setSignalPillClass(this.obsActivityPill, "active");
    }
  }

  setSignalPillClass(pill, variant) {
    if (!pill) return;
    pill.className = `compact-signal-pill ${variant}`;
  }

  updateAiAnalysisChecklist(obs) {
    this.setCheckItem(this.checkFace, obs.face_present && !obs.face_occluded);
    this.setCheckItem(this.checkEyes, obs.eye_state !== "EYES_CLOSED" && obs.eye_state !== "CLOSED");
    this.setCheckItem(this.checkHead, Math.abs(obs.head_yaw_deg || 0) < 26);
    this.setCheckItem(this.checkHands, obs.book_present || obs.observable_study_activity !== "NONE");
    this.setCheckItem(this.checkPhone, !obs.phone_present && obs.phone_status === "NONE");
  }

  setCheckItem(item, isPassing) {
    if (!item) return;
    item.className = isPassing ? "ai-check-item" : "ai-check-item failing";
    const icon = item.querySelector("span.chk-icon");
    if (icon) icon.textContent = isPassing ? "✔" : "✕";
  }

  // =========================================================================
  // METRICS & SPARKLINE RENDERING
  // =========================================================================
  updateMetricsAndSparklines(obs, data) {
    const focusPct = Math.round((obs.focus_level ?? 0.85) * 100);
    const attentionPct = Math.round((obs.attention_level ?? 0.80) * 100);
    const distractPct = Math.round((obs.distraction_level ?? 0.08) * 100);
    const drowsyPct = Math.round((obs.drowsiness_level ?? 0.05) * 100);

    if (this.metricFocusVal) this.metricFocusVal.textContent = `${focusPct}%`;
    if (this.metricAttentionVal) this.metricAttentionVal.textContent = `${attentionPct}%`;
    if (this.metricDistractionVal) this.metricDistractionVal.textContent = `${distractPct}%`;
    if (this.metricDrowsinessVal) this.metricDrowsinessVal.textContent = `${drowsyPct}%`;

    // Append to rolling sparkline buffers (max 30 items)
    this.pushBuffer(this.sparklineData.focus, focusPct, 30);
    this.pushBuffer(this.sparklineData.attention, attentionPct, 30);
    this.pushBuffer(this.sparklineData.distraction, distractPct, 30);
    this.pushBuffer(this.sparklineData.drowsiness, drowsyPct, 30);

    // Draw sparklines
    this.drawSparkline(this.sparkFocusCanvas, this.sparklineData.focus, "#10b981", "#059669");
    this.drawSparkline(this.sparkAttentionCanvas, this.sparklineData.attention, "#38bdf8", "#0284c7");
    this.drawSparkline(this.sparkDistractionCanvas, this.sparklineData.distraction, "#ef4444", "#b91c1c");
    this.drawSparkline(this.sparkDrowsinessCanvas, this.sparklineData.drowsiness, "#f59e0b", "#d97706");
  }

  pushBuffer(arr, item, maxLen) {
    arr.push(item);
    if (arr.length > maxLen) arr.shift();
  }

  drawSparkline(canvas, data, strokeColor, fillColor) {
    if (!canvas || data.length < 2) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const step = w / (data.length - 1);
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const val = data[i];
      const y = h - (val / 100) * (h - 6) - 3;
      const x = i * step;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw leading glow point
    const lastX = (data.length - 1) * step;
    const lastY = h - (data[data.length - 1] / 100) * (h - 6) - 3;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 3, 0, 2 * Math.PI);
    ctx.fillStyle = strokeColor;
    ctx.shadowColor = strokeColor;
    ctx.shadowBlur = 6;
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  // =========================================================================
  // STOCK-MARKET-STYLE REAL-TIME GRAPH
  // =========================================================================
  updateStockGraphBuffer(obs, data) {
    let currentVal = 85;
    if (this.activeMetric === "focus") currentVal = Math.round((obs.focus_level ?? 0.85) * 100);
    else if (this.activeMetric === "attention") currentVal = Math.round((obs.attention_level ?? 0.8) * 100);
    else if (this.activeMetric === "distraction") currentVal = Math.round((obs.distraction_level ?? 0.08) * 100);
    else if (this.activeMetric === "drowsiness") currentVal = Math.round((obs.drowsiness_level ?? 0.05) * 100);

    const d = new Date();
    const timeStr = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;

    this.pushBuffer(this.stockGraphBuffer, { val: currentVal, time: timeStr }, 60);
  }

  startStockChartRenderLoop() {
    const render = () => {
      this.drawStockMarketGraph();
      this.chartAnimFrame = requestAnimationFrame(render);
    };
    this.chartAnimFrame = requestAnimationFrame(render);
  }

  drawStockMarketGraph() {
    const canvas = this.stockChartCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const padLeft = 45;
    const padBottom = 26;
    const padTop = 14;
    const padRight = 16;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    // 1. Draw Grid Lines (0%, 25%, 50%, 75%, 100%)
    ctx.font = "10px -apple-system, sans-serif";
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    const gridSteps = [0, 25, 50, 75, 100];
    for (const stepVal of gridSteps) {
      const y = padTop + plotH - (stepVal / 100) * plotH;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(w - padRight, y);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillText(`${stepVal}%`, padLeft - 8, y);
    }

    if (this.stockGraphBuffer.length < 2) {
      ctx.fillStyle = "rgba(255, 255, 255, 0.25)";
      ctx.textAlign = "center";
      ctx.fillText("Awaiting live detection stream...", padLeft + plotW / 2, padTop + plotH / 2);
      return;
    }

    const data = this.stockGraphBuffer;
    const stepX = plotW / (data.length - 1);

    // 2. Draw Smooth Bezier Curve
    ctx.beginPath();
    const points = [];
    for (let i = 0; i < data.length; i++) {
      const x = padLeft + i * stepX;
      const y = padTop + plotH - (data[i].val / 100) * plotH;
      points.push({ x, y });
    }

    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const midX = (prev.x + curr.x) / 2;
      ctx.bezierCurveTo(midX, prev.y, midX, curr.y, curr.x, curr.y);
    }

    // Dynamic gradient stroke: Green > 70%, Yellow 40-70%, Red < 40%
    const grad = ctx.createLinearGradient(padLeft, padTop + plotH, padLeft, padTop);
    grad.addColorStop(0, "#ef4444");
    grad.addColorStop(0.45, "#f59e0b");
    grad.addColorStop(0.75, "#10b981");
    grad.addColorStop(1.0, "#00f0ff");

    ctx.strokeStyle = grad;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "rgba(0, 240, 255, 0.4)";
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // 3. Area Fill under curve
    ctx.lineTo(points[points.length - 1].x, padTop + plotH);
    ctx.lineTo(points[0].x, padTop + plotH);
    ctx.closePath();
    const areaGrad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
    areaGrad.addColorStop(0, "rgba(0, 240, 255, 0.18)");
    areaGrad.addColorStop(1, "rgba(6, 9, 25, 0.0)");
    ctx.fillStyle = areaGrad;
    ctx.fill();

    // 4. Draw Leading Pulse Head Dot
    const head = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(head.x, head.y, 4, 0, 2 * Math.PI);
    ctx.fillStyle = "#00f0ff";
    ctx.shadowColor = "#00f0ff";
    ctx.shadowBlur = 10;
    ctx.fill();
    ctx.shadowBlur = 0;

    // 5. Draw Time Labels on X-Axis
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const labelStride = Math.max(1, Math.floor(data.length / 5));
    for (let i = 0; i < data.length; i += labelStride) {
      const pt = points[i];
      ctx.fillText(data[i].time.slice(3), pt.x, padTop + plotH + 6);
    }
  }

  // =========================================================================
  // LIVE HUD OVERLAY CANVAS (CAMERA OVERLAY)
  // =========================================================================
  drawHudOverlay(obs) {
    const canvas = this.hudCanvas;
    if (!canvas || !this.videoEl) return;
    const ctx = canvas.getContext("2d");

    const w = (canvas.width = canvas.clientWidth || 640);
    const h = (canvas.height = canvas.clientHeight || 480);
    ctx.clearRect(0, 0, w, h);

    if (!obs || !obs.face_present) return;

    // Coordinates mapping
    let x = w * 0.28;
    let y = h * 0.18;
    let bw = w * 0.44;
    let bh = h * 0.58;

    if (obs.face_box && Array.isArray(obs.face_box) && obs.face_box.length === 4) {
      const [bx1, by1, bx2, by2] = obs.face_box;
      // Map from 640x480 coordinate space to canvas dimensions
      x = (bx1 / 640) * w;
      y = (by1 / 480) * h;
      bw = ((bx2 - bx1) / 640) * w;
      bh = ((by2 - by1) / 480) * h;
    }

    // Neon Green Target Bounding Box
    ctx.strokeStyle = "#10b981";
    ctx.lineWidth = 1.8;
    ctx.shadowColor = "rgba(16, 185, 129, 0.7)";
    ctx.shadowBlur = 8;

    const cornerLen = 14;
    // Top-Left
    ctx.beginPath();
    ctx.moveTo(x, y + cornerLen);
    ctx.lineTo(x, y);
    ctx.lineTo(x + cornerLen, y);
    ctx.stroke();

    // Top-Right
    ctx.beginPath();
    ctx.moveTo(x + bw - cornerLen, y);
    ctx.lineTo(x + bw, y);
    ctx.lineTo(x + bw, y + cornerLen);
    ctx.stroke();

    // Bottom-Left
    ctx.beginPath();
    ctx.moveTo(x, y + bh - cornerLen);
    ctx.lineTo(x, y + bh);
    ctx.lineTo(x + cornerLen, y + bh);
    ctx.stroke();

    // Bottom-Right
    ctx.beginPath();
    ctx.moveTo(x + bw - cornerLen, y + bh);
    ctx.lineTo(x + bw, y + bh);
    ctx.lineTo(x + bw, y + bh - cornerLen);
    ctx.stroke();

    // Target pill label
    ctx.shadowBlur = 0;
    ctx.fillStyle = "rgba(16, 185, 129, 0.85)";
    const lblText = "Face Detected";
    ctx.font = "bold 11px -apple-system, sans-serif";
    const tw = ctx.measureText(lblText).width;
    const px = x + (bw - tw) / 2 - 8;
    const py = y + bh + 4;

    ctx.fillRect(px, py, tw + 16, 18);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(lblText, px + 8, py + 13);
  }

  clearHudCanvas() {
    if (!this.hudCanvas) return;
    const ctx = this.hudCanvas.getContext("2d");
    ctx.clearRect(0, 0, this.hudCanvas.width, this.hudCanvas.height);
  }

  // =========================================================================
  // LIVE EVENTS FEED TIMELINE
  // =========================================================================
  trackSessionEvents(data) {
    const currentState = data.state;
    if (!currentState || currentState === this.lastState) return;

    const now = Date.now();
    const durSec = this.lastStateTimestamp ? Math.round((now - this.lastStateTimestamp) / 1000) : 0;
    this.lastState = currentState;
    this.lastStateTimestamp = now;

    let eventTitle = "Studying (Screen)";
    let variant = "positive";

    if (currentState === "STUDYING_READING") eventTitle = "Studying (Reading)";
    else if (currentState === "STUDYING_WRITING") eventTitle = "Studying (Writing)";
    else if (currentState === "LOOKING_AWAY") { eventTitle = "Looking Away"; variant = "warning"; }
    else if (currentState === "POSSIBLE_DROWSINESS") { eventTitle = "Drowsiness (Yawning/Droop)"; variant = "danger"; }
    else if (currentState === "DISTRACTED") { eventTitle = "Phone Detected"; variant = "danger"; }
    else if (currentState === "STUDENT_ABSENT") { eventTitle = "Student Absent"; variant = "warning"; }
    else if (currentState === "FACE_OCCLUDED") { eventTitle = "Face Occluded"; variant = "warning"; }
    else if (currentState === "RECOVERING") { eventTitle = "Resuming Study Flow"; variant = "positive"; }

    this.addLiveEvent(eventTitle, variant, durSec > 0 ? `${durSec}s` : "");
  }

  addLiveEvent(name, variant, duration) {
    const d = new Date();
    const timeStr = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;

    const newEvt = { name, variant, duration, time: timeStr };
    this.eventsList.unshift(newEvt);
    if (this.eventsList.length > 20) this.eventsList.pop();

    this.renderEventsFeed();
  }

  renderEventsFeed() {
    if (!this.liveEventsFeed) return;
    this.liveEventsFeed.innerHTML = this.eventsList
      .map(
        (e) => `
        <div class="event-feed-row">
          <div class="event-feed-left">
            <span class="event-bullet ${e.variant}"></span>
            <span class="event-timestamp">${e.time}</span>
            <span class="event-name">${e.name}</span>
          </div>
          ${e.duration ? `<span class="event-duration-pill">● ${e.duration}</span>` : ""}
        </div>
      `
      )
      .join("");
  }

  // =========================================================================
  // TOP AUDIO / ACTIVITY SINE WAVEFORM ANIMATION
  // =========================================================================
  startWaveformAnimation() {
    let t = 0;
    const animateWave = () => {
      const canvas = this.topWaveCanvas;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        const w = (canvas.width = 110);
        const h = (canvas.height = 28);
        ctx.clearRect(0, 0, w, h);

        ctx.beginPath();
        const amp = this.isMonitoring && !this.isPaused ? 8 : 2;
        const freq = 0.08;

        for (let x = 0; x < w; x++) {
          const y = h / 2 + Math.sin(x * freq + t) * amp * Math.sin(x / w * Math.PI);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }

        const grad = ctx.createLinearGradient(0, 0, w, 0);
        grad.addColorStop(0, "#8b5cf6");
        grad.addColorStop(0.5, "#00f0ff");
        grad.addColorStop(1, "#38bdf8");

        ctx.strokeStyle = grad;
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      t += 0.08;
      this.waveAnimFrame = requestAnimationFrame(animateWave);
    };
    this.waveAnimFrame = requestAnimationFrame(animateWave);
  }

  // =========================================================================
  // SESSION TIMER & CLEANUP
  // =========================================================================
  startSessionTimer() {
    if (this.sessionTimer) clearInterval(this.sessionTimer);
    this.sessionTimer = setInterval(() => {
      if (!this.isMonitoring || this.isPaused) return;
      const elapsedMs = Date.now() - this.sessionStartSec;
      const totalSec = Math.floor(elapsedMs / 1000);
      const hrs = String(Math.floor(totalSec / 3600)).padStart(2, "0");
      const mins = String(Math.floor((totalSec % 3600) / 60)).padStart(2, "0");
      const secs = String(totalSec % 60).padStart(2, "0");

      if (this.topSessionTime) this.topSessionTime.textContent = `${hrs}:${mins}:${secs}`;
    }, 1000);
  }

  clearSessionData() {
    this.sparklineData.focus = [];
    this.sparklineData.attention = [];
    this.sparklineData.distraction = [];
    this.sparklineData.drowsiness = [];
    this.stockGraphBuffer = [];
    this.eventsList = [];
    this.lastState = null;
    this.renderEventsFeed();

    if (this.topSessionTime) this.topSessionTime.textContent = "00:00:00";
  }

  setCameraStatus(text, variant) {
    if (this.topCameraStatus) this.topCameraStatus.textContent = text;
    if (this.topCameraDot) this.topCameraDot.className = `dot-indicator ${variant}`;
  }

  showCameraError(msg) {
    if (this.errorBannerEl) {
      this.errorBannerEl.style.display = "flex";
      if (this.errorMessageEl) this.errorMessageEl.textContent = msg;
    }
  }

  async populateCameraOptions() {
    if (!this.cameraSelect || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter((d) => d.kind === "videoinput");
      this.cameraSelect.innerHTML = videoDevices
        .map((d, i) => `<option value="${d.deviceId}">${d.label || `Camera ${i + 1}`}</option>`)
        .join("");
    } catch (e) {
      console.warn("Could not list video devices:", e);
    }
  }
}
