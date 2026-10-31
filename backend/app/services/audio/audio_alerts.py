"""
audio_alerts.py — Centralized, non-blocking audio controller with priority hierarchy,
cooldown management, and recovery stop behavior.

Priority hierarchy:
  1. CAMERA_ERROR        (Technical warning tone, NOT a student blame meme)
  2. STUDENT_ABSENT      (Absence alert)
  3. FACE_OCCLUDED       (Occlusion alert)
  4. POSSIBLE_DROWSINESS (Sleepiness alert: "uth jaa")
  5. DISTRACTED / INACTIVITY / LOOKING_AWAY (Distraction meme: "IAS ki Tayari")
  6. Normal studying (STUDYING, STUDYING_READING, RECOVERING, etc.) -> NO alert, stops active alert
"""

from __future__ import annotations

import io
import math
import os
import struct
import threading
import time
import wave
from typing import Dict, Optional, Tuple

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False

import backend.app.core.config as config
from backend.app.services.behavior.behavior_types import BehaviorLabel
from backend.app.services.decision.state_machine import StudyState


def _safe_str(s: str) -> str:
    """Return an ASCII-safe representation of string for Windows console printing."""
    return s.encode("ascii", errors="replace").decode("ascii")


def _init_mixer() -> bool:
    """Init pygame mixer once; return True on success."""
    if not _PYGAME_OK:
        return False
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        return True
    except Exception as exc:
        print(f"[AudioAlert] pygame.mixer init failed: {exc}")
        return False


def _generate_beep_wav(frequency: float = 660.0, duration_sec: float = 0.5) -> bytes:
    """Generate a simple PCM WAV beep in-memory for technical alerts or fallback."""
    sample_rate = 44100
    num_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            # Apply cosine envelope to prevent audio clicking
            env = 0.5 * (1.0 - math.cos(2.0 * math.pi * i / num_samples))
            val = int(env * 16000.0 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            frames.extend(struct.pack("<h", max(-32768, min(32767, val))))
        wf.writeframes(frames)
    return buf.getvalue()


class CentralAudioManager:
    """
    Authoritative, non-blocking audio manager.
    Enforces single active playback, strict priority preemption,
    per-state cooldowns, and instant stop upon recovery.
    """

    # Priority mapping (lower integer = higher priority)
    STATE_PRIORITY: Dict[Any, int] = {
        # StudyState
        StudyState.CAMERA_ERROR:            1,
        StudyState.STUDENT_ABSENT:           2,
        StudyState.FACE_OCCLUDED:            3,
        StudyState.POSSIBLE_DROWSINESS:     4,
        StudyState.DISTRACTED:               5,
        StudyState.INACTIVITY_WARNING:       5,
        StudyState.LOOKING_AWAY:             5,
        # BehaviorLabel
        BehaviorLabel.CAMERA_ERROR:          1,
        BehaviorLabel.STUDENT_ABSENT:        2,
        BehaviorLabel.FACE_FULLY_OCCLUDED:   3,
        BehaviorLabel.POSSIBLE_DROWSINESS:   4,
        BehaviorLabel.POSSIBLE_DISTRACTION:  5,
        BehaviorLabel.INACTIVITY_WARNING:    5,
        BehaviorLabel.LOOKING_AWAY:          5,
        BehaviorLabel.OFF_TASK_CANDIDATE:    5,
    }

    def __init__(self, enabled: bool = config.AUDIO_ENABLED):
        self.enabled = enabled
        self._lock = threading.Lock()
        self._mixer_ready = _init_mixer() if self.enabled else False

        # Loaded sound objects cache: key -> pygame.mixer.Sound
        self._sounds: Dict[str, Optional[object]] = {}
        # Cooldown trackers: state -> last_played_timestamp
        self._last_played: Dict[Any, float] = {}

        # Active playback state
        self._active_state: Optional[Any] = None
        self._active_priority: int = 999
        self._active_channel: Optional[object] = None
        self._is_playing: bool = False

        # Fallback technical beep sound
        self._fallback_beep: Optional[object] = None
        if self._mixer_ready:
            try:
                beep_bytes = _generate_beep_wav(frequency=750.0, duration_sec=0.4)
                self._fallback_beep = pygame.mixer.Sound(io.BytesIO(beep_bytes))
            except Exception:
                self._fallback_beep = None

        # Pre-resolve sound files
        self._init_audio_sources()

    def _init_audio_sources(self) -> None:
        """Resolve and preload audio files."""
        if not self._mixer_ready:
            return

        file_mappings = {
            "distraction": config.AUDIO_DISTRACTION_FILE,
            "sleepiness": config.AUDIO_SLEEPINESS_FILE,
            "camera_error": config.AUDIO_CAMERA_ERROR_FILE,
            "absent": config.AUDIO_ABSENT_FILE or config.AUDIO_DISTRACTION_FILE,
            "occlusion": config.AUDIO_OCCLUSION_FILE or config.AUDIO_DISTRACTION_FILE,
        }

        for key, path in file_mappings.items():
            if not path or not os.path.isfile(path):
                self._sounds[key] = None
                continue
            try:
                sound = pygame.mixer.Sound(path)
                self._sounds[key] = sound
                safe_name = _safe_str(os.path.basename(path))
                print(f"[CentralAudio] Loaded '{key}' audio: {safe_name}")
            except Exception as e:
                print(f"[CentralAudio] Could not load '{key}' audio from {path}: {e}")
                self._sounds[key] = None

    # ──────────────────────────────────────────────────────────────────
    def update_state(self, current_state: Any, cooldown: float = config.ALERT_COOLDOWN_SECONDS) -> bool:
        """
        Notify audio manager of current authoritative state.
        - If normal studying/recovering, stops any active alert.
        - If an alert state is active, triggers appropriate alert respecting priority & cooldown.
        Returns True if an alert was newly triggered.
        """
        # Clean check: if state is NOT an alert state or in diagnostic mode, stop audio immediately
        if getattr(config, "DIAGNOSTIC_MODE", False):
            self.stop()
            return False

        if current_state not in self.STATE_PRIORITY:
            self.stop()
            return False

        if not self.enabled or not self._mixer_ready:
            return False

        state_priority = self.STATE_PRIORITY[current_state]
        now = time.monotonic()

        with self._lock:
            # If an alert is already playing:
            if self._is_playing:
                # Check if still busy
                if self._active_channel is not None and not self._active_channel.get_busy():
                    self._is_playing = False
                    self._active_state = None
                    self._active_priority = 999

            if self._is_playing:
                # If current state has strictly higher priority (lower number), preempt active alert!
                if state_priority < self._active_priority:
                    prev_name = self._active_state.name if hasattr(self._active_state, "name") else str(self._active_state)
                    print(f"[CentralAudio] Preempting active alert '{prev_name}' (P{self._active_priority}) with higher priority '{current_state.name}' (P{state_priority})")
                    self._stop_locked()
                else:
                    # Active alert has equal or higher priority: do not interrupt
                    act_name = self._active_state.name if hasattr(self._active_state, "name") else str(self._active_state)
                    # print(f"[CentralAudio] Alert {current_state.name} ignored: active alert '{act_name}' (P{self._active_priority}) playing")
                    return False

            # Check cooldown for this state
            last_time = self._last_played.get(current_state, 0.0)
            if (now - last_time) < cooldown:
                return False

            # Trigger sound
            sound = self._select_sound_for_state(current_state)
            if sound is None:
                # Use fallback technical beep if available, otherwise silent
                sound = self._fallback_beep

            if sound is None:
                return False

            try:
                channel = sound.play()
                if channel is not None:
                    self._active_channel = channel
                    self._active_state = current_state
                    self._active_priority = state_priority
                    self._is_playing = True
                    self._last_played[current_state] = now
                    print(f"[CentralAudio] Playing alert for state: {current_state.name} (Priority {state_priority})")
                    return True
            except Exception as e:
                print(f"[CentralAudio] Play error: {e}")
                return False

        return False

    def _select_sound_for_state(self, state: Any) -> Optional[object]:
        """Map state to preloaded sound."""
        if state in (StudyState.CAMERA_ERROR, BehaviorLabel.CAMERA_ERROR):
            return self._sounds.get("camera_error") or self._fallback_beep
        elif state in (StudyState.POSSIBLE_DROWSINESS, BehaviorLabel.POSSIBLE_DROWSINESS):
            return self._sounds.get("sleepiness")
        elif state in (StudyState.STUDENT_ABSENT, BehaviorLabel.STUDENT_ABSENT):
            return self._sounds.get("absent") or self._sounds.get("distraction")
        elif state in (StudyState.FACE_OCCLUDED, BehaviorLabel.FACE_FULLY_OCCLUDED):
            if not getattr(config, "OCCLUSION_ALERT_ENABLED", True):
                return None
            return self._sounds.get("occlusion") or self._sounds.get("distraction")
        elif state in (
            StudyState.DISTRACTED,
            StudyState.INACTIVITY_WARNING,
            StudyState.LOOKING_AWAY,
            BehaviorLabel.POSSIBLE_DISTRACTION,
            BehaviorLabel.INACTIVITY_WARNING,
            BehaviorLabel.LOOKING_AWAY,
            BehaviorLabel.OFF_TASK_CANDIDATE,
        ):
            if not getattr(config, "DISTRACTION_ALERT_ENABLED", True):
                return None
            return self._sounds.get("distraction")
        return None

    def stop(self) -> None:
        """Immediately stop any active alert playback."""
        with self._lock:
            self._stop_locked()

    def stop_alert(self) -> None:
        """Alias for stop() for backward compatibility."""
        self.stop()

    def update_audio(
        self,
        state: Any,
        now: Optional[float] = None,
        cooldown: float = config.ALERT_COOLDOWN_SECONDS,
    ) -> bool:
        """Alias for update_state() with optional timestamp parameter."""
        return self.update_state(state, cooldown=cooldown)

    def _stop_locked(self) -> None:
        """Internal stop with lock already held."""
        try:
            if self._active_channel is not None:
                self._active_channel.stop()
        except Exception:
            pass
        self._is_playing = False
        self._active_state = None
        self._active_priority = 999
        self._active_channel = None

    @property
    def is_playing(self) -> bool:
        with self._lock:
            if self._is_playing and self._active_channel is not None:
                if not self._active_channel.get_busy():
                    self._is_playing = False
            return self._is_playing

    @property
    def active_state(self) -> Optional[StudyState]:
        return self._active_state


STATE_PRIORITY = CentralAudioManager.STATE_PRIORITY


# ──────────────────────────────────────────────────────────────────────
#  Legacy Backward Compatibility Wrapper (AudioAlert & build_alerts)
# ──────────────────────────────────────────────────────────────────────

class AudioAlert:
    """Backward-compatible single channel alert wrapping CentralAudioManager."""

    def __init__(self, name: str, audio_path: str, enabled: bool) -> None:
        self.name = name
        self.audio_path = audio_path
        self.enabled = enabled
        self._last_played: float = 0.0
        self._lock = threading.Lock()
        self._is_playing = False
        self._sound: Optional[object] = None

        if not enabled or not _init_mixer():
            self.enabled = False
            return

        if os.path.isfile(audio_path):
            try:
                self._sound = pygame.mixer.Sound(audio_path)
            except Exception:
                self.enabled = False

    def trigger(self, cooldown: float = config.ALERT_COOLDOWN_SECONDS) -> bool:
        if not self.enabled or self._sound is None:
            return False
        now = time.monotonic()
        with self._lock:
            if self._is_playing or (now - self._last_played < cooldown):
                return False
            self._last_played = now
            self._is_playing = True

        try:
            channel = self._sound.play()
            if channel is not None:
                def _wait():
                    while channel.get_busy():
                        time.sleep(0.05)
                    with self._lock:
                        self._is_playing = False
                threading.Thread(target=_wait, daemon=True).start()
                return True
        except Exception:
            pass
        with self._lock:
            self._is_playing = False
        return False

    def stop(self) -> None:
        try:
            if self._sound is not None:
                self._sound.stop()
        except Exception:
            pass
        with self._lock:
            self._is_playing = False


def build_alerts() -> Tuple[AudioAlert, AudioAlert]:
    """Construct distraction + sleepiness alerts for backward compatibility."""
    _init_mixer()
    dist = AudioAlert(
        name="distraction",
        audio_path=config.AUDIO_DISTRACTION_FILE,
        enabled=config.AUDIO_ENABLED and config.DISTRACTION_ALERT_ENABLED,
    )
    sleep = AudioAlert(
        name="sleepiness",
        audio_path=config.AUDIO_SLEEPINESS_FILE,
        enabled=config.AUDIO_ENABLED and config.SLEEPINESS_ALERT_ENABLED,
    )
    return dist, sleep
