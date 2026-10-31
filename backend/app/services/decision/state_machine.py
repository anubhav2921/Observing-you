"""
state_machine.py — Robust Centralized State Machine for AI Study Monitoring.
Handles explicit state transitions, hysteresis, rolling smoothing, and diagnostics.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

import backend.app.core.config as config
from backend.app.core.logging import StructuredLogger


class StudyState(Enum):
    STUDYING                    = auto()
    STUDYING_READING            = auto()
    STUDYING_WRITING            = auto()
    MONITORING                  = auto()
    LOOKING_AWAY                = auto()
    STUDY_ACTIVITY_UNCONFIRMED  = auto()
    INACTIVITY_WARNING          = auto()
    DISTRACTED                  = auto()
    POSSIBLE_DROWSINESS         = auto()
    FACE_OCCLUDED               = auto()
    OCCLUSION_UNCERTAIN         = auto()
    STUDENT_ABSENT              = auto()
    CAMERA_ERROR                = auto()
    LOW_VISIBILITY              = auto()
    RECOVERING                  = auto()

    # Aliases for backward compatibility
    ATTENTIVE                   = STUDYING
    PHONE_DETECTED              = DISTRACTED
    POSSIBLY_SLEEPY             = POSSIBLE_DROWSINESS
    FACE_COVERED                = FACE_OCCLUDED
    PROLONGED_INACTIVITY        = INACTIVITY_WARNING
    CAMERA_BLOCKED              = CAMERA_ERROR
    LOW_CONFIDENCE              = OCCLUSION_UNCERTAIN
    UNKNOWN                     = MONITORING


# Display properties for UI (Label text, BGR Color)
STATE_DISPLAY: Dict[StudyState, Tuple[str, Tuple[int, int, int]]] = {
    StudyState.STUDYING:                   ("[OK] STUDYING",                   (0, 200, 80)),
    StudyState.STUDYING_READING:           ("[READ] READING / NOTES",           (0, 220, 140)),
    StudyState.STUDYING_WRITING:           ("[WRITE] WRITING / DESK WORK",      (0, 210, 180)),
    StudyState.MONITORING:                 ("[~] MONITORING",                  (200, 200, 120)),
    StudyState.LOOKING_AWAY:               ("[!] LOOKING AWAY",                 (0, 165, 255)),
    StudyState.STUDY_ACTIVITY_UNCONFIRMED: ("[?] ACTIVITY UNCONFIRMED",         (0, 180, 240)),
    StudyState.INACTIVITY_WARNING:         ("[!] INACTIVITY WARNING",           (0, 140, 255)),
    StudyState.DISTRACTED:                 ("[OFF-TASK] DISTRACTED (PHONE)",    (0, 60, 220)),
    StudyState.POSSIBLE_DROWSINESS:        ("[Zz] POSSIBLE DROWSINESS",         (0, 60, 255)),
    StudyState.FACE_OCCLUDED:              ("[X] FACE OCCLUDED",                (80, 100, 220)),
    StudyState.OCCLUSION_UNCERTAIN:        ("[?] OCCLUSION UNCERTAIN",          (160, 160, 80)),
    StudyState.STUDENT_ABSENT:             ("[--] STUDENT ABSENT",              (120, 120, 120)),
    StudyState.CAMERA_ERROR:               ("[ERROR] CAMERA FAULT",             (30, 30, 240)),
    StudyState.LOW_VISIBILITY:             ("[VIS] LOW VISIBILITY",             (80, 80, 160)),
    StudyState.RECOVERING:                 ("[REC] RESUMING STUDY",             (80, 220, 160)),
}

STATE_RESPONSES: Dict[StudyState, str] = {
    StudyState.STUDYING:                   "Student is focused and studying.",
    StudyState.STUDYING_READING:           "Student is actively reading study material.",
    StudyState.STUDYING_WRITING:           "Student is actively writing / desk studying.",
    StudyState.MONITORING:                 "System initializing / evaluating baseline.",
    StudyState.LOOKING_AWAY:               "Attention reminder: Gaze turned away.",
    StudyState.STUDY_ACTIVITY_UNCONFIRMED: "Looking toward camera without clear study activity.",
    StudyState.INACTIVITY_WARNING:         "Inactivity alert: Prolonged staring without activity.",
    StudyState.DISTRACTED:                 "Distraction alert: Off-task behavior (phone).",
    StudyState.POSSIBLE_DROWSINESS:        "Drowsiness alert: Sustained eye closure / head droop.",
    StudyState.FACE_OCCLUDED:              "Visibility alert: Sustained face concealment.",
    StudyState.OCCLUSION_UNCERTAIN:        "Face landmarks unavailable; posture indeterminate.",
    StudyState.STUDENT_ABSENT:             "Absence alert: No student detected in view.",
    StudyState.CAMERA_ERROR:               "Technical alert: Camera feed interrupted or frozen.",
    StudyState.LOW_VISIBILITY:             "Lighting warning: Camera view is underexposed/dark.",
    StudyState.RECOVERING:                 "Study activity resumed; stabilizing.",
}

# Warning / Alert States that require recovery before returning to normal studying
ALERT_STATES: set[StudyState] = {
    StudyState.DISTRACTED,
    StudyState.INACTIVITY_WARNING,
    StudyState.POSSIBLE_DROWSINESS,
    StudyState.FACE_OCCLUDED,
    StudyState.STUDENT_ABSENT,
    StudyState.CAMERA_ERROR,
}


@dataclass
class DetectorSignals:
    """Raw detector inputs for a single time step."""
    timestamp: float                       # Monotonic time
    camera_valid: bool = True              # Camera read succeeded
    frame_frozen: bool = False             # Frame pixels identical to previous
    low_visibility: bool = False           # Mean intensity < threshold
    person_detected: bool = False          # YOLO person detected
    person_conf: float = 0.0
    person_box: Optional[Tuple[int, int, int, int]] = None
    face_detected: bool = False            # MediaPipe face detected
    face_conf: float = 0.0
    face_box: Optional[Tuple[int, int, int, int]] = None
    ear: Optional[float] = None            # Eye Aspect Ratio
    head_yaw: Optional[float] = None       # Degrees (- = left, + = right)
    head_pitch: Optional[float] = None     # Degrees (+ = down)
    phone_detected: bool = False           # YOLO cell phone
    book_detected: bool = False            # YOLO book
    laptop_detected: bool = False          # YOLO laptop
    hands_near_face: bool = False          # Hands/objects over head area
    motion_score: float = 0.0              # Estimated inter-frame motion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cam_ok": self.camera_valid,
            "frozen": self.frame_frozen,
            "low_vis": self.low_visibility,
            "person": self.person_detected,
            "face": self.face_detected,
            "ear": round(self.ear, 3) if self.ear is not None else None,
            "yaw": round(self.head_yaw, 1) if self.head_yaw is not None else None,
            "pitch": round(self.head_pitch, 1) if self.head_pitch is not None else None,
            "phone": self.phone_detected,
            "book": self.book_detected,
            "laptop": self.laptop_detected,
            "hands_face": self.hands_near_face,
            "motion": round(self.motion_score, 4),
        }


@dataclass
class StateEvaluation:
    """Authoritative state output for a single time step."""
    state: StudyState
    confidence: float
    duration_in_state: float
    trigger_condition: str
    signals: DetectorSignals
    transitioned: bool = False
    prev_state: Optional[StudyState] = None
    recovery_reason: Optional[str] = None


class StudyStateMachine:
    """
    Centralized, deterministic state manager with elapsed-duration tracking,
    hysteresis, rolling consensus smoothing, and structured logging.
    """

    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger
        self.current_state = StudyState.MONITORING
        self.state_enter_time: Optional[float] = None
        self.last_transition_time: Optional[float] = None

        # Duration accumulator timers (start timestamps in monotonic seconds)
        self._absent_start: Optional[float] = None
        self._camera_error_start: Optional[float] = None
        self._low_vis_start: Optional[float] = None
        self._phone_start: Optional[float] = None
        self._eye_closed_start: Optional[float] = None
        self._droop_start: Optional[float] = None
        self._gaze_away_start: Optional[float] = None
        self._staring_start: Optional[float] = None
        self._occlusion_start: Optional[float] = None
        self._recovery_start: Optional[float] = None

        # Prior active alert state being recovered from
        self._recovering_from_state: Optional[StudyState] = None

        # Rolling history for smoothing (holds recent raw instantaneous candidate states)
        self._history: deque[Tuple[float, StudyState]] = deque()
        self._max_history_sec = config.SMOOTHING_WINDOW_SECS

        # Diagnostics
        self.last_confidence: float = 1.0
        self.last_signals: Optional[DetectorSignals] = None

    # ──────────────────────────────────────────────────────────────────
    def update(self, signals: DetectorSignals) -> StateEvaluation:
        """
        Evaluate new detector signals and update the authoritative state.
        Uses time.monotonic() timestamps and elapsed durations.
        """
        now = signals.timestamp
        if self.state_enter_time is None:
            self.state_enter_time = now
            self.last_transition_time = now

        self.last_signals = signals

        # Clean rolling history
        cutoff = now - self._max_history_sec
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

        # Step 1: Evaluate raw instantaneous candidate state and update timers
        candidate, trigger, conf = self._evaluate_candidate(signals, now)
        self._history.append((now, candidate))

        # Step 2: Rolling consensus smoothing
        smoothed_state = self._compute_consensus(candidate)

        # Step 3: Handle explicit transitions with hysteresis & recovery rules
        new_state, transition_trigger, final_conf, rec_reason = self._handle_transitions(
            smoothed_state, trigger, conf, signals, now
        )

        transitioned = False
        prev_state = self.current_state

        if new_state != self.current_state:
            transitioned = True
            dur_in_prev = now - self.state_enter_time
            self.current_state = new_state
            self.state_enter_time = now
            self.last_transition_time = now
            self.last_confidence = final_conf

            if self.logger:
                self.logger.log_transition(
                    prev_state=prev_state.name,
                    new_state=new_state.name,
                    trigger_condition=transition_trigger,
                    confidence=final_conf,
                    elapsed_duration=dur_in_prev,
                    detector_outputs=signals.to_dict(),
                    audio_event=new_state.name if new_state in ALERT_STATES else "none",
                    recovery_reason=rec_reason,
                )

        state_duration = now - self.state_enter_time

        return StateEvaluation(
            state=self.current_state,
            confidence=final_conf,
            duration_in_state=state_duration,
            trigger_condition=transition_trigger,
            signals=signals,
            transitioned=transitioned,
            prev_state=prev_state if transitioned else None,
            recovery_reason=rec_reason,
        )

    # ──────────────────────────────────────────────────────────────────
    def _evaluate_candidate(
        self, s: DetectorSignals, now: float
    ) -> Tuple[StudyState, str, float]:
        """
        Hierarchical evaluation of candidate state from physical signals and durations.
        Updates duration timers.
        """
        # 1. Camera Faults (Highest priority technical failures)
        if not s.camera_valid or s.frame_frozen:
            if self._camera_error_start is None:
                self._camera_error_start = now
            dur = now - self._camera_error_start
            trigger = "Camera feed lost" if not s.camera_valid else "Frozen camera frame detected"
            conf = min(1.0, 0.7 + (dur / 2.0))
            return StudyState.CAMERA_ERROR, trigger, conf
        else:
            self._camera_error_start = None

        # 2. Low Lighting / Visibility
        if s.low_visibility:
            if self._low_vis_start is None:
                self._low_vis_start = now
            return StudyState.LOW_VISIBILITY, "Low scene illumination / underexposure", 0.85
        else:
            self._low_vis_start = None

        # 3. Student Absence (No person detected by YOLO)
        if not s.person_detected:
            if self._absent_start is None:
                self._absent_start = now
            dur = now - self._absent_start
            if dur >= config.STUDENT_ABSENT_SECS:
                return StudyState.STUDENT_ABSENT, f"Student absent for {dur:.1f}s", 0.95
            return StudyState.MONITORING, f"Person absent ({dur:.1f}s / {config.STUDENT_ABSENT_SECS}s)", 0.6
        else:
            self._absent_start = None

        # Person is present in the frame from here onwards:

        # 4. Off-task Phone Distraction
        if s.phone_detected:
            if self._phone_start is None:
                self._phone_start = now
            dur = now - self._phone_start
            if dur >= config.PHONE_DETECT_SECS:
                return StudyState.DISTRACTED, f"Cell phone detected for {dur:.1f}s", 0.92
        else:
            self._phone_start = None

        # 5. Face Visibility & Reading vs Occlusion Discrimination
        if not s.face_detected:
            # Face landmarks are not detected, but person is present!
            # Could be:
            #   (A) Deliberate face concealment (hands/object covering face)
            #   (B) Reading (head pitched down at book/notebook, book occluding chin/face)
            #   (C) Ambiguous (neither clearly reading nor clearly hiding)

            is_reading_pose = (
                s.book_detected
                or (s.head_pitch is not None and config.READING_PITCH_MIN_DEG <= s.head_pitch <= config.READING_PITCH_MAX_DEG)
            )

            if s.hands_near_face and not s.book_detected:
                # Sustained hands covering face -> FACE_OCCLUDED
                if self._occlusion_start is None:
                    self._occlusion_start = now
                dur = now - self._occlusion_start
                if dur >= config.FACE_OCCLUDED_SECS:
                    return StudyState.FACE_OCCLUDED, f"Face covered by hands for {dur:.1f}s", 0.90
                return StudyState.OCCLUSION_UNCERTAIN, f"Face hidden by hands ({dur:.1f}s)", 0.65

            elif is_reading_pose or (s.book_detected and s.motion_score > 0.002):
                # Visibly reading! Do NOT classify as occluded.
                self._occlusion_start = None
                return StudyState.STUDYING_READING, "Reading book/notes (face landmarks obscured)", 0.88

            else:
                # Person present, face not detected, not clearly reading:
                # Deliberate face concealment, face covered by cloth/hood/arms, or hidden away
                if self._occlusion_start is None:
                    self._occlusion_start = now
                dur = now - self._occlusion_start
                if dur >= config.FACE_OCCLUDED_SECS:
                    # Sustained face concealment / hidden face -> trigger FACE_OCCLUDED alert!
                    return StudyState.FACE_OCCLUDED, f"Face hidden / concealed for {dur:.1f}s", 0.88
                return StudyState.OCCLUSION_UNCERTAIN, f"Face not detected ({dur:.1f}s)", 0.60
        else:
            # Face is detected! Reset occlusion timer
            self._occlusion_start = None

        # Face is present and landmarks are available:

        # 6. Sleepiness / Drowsiness Detection
        # Sustained eye closure or repeated drooping
        ear = s.ear if s.ear is not None else 0.30
        pitch = s.head_pitch if s.head_pitch is not None else 0.0
        eyes_closed = ear < config.EAR_CLOSE_THRESHOLD
        borderline_closed = ear < config.BORDERLINE_EAR_THRESHOLD
        head_drooping = pitch > config.HEAD_PITCH_DROOP_DEG

        if eyes_closed:
            if self._eye_closed_start is None:
                self._eye_closed_start = now
            dur = now - self._eye_closed_start
            if dur >= config.DROWSINESS_SUSTAINED_SECS:
                return StudyState.POSSIBLE_DROWSINESS, f"Eyes closed for {dur:.1f}s (EAR: {ear:.2f})", 0.92
        else:
            # Normal eye opening resets eye-closed timer immediately (no false accumulation across blinks)
            self._eye_closed_start = None

        if head_drooping and borderline_closed:
            if self._droop_start is None:
                self._droop_start = now
            dur = now - self._droop_start
            if dur >= config.DROOP_SUSTAINED_SECS:
                return StudyState.POSSIBLE_DROWSINESS, f"Head droop + drowsy eyes for {dur:.1f}s", 0.86
        else:
            self._droop_start = None

        # 7. Looking Away (Lateral head turn)
        yaw = s.head_yaw if s.head_yaw is not None else 0.0
        looking_away = abs(yaw) > config.HEAD_YAW_THRESHOLD_DEG
        if looking_away:
            if self._gaze_away_start is None:
                self._gaze_away_start = now
            dur = now - self._gaze_away_start
            if dur >= config.LOOKING_AWAY_SECS:
                return StudyState.LOOKING_AWAY, f"Head turned away ({yaw:+.1f} deg) for {dur:.1f}s", 0.90
        else:
            self._gaze_away_start = None

        # 8. Camera-Staring & Inactivity vs Active Study
        # If student looks straight at camera or sits motionless with no study materials
        camera_facing = abs(yaw) < 18.0 and abs(pitch) < 16.0
        no_study_materials = (not s.book_detected) and (not s.laptop_detected)
        still_motion = s.motion_score < config.MOTION_STILL_THRESHOLD
        is_inactive = no_study_materials and (still_motion or (camera_facing and still_motion))

        if is_inactive:
            if self._staring_start is None:
                self._staring_start = now
            dur = now - self._staring_start
            if dur >= config.INACTIVITY_WARNING_SECS:
                return StudyState.INACTIVITY_WARNING, f"Inactivity / motionless for {dur:.1f}s", 0.88
            elif dur >= config.CAMERA_STARING_UNCONFIRMED_SECS:
                return StudyState.STUDY_ACTIVITY_UNCONFIRMED, f"Facing camera / idle without study materials ({dur:.1f}s)", 0.72
        else:
            self._staring_start = None

        # 9. Active Study Classification
        # Reading vs Writing vs General Studying
        if s.laptop_detected:
            return StudyState.STUDYING_WRITING, "Attentive laptop / keyboard study", 0.92

        if s.book_detected or (config.READING_PITCH_MIN_DEG <= pitch <= config.READING_PITCH_MAX_DEG and abs(yaw) <= config.READING_YAW_MAX_DEG):
            return StudyState.STUDYING_READING, "Attentive reading (book or desk notes)", 0.93

        if s.motion_score > 0.015 and pitch > 5.0:
            return StudyState.STUDYING_WRITING, "Attentive writing / typing", 0.90

        return StudyState.STUDYING, "Attentive study posture", 0.92

    # ──────────────────────────────────────────────────────────────────
    def _compute_consensus(self, latest: StudyState) -> StudyState:
        """Rolling window majority vote to smooth high-frequency detector noise."""
        if not self._history:
            return latest

        # Direct adoption for alert states whose durations have already been verified by timers
        if latest in ALERT_STATES:
            return latest

        counts: Dict[StudyState, int] = {}
        for _, st in self._history:
            counts[st] = counts.get(st, 0) + 1

        total = len(self._history)
        best_state, count = max(counts.items(), key=lambda item: item[1])

        # Require minimum consensus ratio to override current state
        if (count / total) >= config.MIN_STATE_CONSENSUS_RATIO:
            return best_state
        return self.current_state

    # ──────────────────────────────────────────────────────────────────
    def _handle_transitions(
        self,
        candidate_state: StudyState,
        trigger: str,
        conf: float,
        signals: DetectorSignals,
        now: float,
    ) -> Tuple[StudyState, str, float, Optional[str]]:
        """
        State transition logic enforcing hysteresis, stability periods, and recovery.
        """
        current = self.current_state

        # Immediate priority: CAMERA_ERROR always takes effect immediately
        if candidate_state == StudyState.CAMERA_ERROR:
            self._recovery_start = None
            return StudyState.CAMERA_ERROR, trigger, conf, None

        # Camera error resolution for non-student states
        if current == StudyState.CAMERA_ERROR and signals.camera_valid and not signals.frame_frozen:
            if candidate_state in (StudyState.LOW_VISIBILITY, StudyState.MONITORING):
                return candidate_state, trigger, conf, "Camera recovered"

        # If currently in an alert state and clean studying is observed:
        # Enter RECOVERING state for a stability duration before confirming STUDYING
        is_clean_study = candidate_state in (
            StudyState.STUDYING,
            StudyState.STUDYING_READING,
            StudyState.STUDYING_WRITING,
        )

        if current in ALERT_STATES:
            if is_clean_study:
                if self._recovery_start is None:
                    self._recovery_start = now
                    self._recovering_from_state = current

                dur = now - self._recovery_start
                if dur >= config.RECOVERY_STABILITY_SECS:
                    # Successfully recovered!
                    recovered_from = self._recovering_from_state.name if self._recovering_from_state else "alert"
                    self._recovery_start = None
                    self._recovering_from_state = None
                    return candidate_state, f"Recovered from {recovered_from} ({dur:.1f}s clean)", 0.90, f"Clean activity resumed"
                else:
                    return StudyState.RECOVERING, f"Stabilizing study recovery ({dur:.1f}s / {config.RECOVERY_STABILITY_SECS}s)", 0.80, None
            else:
                # Still exhibiting alert condition or intermediate state
                self._recovery_start = None
                # Allow transition between alert states if candidate is higher/different alert
                if candidate_state in ALERT_STATES and candidate_state != current:
                    return candidate_state, trigger, conf, None
                return current, trigger, conf, None

        if current == StudyState.RECOVERING:
            if is_clean_study:
                dur = now - (self._recovery_start or now)
                if dur >= config.RECOVERY_STABILITY_SECS:
                    self._recovery_start = None
                    self._recovering_from_state = None
                    return candidate_state, "Recovery completed; studying active", 0.92, "Activity confirmed"
                return StudyState.RECOVERING, f"Stabilizing ({dur:.1f}s)", 0.82, None
            else:
                # Interrupted recovery
                self._recovery_start = None
                return candidate_state, trigger, conf, None

        # Normal transitions (from non-alert states)
        return candidate_state, trigger, conf, None
