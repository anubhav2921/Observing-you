/**
 * frontend/js/audio_controller.js — Browser Audio Alert Manager
 * Handles alert preemption, autoplay unlock, user muting, and recovery stopping.
 */

export class BrowserAudioController {
  constructor() {
    this.audioEnabled = true;
    this.isUnlocked = false;

    // Audio elements cache
    this.audioClips = {
      occlusion: new Audio("/assets/audio/occlusion_alert.mp3"),
      drowsiness: new Audio("/assets/audio/drowsiness_alert.mp3"),
      distraction: new Audio("/assets/audio/distraction_alert.mp3"),
    };

    // Configure loop and preload
    Object.values(this.audioClips).forEach((audio) => {
      audio.preload = "auto";
      audio.loop = false;
    });

    this.currentPlayingKey = null;
    this.currentPriority = 99;

    // Attach unlock handlers to user interactions on window
    const unlockHandler = () => {
      this.unlockAudio();
      window.removeEventListener("click", unlockHandler);
      window.removeEventListener("keydown", unlockHandler);
      window.removeEventListener("touchstart", unlockHandler);
    };
    window.addEventListener("click", unlockHandler);
    window.addEventListener("keydown", unlockHandler);
    window.addEventListener("touchstart", unlockHandler);
  }

  /**
   * Unlock browser audio playback on user gesture (click).
   */
  unlockAudio() {
    if (this.isUnlocked) return;

    // Play and unlock each audio element
    Object.values(this.audioClips).forEach((audio) => {
      try {
        const promise = audio.play();
        if (promise !== undefined) {
          promise.then(() => {
            audio.pause();
            audio.currentTime = 0;
          }).catch((e) => {
            // Browser blocked until gesture
          });
        }
      } catch (err) {
        // Ignored
      }
    });

    this.isUnlocked = true;
    console.log("[AudioController] Browser audio unlocked successfully.");
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
      if (!activeAudio.paused && !activeAudio.ended) {
        return; // Already playing this alert
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
      audio.currentTime = 0;
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          this.currentPlayingKey = targetKey;
          this.currentPriority = priority;
          console.log(`[AudioController] Playing alert audio for: ${targetKey}`);
        }).catch((err) => {
          console.warn("[AudioController] Autoplay prevented by browser:", err);
          // If browser blocked it, try unlocking again
          this.isUnlocked = false;
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
}

