/**
 * frontend/src/utils/audio_controller.js — Browser Audio Alert Manager
 * Handles alert preemption, autoplay unlock, user muting, volume control, and recovery stopping.
 */

export class BrowserAudioController {
  constructor() {
    this.audioEnabled = true;
    this.isUnlocked = false;
    this.volume = 1.0;
    this.audioCtx = null;

    // Audio elements cache
    this.audioClips = {
      occlusion: new Audio("/assets/audio/occlusion_alert.mp3"),
      drowsiness: new Audio("/assets/audio/drowsiness_alert.mp3"),
      distraction: new Audio("/assets/audio/distraction_alert.mp3"),
    };

    // Configure preloading and volume
    Object.values(this.audioClips).forEach((audio) => {
      audio.preload = "auto";
      audio.loop = false;
      audio.volume = this.volume;
    });

    this.currentPlayingKey = null;
    this.currentPriority = 99;

    // Attach unlock handlers to any user gesture on window
    const unlockHandler = () => {
      this.unlockAudio();
    };
    window.addEventListener("click", unlockHandler, { passive: true });
    window.addEventListener("keydown", unlockHandler, { passive: true });
    window.addEventListener("touchstart", unlockHandler, { passive: true });
  }

  /**
   * Unlock browser audio playback on user gesture (click or keypress).
   */
  unlockAudio() {
    if (!this.audioCtx) {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          this.audioCtx = new AudioCtx();
        }
      } catch (e) {
        console.warn("[AudioController] Web Audio API init error:", e);
      }
    }

    if (this.audioCtx && this.audioCtx.state === "suspended") {
      this.audioCtx.resume().catch(() => {});
    }

    // Preload audio elements
    Object.values(this.audioClips).forEach((audio) => {
      try {
        audio.load();
      } catch (err) {
        // Ignored
      }
    });

    this.isUnlocked = true;
    console.log("[AudioController] Browser audio unlocked successfully.");
  }

  /**
   * Set playback volume (0.0 to 1.0).
   */
  setVolume(vol) {
    this.volume = Math.max(0, Math.min(1, vol));
    Object.values(this.audioClips).forEach((audio) => {
      audio.volume = this.volume;
    });
  }

  /**
   * Toggle mute status.
   * @returns {boolean} New audioEnabled state.
   */
  toggleMute() {
    this.audioEnabled = !this.audioEnabled;
    if (!this.audioEnabled) {
      this.stopAll();
    }
    return this.audioEnabled;
  }

  /**
   * Stop all active audio playback.
   */
  stopAll() {
    Object.values(this.audioClips).forEach((audio) => {
      try {
        audio.pause();
        audio.currentTime = 0;
      } catch (e) {
        // ignore
      }
    });
    this.currentPlayingKey = null;
    this.currentPriority = 99;
  }

  /**
   * Alias for stopAll() for compatibility.
   */
  stop() {
    this.stopAll();
  }

  /**
   * Primary entrypoint called by App.js on WebSocket state updates.
   * @param {Object} alertData - { active, name, priority, audio_file, reason }
   */
  evaluateAlert(alertData) {
    this.handleAlertEvent(alertData);
  }

  /**
   * Handle incoming alert event from backend.
   * @param {Object} alertData - { active, name, priority, audio_file, reason }
   */
  handleAlertEvent(alertData) {
    if (!alertData) {
      this.stopAll();
      return;
    }

    // If alert cleared or student is studying/recovering, stop audio immediately
    if (!alertData.active) {
      if (this.currentPlayingKey !== null) {
        this.stopAll();
      }
      return;
    }

    if (!this.audioEnabled) {
      return;
    }

    // Resume AudioContext if suspended
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      this.audioCtx.resume().catch(() => {});
    }

    // Determine target clip key
    let targetKey = "distraction";
    const name = (alertData.name || "").toUpperCase();
    if (name.includes("OCCLUD")) {
      targetKey = "occlusion";
    } else if (name.includes("DROWS") || name.includes("SLEEP")) {
      targetKey = "drowsiness";
    }

    const priority = alertData.priority !== null && alertData.priority !== undefined ? alertData.priority : 5;

    // Check if clip is already actively playing
    if (this.currentPlayingKey === targetKey) {
      const activeAudio = this.audioClips[targetKey];
      if (activeAudio && !activeAudio.paused && !activeAudio.ended) {
        return; // Already actively playing this alert
      }
    }

    // Preemption: Stop if current priority is lower (numerically higher)
    if (this.currentPlayingKey !== null && priority < this.currentPriority) {
      console.log(`[AudioController] Preempting ${this.currentPlayingKey} (P${this.currentPriority}) with ${targetKey} (P${priority})`);
      this.stopAll();
    }

    // Play target audio
    const audio = this.audioClips[targetKey];
    if (audio) {
      audio.volume = this.volume;
      audio.currentTime = 0;
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            this.currentPlayingKey = targetKey;
            this.currentPriority = priority;
            console.log(`[AudioController] Playing alert audio for: ${targetKey}`);
          })
          .catch((err) => {
            console.warn("[AudioController] Autoplay prevented by browser:", err);
            this.isUnlocked = false;
            // Play synthetic WebAudio fallback tone if element was blocked
            this._playFallbackTone(targetKey);
          });
      }

      audio.onended = () => {
        if (this.currentPlayingKey === targetKey) {
          this.currentPlayingKey = null;
          this.currentPriority = 99;
        }
      };
    }
  }

  /**
   * Synthetic Web Audio fallback tone in case media element playback is blocked.
   */
  _playFallbackTone(targetKey) {
    try {
      if (!this.audioCtx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) this.audioCtx = new AudioCtx();
      }
      if (!this.audioCtx) return;

      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      const freq = targetKey === "drowsiness" ? 440 : (targetKey === "occlusion" ? 587 : 784);
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);

      gain.gain.setValueAtTime(0.3 * this.volume, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.4);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start();
      osc.stop(this.audioCtx.currentTime + 0.4);
    } catch (e) {
      // Ignore
    }
  }
}
