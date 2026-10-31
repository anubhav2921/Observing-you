"""
temporal_decision_engine.py — Temporal Decision Engine for Upper-Body Study Monitoring.
Maintains independent duration timers, multi-label behavior sets, hysteresis,
confidence scoring, and selects the authoritative primary state.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

import backend.app.core.config as config
from backend.app.services.behavior.behavior_types import (
    BehaviorCategory,
    BehaviorLabel,
    EyeState,
    HandActivity,
    HeadDirection,
    ObservablePoseFeatures,
    PhoneInteractionStatus,
    ShoulderPosture,
    UpperBodyDecision,
    UpperBodyFeatures,
)
from backend.app.core.logging import StructuredLogger


# Warning states that require clean recovery stability before returning to study
ALERT_BEHAVIORS: Set[BehaviorLabel] = {
    BehaviorLabel.POSSIBLE_DISTRACTION,
    BehaviorLabel.LOOKING_AWAY,
    BehaviorLabel.INACTIVITY_WARNING,
    BehaviorLabel.OFF_TASK_CANDIDATE,
    BehaviorLabel.FACE_FULLY_OCCLUDED,
    BehaviorLabel.POSSIBLE_DROWSINESS,
    BehaviorLabel.STUDENT_ABSENT,
    BehaviorLabel.CAMERA_ERROR,
}


class TemporalDecisionEngine:
    """
    Authoritative temporal decision engine.
    Computes active multi-label behaviors and arbitrates the single authoritative state
    using elapsed-duration timers and hysteresis.
    """

    def __init__(self, logger: Optional[StructuredLogger] = None) -> None:
        self.logger = logger
        self.primary_state: BehaviorLabel = BehaviorLabel.ACTIVITY_UNCONFIRMED
        self.active_behaviors: Set[BehaviorLabel] = {BehaviorLabel.ACTIVITY_UNCONFIRMED}
        self.state_enter_time: Optional[float] = None

        # Independent duration accumulator timers (start timestamps in monotonic seconds)
        self._absence_start: Optional[float] = None
        self._occlusion_start: Optional[float] = None
        self._eye_closed_start: Optional[float] = None
        self._droop_start: Optional[float] = None
        self._head_down_start: Optional[float] = None
        self._phone_start: Optional[float] = None
        self._gaze_away_start: Optional[float] = None
        self._repeated_turns_start: Optional[float] = None
        self._camera_staring_start: Optional[float] = None
        self._inactivity_start: Optional[float] = None
        self._camera_error_start: Optional[float] = None
        self._recovery_start: Optional[float] = None

        self._recovering_from_state: Optional[BehaviorLabel] = None

        # Rolling history for smoothing candidate states (0.5s window)
        self._history: deque[Tuple[float, BehaviorLabel]] = deque()
        self._max_history_sec = config.SMOOTHING_WINDOW_SECS

        # Diagnostics
        self.last_confidence: float = 1.0

    def reset(self) -> None:
        """Reset all temporal accumulators, hysteresis buffers, and active states."""
        self.primary_state = BehaviorLabel.ACTIVITY_UNCONFIRMED
        self.active_behaviors = {BehaviorLabel.ACTIVITY_UNCONFIRMED}
        self.state_enter_time = None
        self._absence_start = None
        self._occlusion_start = None
        self._eye_closed_start = None
        self._droop_start = None
        self._head_down_start = None
        self._phone_start = None
        self._gaze_away_start = None
        self._repeated_turns_start = None
        self._camera_staring_start = None
        self._inactivity_start = None
        self._camera_error_start = None
        self._recovery_start = None
        self._recovering_from_state = None
        self._history.clear()
        self.last_confidence = 1.0

    # ──────────────────────────────────────────────────────────────────
    def update(self, f: UpperBodyFeatures) -> UpperBodyDecision:
        """
        Process upper-body features and return multi-label set + authoritative primary state.
        """
        now = f.timestamp
        if self.state_enter_time is None:
            self.state_enter_time = now

        # Clean rolling history
        cutoff = now - self._max_history_sec
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

        # Step 1: Compute independent multi-label behaviors
        active_set = self._compute_multi_label_behaviors(f, now)

        # Step 2: Determine instantaneous candidate primary state from timers
        candidate_primary, trigger, conf = self._evaluate_primary_candidate(f, active_set, now)
        self._history.append((now, candidate_primary))

        # Step 3: Rolling consensus smoothing (alert states adopt directly to avoid lag)
        smoothed_primary = candidate_primary if candidate_primary in ALERT_BEHAVIORS else self._compute_consensus(candidate_primary)

        # Step 4: Enforce transition hysteresis and recovery stability
        new_primary, transition_trigger, final_conf, rec_reason = self._handle_transitions(
            smoothed_primary, trigger, conf, f, now
        )

        alert_eligible = (new_primary in ALERT_BEHAVIORS)
        alert_rejection_reason = None
        if not alert_eligible:
            if candidate_primary in ALERT_BEHAVIORS:
                alert_rejection_reason = f"Candidate '{candidate_primary.name}' awaiting duration threshold or consensus"
            elif self.primary_state in ALERT_BEHAVIORS:
                alert_rejection_reason = f"Recovering from active alert '{self.primary_state.name}'"
            else:
                alert_rejection_reason = "Clean study activity"

        diagnostic_reason = f"State: {new_primary.name} ({final_conf:.2f}) | {transition_trigger}"

        transitioned = False
        prev_primary = self.primary_state

        is_submode_switch = (
            prev_primary in (BehaviorLabel.STUDYING_SCREEN, BehaviorLabel.STUDYING_READING_WRITING)
            and new_primary in (BehaviorLabel.STUDYING_SCREEN, BehaviorLabel.STUDYING_READING_WRITING)
        )

        if new_primary != self.primary_state:
            dur_in_prev = now - self.state_enter_time
            self.primary_state = new_primary
            self.last_confidence = final_conf

            if not is_submode_switch:
                transitioned = True
                self.state_enter_time = now

                if self.logger:
                    self.logger.log_transition(
                        prev_state=prev_primary.name,
                        new_state=new_primary.name,
                        trigger_condition=transition_trigger,
                        confidence=final_conf,
                        elapsed_duration=dur_in_prev,
                        detector_outputs={
                            "cam_ok": f.camera_valid,
                            "person": f.person_detected,
                            "face": f.face_detected,
                            "ear": f.ear,
                            "yaw": f.head_yaw,
                            "pitch": f.head_pitch,
                            "shoulders": f.shoulders_detected,
                            "phone": f.phone_detected,
                            "book": f.book_detected,
                            "motion": f.upper_body_motion,
                            "multi_labels": [b.name for b in active_set],
                        },
                        audio_event=new_primary.name if new_primary in ALERT_BEHAVIORS else "none",
                        recovery_reason=rec_reason,
                    )

        state_duration = now - self.state_enter_time
        self.active_behaviors = active_set

        # Map to Parent Behavioral Category (Section 2 Taxonomy)
        category = BehaviorCategory.PRODUCTIVE_STUDYING
        if self.primary_state in (BehaviorLabel.STUDYING_SCREEN, BehaviorLabel.STUDYING_READING_WRITING):
            category = BehaviorCategory.PRODUCTIVE_STUDYING
        elif self.primary_state == BehaviorLabel.POSSIBLE_DISTRACTION:
            category = BehaviorCategory.DIGITAL_DISTRACTION if f.phone_detected else BehaviorCategory.VISUAL_DISTRACTION
        elif self.primary_state == BehaviorLabel.LOOKING_AWAY:
            category = BehaviorCategory.VISUAL_DISTRACTION
        elif self.primary_state == BehaviorLabel.INACTIVITY_WARNING:
            category = BehaviorCategory.PHYSICAL_DISENGAGEMENT
        elif self.primary_state == BehaviorLabel.POSSIBLE_DROWSINESS:
            category = BehaviorCategory.DROWSINESS
        elif self.primary_state in (BehaviorLabel.FACE_FULLY_OCCLUDED, BehaviorLabel.FACE_PARTIALLY_OCCLUDED):
            category = BehaviorCategory.FACE_OCCLUSION
        elif self.primary_state == BehaviorLabel.STUDENT_ABSENT:
            category = BehaviorCategory.STUDENT_ABSENT
        elif self.primary_state == BehaviorLabel.ACTIVITY_UNCONFIRMED:
            category = BehaviorCategory.ACTIVITY_UNCONFIRMED

        phone_st = f.phone_interaction
        if phone_st in (PhoneInteractionStatus.PHONE_IN_USE, PhoneInteractionStatus.PHONE_HELD):
            if (now - (self._phone_start or now)) >= getattr(config, "PHONE_ACTIVE_USAGE_SECS", 0.8):
                phone_st = PhoneInteractionStatus.PHONE_CONFIRMED

        return UpperBodyDecision(
            primary_state=self.primary_state,
            active_behaviors=self.active_behaviors,
            confidence=final_conf,
            duration_in_primary=state_duration,
            trigger_condition=transition_trigger,
            features=f,
            pose_features=f.pose_features,
            behavior_category=category,
            phone_status=phone_st,
            transitioned=transitioned,
            prev_state=prev_primary if transitioned else None,
            recovery_reason=rec_reason,
            observations=f.observations,
            diagnostic_reason=diagnostic_reason,
            alert_eligible=alert_eligible,
            alert_rejection_reason=alert_rejection_reason,
        )

    # ──────────────────────────────────────────────────────────────────
    def _compute_multi_label_behaviors(self, f: UpperBodyFeatures, now: float) -> Set[BehaviorLabel]:
        """
        Multi-label classification: returns all active behaviors simultaneously.
        Does NOT force mutually compatible behaviors into an exclusive class.
        """
        active: Set[BehaviorLabel] = set()

        if not f.camera_valid or f.frame_frozen:
            active.add(BehaviorLabel.CAMERA_ERROR)
            return active

        if f.low_visibility:
            active.add(BehaviorLabel.LOW_VISIBILITY)

        if not f.person_detected and not f.shoulders_detected:
            active.add(BehaviorLabel.STUDENT_ABSENT)
            return active

        # Student is present:
        # Check Occlusion: Partial vs Full
        if not f.face_detected:
            if (
                f.pose_features.face_covered_by_hand
                or f.hand_to_face_iou > 0.35
                or (self._occlusion_start is not None and (now - self._occlusion_start) >= config.FACE_OCCLUDED_SECS)
            ):
                active.add(BehaviorLabel.FACE_FULLY_OCCLUDED)
            elif f.book_detected:
                active.add(BehaviorLabel.FACE_PARTIALLY_OCCLUDED)
                active.add(BehaviorLabel.STUDYING_READING_WRITING)
            else:
                active.add(BehaviorLabel.FACE_PARTIALLY_OCCLUDED)
        else:
            if f.hand_to_face_iou > 0.35:
                active.add(BehaviorLabel.FACE_PARTIALLY_OCCLUDED)

        # Check Drowsiness cues (strictly exclude normal blinks and unvalidated face data)
        is_eyes_closed = (
            (f.eye_state == EyeState.EYES_CLOSED)
            or (f.ear is not None and f.ear < config.EAR_CLOSE_THRESHOLD and f.eye_state != EyeState.UNKNOWN)
        )
        drowsiness_valid = (
            (f.face_detected and getattr(f, "landmark_validity", True) and not getattr(f.pose_features, "normal_blinking", False))
            or (self._head_down_start is not None and (now - self._head_down_start) >= config.DROWSINESS_SUSTAINED_SECS)
        )
        if drowsiness_valid and (
            f.pose_features.sustained_eye_closure
            or (is_eyes_closed and self._eye_closed_start is not None and (now - self._eye_closed_start) >= config.DROWSINESS_SUSTAINED_SECS)
            or (f.pose_features.repeated_head_drooping and (f.ear is not None and f.ear < config.BORDERLINE_EAR_THRESHOLD))
            or (self._head_down_start is not None and (now - self._head_down_start) >= config.DROWSINESS_SUSTAINED_SECS)
        ):
            active.add(BehaviorLabel.POSSIBLE_DROWSINESS)

        # Check Distraction cues (Phone or sustained gaze turn)
        if f.phone_detected or f.pose_features.phone_held_near_upper_torso:
            active.add(BehaviorLabel.POSSIBLE_DISTRACTION)

        if f.head_direction in (HeadDirection.TURNED_LEFT, HeadDirection.TURNED_RIGHT) or f.pose_features.repeated_head_turns:
            active.add(BehaviorLabel.LOOKING_AWAY)
            active.add(BehaviorLabel.POSSIBLE_DISTRACTION)

        # Check Inactivity / Idle cues
        no_study_materials = (not f.book_detected) and (not f.laptop_detected) and (not f.hands_near_lower_border)
        is_inactive = no_study_materials and (
            f.shoulder_posture == ShoulderPosture.LEANING_BACKWARD
            or (f.head_direction == HeadDirection.FACING_SCREEN and f.pose_features.minimal_upper_body_movement and not f.pose_features.face_resting_on_hand)
        )
        if is_inactive:
            active.add(BehaviorLabel.INACTIVITY_WARNING)
            active.add(BehaviorLabel.ACTIVITY_UNCONFIRMED)

        # Check Study Behaviors
        # Screen studying
        if f.head_direction == HeadDirection.FACING_SCREEN and not f.book_detected and f.eye_state == EyeState.EYES_OPEN:
            active.add(BehaviorLabel.STUDYING_SCREEN)

        # Reading / Writing (book, downward pitch, desk hand activity)
        is_reading_writing = (
            f.book_detected
            or f.laptop_detected
            or (f.head_pitch is not None and config.READING_PITCH_MIN_DEG <= f.head_pitch <= config.READING_PITCH_MAX_DEG)
            or f.hands_near_lower_border
        )
        if is_reading_writing:
            active.add(BehaviorLabel.STUDYING_READING_WRITING)

        # Activity unconfirmed: looking at camera/screen without study materials or motion
        if f.head_direction == HeadDirection.FACING_SCREEN and not is_reading_writing and f.pose_features.minimal_upper_body_movement:
            active.add(BehaviorLabel.ACTIVITY_UNCONFIRMED)

        if not active:
            active.add(BehaviorLabel.STUDYING_SCREEN)

        return active

    # ──────────────────────────────────────────────────────────────────
    def _evaluate_primary_candidate(
        self, f: UpperBodyFeatures, active_set: Set[BehaviorLabel], now: float
    ) -> Tuple[BehaviorLabel, str, float]:
        """
        Select candidate primary state for audio priority and state machine logging.
        Applies temporal duration timers.
        """
        # 1. Technical camera faults & Model inference failures
        if not f.camera_valid or f.frame_frozen or getattr(f, "inference_error", False):
            if self._camera_error_start is None:
                self._camera_error_start = now
            return BehaviorLabel.CAMERA_ERROR, "Camera feed interrupted, frozen, or model inference error", 0.98
        self._camera_error_start = None

        # 2. Low visibility (Check before absence: darkness prevents person detection)
        if f.low_visibility:
            return BehaviorLabel.LOW_VISIBILITY, "Scene illumination too dark", 0.90

        # 3. Student absence (no person / shoulders in view)
        if not f.person_detected and not f.shoulders_detected:
            if self._absence_start is None:
                self._absence_start = now
            dur = now - self._absence_start
            if dur >= config.STUDENT_ABSENT_SECS:
                return BehaviorLabel.STUDENT_ABSENT, f"Student absent for {dur:.1f}s", 0.95
            return BehaviorLabel.ACTIVITY_UNCONFIRMED, f"Absent ({dur:.1f}s / {config.STUDENT_ABSENT_SECS}s)", 0.60
        self._absence_start = None

        # 4. Digital Distraction: Dedicated Phone Interaction Policy (Section 4)
        # Distinguish: PHONE_VISIBLE vs PHONE_HELD vs PHONE_IN_USE vs CONFIRMED
        phone_active = getattr(f.pose_features, "phone_actively_used", False) or f.phone_interaction in (
            PhoneInteractionStatus.PHONE_IN_USE, PhoneInteractionStatus.PHONE_HELD
        )

        if phone_active:
            if self._phone_start is None:
                self._phone_start = now
            dur = now - self._phone_start
            required_dur = getattr(config, "PHONE_ACTIVE_USAGE_SECS", 0.8)
            if dur >= required_dur:
                return BehaviorLabel.POSSIBLE_DISTRACTION, f"Active cell phone usage confirmed for {dur:.1f}s", 0.96
        elif f.phone_detected or f.pose_features.phone_held_near_upper_torso:
            # Phone merely visible / on desk without active handling
            if self._phone_start is None:
                self._phone_start = now
            dur = now - self._phone_start
            required_dur = getattr(config, "PHONE_VISIBLE_SECS", 3.0)
            if dur >= required_dur:
                return BehaviorLabel.POSSIBLE_DISTRACTION, f"Cell phone detected in vicinity for {dur:.1f}s", 0.88
        else:
            self._phone_start = None

        # 5. Face Concealment vs Reading vs Head Down on Desk
        if not f.face_detected:
            is_reading = (
                f.book_detected
                or (f.head_pitch is not None and config.READING_PITCH_MIN_DEG <= f.head_pitch <= config.READING_PITCH_MAX_DEG)
            )
            if is_reading:
                self._occlusion_start = None
                self._head_down_start = None
                return BehaviorLabel.STUDYING_READING_WRITING, "Reading book/notes (face landmarks obscured)", 0.90

            # Hands covering face / deliberate concealment takes precedence over indeterminate head posture
            is_face_covered = (
                f.pose_features.face_covered_by_hand
                or f.hand_to_face_iou > 0.30
                or f.hand_activity == HandActivity.HAND_COVERING_FACE
            )

            if is_face_covered:
                self._head_down_start = None
                if self._occlusion_start is None:
                    self._occlusion_start = now
                dur = now - self._occlusion_start
                if dur >= config.FACE_OCCLUDED_SECS:
                    return BehaviorLabel.FACE_FULLY_OCCLUDED, f"Face covered by hands for {dur:.1f}s", 0.92
                return BehaviorLabel.FACE_PARTIALLY_OCCLUDED, f"Face covered by hands ({dur:.1f}s / {config.FACE_OCCLUDED_SECS:.1f}s)", 0.70

            # Check if student head is genuinely down on desk (verified forward lean posture, no hands covering face)
            head_down_posture = (
                f.shoulders_detected
                and f.shoulder_posture == ShoulderPosture.LEANING_FORWARD
                and f.upper_body_motion < 0.010
                and not f.book_detected
            )
            if head_down_posture:
                if self._head_down_start is None:
                    self._head_down_start = now
                dur_hd = now - self._head_down_start
                if dur_hd >= (config.DROWSINESS_SUSTAINED_SECS + 1.0):
                    return BehaviorLabel.POSSIBLE_DROWSINESS, f"Head down on desk for {dur_hd:.1f}s", 0.88
            else:
                self._head_down_start = None

            # General face absence/concealment
            if self._occlusion_start is None:
                self._occlusion_start = now
            dur = now - self._occlusion_start
            if dur >= config.FACE_OCCLUDED_SECS:
                return BehaviorLabel.FACE_FULLY_OCCLUDED, f"Face concealed / hidden for {dur:.1f}s", 0.90
            return BehaviorLabel.FACE_PARTIALLY_OCCLUDED, f"Face hidden/obscured ({dur:.1f}s / {config.FACE_OCCLUDED_SECS:.1f}s)", 0.70
        else:
            self._occlusion_start = None
            self._head_down_start = None

        # 6. Drowsiness (sustained validated eye closure, repeated drooping, fatigue indicators)
        # Rule: missing/invalid landmarks, normal blinks, or downward reading must NOT trigger drowsiness
        landmarks_valid = f.face_detected and getattr(f, "landmark_validity", True)
        is_normal_blink = getattr(f.pose_features, "normal_blinking", False) or getattr(f.pose_features, "brief_eye_closure", False)

        is_eyes_closed = (
            (f.eye_state == EyeState.EYES_CLOSED)
            or (f.ear is not None and f.ear < config.EAR_CLOSE_THRESHOLD and f.eye_state != EyeState.UNKNOWN)
        )

        if not landmarks_valid or is_normal_blink:
            self._eye_closed_start = None
        elif is_eyes_closed:
            # Context compensation: looking down typing or reading foreshortens eyelids
            is_looking_down_studying = (
                f.head_pitch is not None and f.head_pitch > 10.0
                and (f.hands_near_lower_border or f.book_detected or f.laptop_detected)
            )
            if is_looking_down_studying and not f.pose_features.sustained_eye_closure:
                self._eye_closed_start = None
            else:
                if self._eye_closed_start is None:
                    self._eye_closed_start = now
                dur = now - self._eye_closed_start
                if dur >= config.DROWSINESS_SUSTAINED_SECS or f.pose_features.sustained_eye_closure:
                    ear_val = f.ear if f.ear is not None else 0.0
                    return BehaviorLabel.POSSIBLE_DROWSINESS, f"Eyes closed for {dur:.1f}s (EAR: {ear_val:.2f})", 0.94
        else:
            self._eye_closed_start = None

        if landmarks_valid and f.pose_features.repeated_head_drooping and (f.ear is not None and f.ear < config.BORDERLINE_EAR_THRESHOLD):
            if self._droop_start is None:
                self._droop_start = now
            dur = now - self._droop_start
            if dur >= config.DROOP_SUSTAINED_SECS:
                return BehaviorLabel.POSSIBLE_DROWSINESS, f"Repeated head drooping for {dur:.1f}s", 0.88
        else:
            self._droop_start = None

        if landmarks_valid and f.hand_near_eyes and (f.pose_features.repeated_head_drooping or (f.ear is not None and f.ear < config.BORDERLINE_EAR_THRESHOLD)):
            return BehaviorLabel.POSSIBLE_DROWSINESS, "Fatigue indicators: eye rubbing and drooping", 0.85

        # 7. Looking away & Repeated room scanning
        if f.pose_features.repeated_head_turns:
            if self._repeated_turns_start is None:
                self._repeated_turns_start = now
            dur_rt = now - self._repeated_turns_start
            if dur_rt >= 3.0:
                return BehaviorLabel.POSSIBLE_DISTRACTION, f"Looking around room repeatedly for {dur_rt:.1f}s", 0.88
        else:
            self._repeated_turns_start = None

        if f.head_direction in (HeadDirection.TURNED_LEFT, HeadDirection.TURNED_RIGHT):
            if self._gaze_away_start is None:
                self._gaze_away_start = now
            dur = now - self._gaze_away_start
            if dur >= config.LOOKING_AWAY_SECS:
                return BehaviorLabel.POSSIBLE_DISTRACTION, f"Gaze turned away for {dur:.1f}s", 0.90
        else:
            self._gaze_away_start = None

        # 8. Inactivity & Camera-Staring (Section 3 A):
        # Sitting idle, camera staring, or leaning back without study materials
        no_study_materials = (not f.book_detected) and (not f.laptop_detected) and (not f.hands_near_lower_border)
        is_camera_staring = (
            f.head_direction == HeadDirection.FACING_SCREEN
            and f.pose_features.minimal_upper_body_movement
            and not f.pose_features.face_resting_on_hand
        )
        is_leaning_back_idle = (
            f.shoulder_posture == ShoulderPosture.LEANING_BACKWARD
            and f.pose_features.minimal_upper_body_movement
        )

        if no_study_materials and (is_camera_staring or is_leaning_back_idle):
            if self._inactivity_start is None:
                self._inactivity_start = now
            dur = now - self._inactivity_start
            if dur >= config.INACTIVITY_WARNING_SECS:
                return BehaviorLabel.POSSIBLE_DISTRACTION, f"Sustained inactivity / idle for {dur:.1f}s", 0.88
            elif dur >= config.CAMERA_STARING_UNCONFIRMED_SECS:
                return BehaviorLabel.ACTIVITY_UNCONFIRMED, f"Sitting idle without study activity ({dur:.1f}s)", 0.72
        else:
            self._inactivity_start = None

        # 9. Active Study Classification
        if BehaviorLabel.STUDYING_READING_WRITING in active_set:
            return BehaviorLabel.STUDYING_READING_WRITING, "Reading book/desk notes or writing", 0.93

        return BehaviorLabel.STUDYING_SCREEN, "Attentive studying at screen", 0.92

    # ──────────────────────────────────────────────────────────────────
    def _compute_consensus(self, latest: BehaviorLabel) -> BehaviorLabel:
        """Rolling window majority vote."""
        if not self._history:
            return latest

        counts: Dict[BehaviorLabel, int] = {}
        for _, st in self._history:
            counts[st] = counts.get(st, 0) + 1

        best_state, count = max(counts.items(), key=lambda item: item[1])
        if (count / len(self._history)) >= config.MIN_STATE_CONSENSUS_RATIO:
            return best_state
        return self.primary_state

    # ──────────────────────────────────────────────────────────────────
    def _handle_transitions(
        self,
        candidate: BehaviorLabel,
        trigger: str,
        conf: float,
        f: UpperBodyFeatures,
        now: float,
    ) -> Tuple[BehaviorLabel, str, float, Optional[str]]:
        """Hysteresis and recovery stabilization."""
        current = self.primary_state

        if candidate == BehaviorLabel.CAMERA_ERROR:
            self._recovery_start = None
            return BehaviorLabel.CAMERA_ERROR, trigger, conf, None

        if current == BehaviorLabel.CAMERA_ERROR and f.camera_valid and not f.frame_frozen:
            return candidate, trigger, conf, "Camera recovered"

        if candidate == BehaviorLabel.LOW_VISIBILITY:
            self._recovery_start = None
            return BehaviorLabel.LOW_VISIBILITY, trigger, conf, None

        if current == BehaviorLabel.FACE_FULLY_OCCLUDED and not f.person_detected and not f.shoulders_detected:
            self._recovery_start = None
            return candidate, trigger, conf, "Student left chair"

        is_clean_study = candidate in (
            BehaviorLabel.STUDYING_SCREEN,
            BehaviorLabel.STUDYING_READING_WRITING,
        )

        def _get_recovery_requirements(alert_st: Optional[BehaviorLabel]) -> Tuple[float, bool]:
            """Return (required_seconds, is_condition_satisfied) for specific alert category."""
            base_rec = config.RECOVERY_STABILITY_SECS
            if alert_st == BehaviorLabel.POSSIBLE_DROWSINESS:
                req_sec = max(base_rec, getattr(config, "RECOVERY_DROWSINESS_SECS", 2.0))
                # Must have confirmed open eyes and no repeated head droops
                cond_ok = (is_clean_study and f.eye_state != EyeState.EYES_CLOSED and not f.pose_features.repeated_head_drooping)
                return req_sec, cond_ok
            elif alert_st in (BehaviorLabel.POSSIBLE_DISTRACTION, BehaviorLabel.LOOKING_AWAY):
                req_sec = base_rec
                cond_ok = (is_clean_study and not f.phone_detected and not f.pose_features.repeated_head_turns)
                return req_sec, cond_ok
            elif alert_st == BehaviorLabel.FACE_FULLY_OCCLUDED:
                req_sec = base_rec
                cond_ok = (is_clean_study and f.face_detected)
                return req_sec, cond_ok
            elif alert_st == BehaviorLabel.STUDENT_ABSENT:
                req_sec = base_rec
                cond_ok = (is_clean_study and (f.person_detected or f.shoulders_detected))
                return req_sec, cond_ok
            return base_rec, is_clean_study

        if current in ALERT_BEHAVIORS:
            req_dur, cond_met = _get_recovery_requirements(current)
            if cond_met:
                if self._recovery_start is None:
                    self._recovery_start = now
                    self._recovering_from_state = current

                dur = now - self._recovery_start
                if dur >= req_dur:
                    rec_from = self._recovering_from_state.name if self._recovering_from_state else "alert"
                    self._recovery_start = None
                    self._recovering_from_state = None
                    return candidate, f"Recovered from {rec_from} ({dur:.1f}s clean)", 0.92, "Clean study resumed"
                return BehaviorLabel.RECOVERING, f"Stabilizing recovery ({dur:.1f}s / {req_dur:.1f}s)", 0.82, None
            else:
                self._recovery_start = None
                if candidate in ALERT_BEHAVIORS and candidate != current:
                    return candidate, trigger, conf, None
                return current, trigger, conf, None

        if current == BehaviorLabel.RECOVERING:
            req_dur, cond_met = _get_recovery_requirements(self._recovering_from_state)
            if cond_met:
                dur = now - (self._recovery_start or now)
                if dur >= req_dur:
                    self._recovery_start = None
                    self._recovering_from_state = None
                    return candidate, "Recovery completed; studying active", 0.92, "Activity confirmed"
                return BehaviorLabel.RECOVERING, f"Stabilizing ({dur:.1f}s / {req_dur:.1f}s)", 0.82, None
            else:
                self._recovery_start = None
                return candidate, trigger, conf, None

        return candidate, trigger, conf, None
