/**
 * frontend/js/camera_manager.js — Browser Webcam Management
 * Handles getUserMedia, track lifecycle, permissions, and frame capture.
 */

export class CameraManager {
  constructor(videoElement, captureCanvas) {
    this.videoElement = videoElement;
    this.captureCanvas = captureCanvas;
    this.ctx = captureCanvas.getContext("2d", { willReadFrequently: true });
    this.stream = null;
    this.isActive = false;

    // Safety cleanup on page exit
    window.addEventListener("beforeunload", () => this.stopCamera());
    window.addEventListener("pagehide", () => this.stopCamera());
  }

  /**
   * Request webcam access and attach stream to HTML video element.
   * @returns {Promise<{ success: boolean, error?: string, errorType?: string }>}
   */
  async startCamera() {
    if (this.isActive && this.stream) {
      return { success: true };
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return {
        success: false,
        error: "Camera API (getUserMedia) is not supported in this browser or context (requires HTTPS or localhost).",
        errorType: "NotSupportedError",
      };
    }

    try {
      const constraints = {
        audio: false,
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 10, max: 15 },
          facingMode: "user",
        },
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.videoElement.srcObject = this.stream;

      // Wait until metadata is loaded and video is playing
      await new Promise((resolve, reject) => {
        this.videoElement.onloadedmetadata = () => {
          this.videoElement.play().then(resolve).catch(reject);
        };
        this.videoElement.onerror = reject;
      });

      this.isActive = true;
      return { success: true };
    } catch (err) {
      console.error("[CameraManager] Error accessing webcam:", err);
      let errorType = err.name || "UnknownError";
      let errorMsg = err.message || "Failed to open camera.";

      if (errorType === "NotAllowedError" || errorType === "PermissionDeniedError") {
        errorMsg = "Webcam permission was denied. Please allow camera access in your browser site settings.";
      } else if (errorType === "NotFoundError" || errorType === "DevicesNotFoundError") {
        errorMsg = "No webcam device was found on this system.";
      } else if (errorType === "NotReadableError" || errorType === "TrackStartError") {
        errorMsg = "Camera is already in use by another application (e.g., local OpenCV script, Zoom, or Teams).";
      }

      this.stopCamera();
      return { success: false, error: errorMsg, errorType };
    }
  }

  /**
   * Stop all media tracks and release the camera hardware cleanly.
   */
  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch (e) {
          console.warn("[CameraManager] Error stopping track:", e);
        }
      });
      this.stream = null;
    }

    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }

    this.isActive = false;
  }

  /**
   * Capture current video frame onto hidden canvas and return JPEG Blob.
   * Enforces dimension validation to prevent empty frames.
   * @returns {Promise<Blob|null>}
   */
  captureFrameBlob(quality = 0.7) {
    if (!this.isActive || !this.videoElement || this.videoElement.readyState < 2) {
      return Promise.resolve(null);
    }

    const vw = this.videoElement.videoWidth;
    const vh = this.videoElement.videoHeight;

    if (vw === 0 || vh === 0) {
      return Promise.resolve(null);
    }

    // Match canvas dimensions to video
    if (this.captureCanvas.width !== vw || this.captureCanvas.height !== vh) {
      this.captureCanvas.width = vw;
      this.captureCanvas.height = vh;
    }

    // Draw video frame to canvas
    this.ctx.drawImage(this.videoElement, 0, 0, vw, vh);

    // Convert to Blob asynchronously
    return new Promise((resolve) => {
      this.captureCanvas.toBlob((blob) => resolve(blob), "image/jpeg", quality);
    });
  }
}

