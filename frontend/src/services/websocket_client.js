/**
 * frontend/js/websocket_client.js — Real-Time WebSocket Communication
 * Manages bi-directional streaming, flow-controlled frame transmission, and reconnects.
 */

export class MonitorWebSocketClient {
  constructor(url = null) {
    if (!url) {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      this.url = `${protocol}//${window.location.host}/ws/monitor`;
    } else {
      this.url = url;
    }

    this.ws = null;
    this.isConnected = false;
    this.isAwaitingAck = false;
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;

    // Callbacks
    this.onEvent = () => {};
    this.onStatusChange = () => {};
    this.onError = () => {};
  }

  /**
   * Open WebSocket connection.
   */
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
      this.ws.binaryType = "blob";

      this.ws.onopen = () => {
        console.log("[WebSocket] Connection established to", this.url);
        this.isConnected = true;
        this.isAwaitingAck = false;
        this.reconnectAttempts = 0;
        this.onStatusChange({ connected: true, statusText: "Connected" });
      };

      this.ws.onmessage = async (event) => {
        // Backend replied with processed frame event (Flow Control ACK)
        this.isAwaitingAck = false;

        try {
          if (typeof event.data === "string") {
            const data = JSON.parse(event.data);
            this.onEvent(data);
          } else if (event.data instanceof Blob) {
            const text = await event.data.text();
            const data = JSON.parse(text);
            this.onEvent(data);
          }
        } catch (e) {
          console.warn("[WebSocket] Failed to parse message:", e);
        }
      };

      this.ws.onerror = (err) => {
        console.error("[WebSocket] Connection error:", err);
        this.onError(err);
      };

      this.ws.onclose = () => {
        console.log("[WebSocket] Connection closed.");
        this.isConnected = false;
        this.isAwaitingAck = false;
        this.onStatusChange({ connected: false, statusText: "Disconnected" });
      };
    } catch (e) {
      console.error("[WebSocket] Exception creating WebSocket:", e);
      this.onStatusChange({ connected: false, statusText: "Failed to connect" });
    }
  }

  /**
   * Send a video frame Blob to backend if not waiting for prior acknowledgment.
   * @param {Blob} frameBlob
   * @returns {boolean} True if frame was sent, False if dropped due to backpressure.
   */
  sendFrame(frameBlob) {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }

    // Flow control: drop frame if prior frame is still being processed
    if (this.isAwaitingAck) {
      return false;
    }

    try {
      this.isAwaitingAck = true;
      this.ws.send(frameBlob);
      return true;
    } catch (e) {
      this.isAwaitingAck = false;
      console.warn("[WebSocket] Error sending frame:", e);
      return false;
    }
  }

  /**
   * Send text JSON command (e.g. reset, ping).
   */
  sendCommand(commandObj) {
    if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(commandObj));
    }
  }

  /**
   * Disconnect cleanly.
   */
  disconnect() {
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {
        // ignore
      }
      this.ws = null;
    }
    this.isConnected = false;
    this.isAwaitingAck = false;
    this.onStatusChange({ connected: false, statusText: "Disconnected" });
  }
}

