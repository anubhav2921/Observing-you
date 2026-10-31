"""
behavior_types.py — Type definitions, enums, and data models for
Upper-Body Study Behavior Recognition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple


class BehaviorCategory(Enum):
    """Parent behavioral taxonomy categories required by monitoring policy."""
    PRODUCTIVE_STUDYING      = auto()
    DIGITAL_DISTRACTION      = auto()
    VISUAL_DISTRACTION       = auto()
    PHYSICAL_DISENGAGEMENT   = auto()
    DROWSINESS               = auto()
    PHYSICAL_DISTRACTION     = auto()
    SOCIAL_DISTRACTION       = auto()
    STUDY_AVOIDANCE          = auto()
    FACE_OCCLUSION           = auto()
    STUDENT_ABSENT           = auto()
    ACTIVITY_UNCONFIRMED     = auto()


class PhoneInteractionStatus(Enum):
    """Granular phone interaction state."""
    NONE                     = auto()
    PHONE_VISIBLE            = auto()  # Phone on desk, not touched
    PHONE_HELD               = auto()  # Hand near/overlapping phone
    PHONE_IN_USE             = auto()  # Hand holding phone + head/gaze directed toward it
    PHONE_CONFIRMED          = auto()  # Temporal confirmation window met (0.5–1.0s)


class BehaviorLabel(Enum):
    """Target behavior labels for upper-body study monitoring."""
    STUDYING_SCREEN            = auto()  # Student focused on computer screen
    STUDYING_READING_WRITING   = auto()  # Student reading book or writing on desk
    POSSIBLE_DISTRACTION       = auto()  # Phone off-task
    LOOKING_AWAY               = auto()  # Gaze turned away / repeated head turns
    INACTIVITY_WARNING         = auto()  # Prolonged inactivity / motionless / sitting idle
    OFF_TASK_CANDIDATE         = auto()  # Candidate off-task behavior awaiting confirmation
    ACTIVITY_UNCONFIRMED       = auto()  # Facing camera/screen with no observable study cues
    FACE_PARTIALLY_OCCLUDED    = auto()  # Face partly obscured (e.g. by book edge or hand)
    FACE_FULLY_OCCLUDED        = auto()  # Face completely hidden (deliberate concealment)
    POSSIBLE_DROWSINESS        = auto()  # Sustained eye closure or repeated head drooping
    STUDENT_ABSENT             = auto()  # No student present in upper-body camera view
    CAMERA_ERROR               = auto()  # Camera feed lost, invalid, or frozen
    LOW_VISIBILITY             = auto()  # Extreme underexposure or poor lighting
    RECOVERING                 = auto()  # Transition state stabilizing return to study


class HeadDirection(Enum):
    FACING_SCREEN   = auto()
    TILTED_DOWN     = auto()
    TILTED_UP       = auto()
    TURNED_LEFT     = auto()
    TURNED_RIGHT    = auto()
    TILTED_SIDEWAYS = auto()
    UNKNOWN         = auto()


class EyeState(Enum):
    EYES_OPEN   = auto()
    EYES_CLOSED = auto()
    BLINKING    = auto()
    UNKNOWN     = auto()


class ShoulderPosture(Enum):
    UPRIGHT          = auto()
    LEANING_FORWARD  = auto()
    LEANING_BACKWARD = auto()
    SHOULDERS_ROTATED = auto()
    SHOULDERS_TILTED = auto()
    UNKNOWN          = auto()


class HandActivity(Enum):
    HANDS_NOT_VISIBLE           = auto()
    HANDS_NEAR_LOWER_BORDER     = auto()  # At desk / keyboard / notebook
    HAND_AT_CHIN                = auto()  # Thinking / resting chin on hand
    HAND_AT_EYES                = auto()  # Rubbing eyes / tired gesture
    HAND_COVERING_FACE          = auto()  # Deliberate face obscuration
    HAND_HOLDING_PHONE          = auto()
    UNKNOWN                     = auto()


class ObjectState(Enum):
    NONE               = auto()
    BOOK_VISIBLE       = auto()
    BOOK_NEAR_TORSO    = auto()
    PHONE_NEAR_TORSO   = auto()
    LAPTOP_VISIBLE     = auto()


@dataclass
class ObservablePoseFeatures:
    """
    Observable independent visual features (Section D).
    These are visual signals, NOT definitive proof of intent.
    """
    head_facing_screen: bool = False
    head_tilted_down: bool = False
    head_tilted_up: bool = False
    head_turned_left_right: bool = False
    head_tilted_sideways: bool = False
    repeated_head_turns: bool = False
    repeated_head_drooping: bool = False
    face_resting_on_hand: bool = False
    face_covered_by_hand: bool = False
    face_covered_by_book_or_object: bool = False
    upright_upper_body: bool = False
    upper_body_leaning_forward_or_backward: bool = False
    shoulders_rotated: bool = False
    shoulders_tilted: bool = False
    hands_moving_near_lower_camera_boundary: bool = False
    hand_touching_chin_or_eyes: bool = False
    phone_held_near_upper_torso: bool = False
    phone_actively_used: bool = False
    brief_eye_closure: bool = False
    normal_blinking: bool = False
    sustained_eye_closure: bool = False
    upper_body_moving_out_of_frame: bool = False
    minimal_upper_body_movement: bool = False
    yawn_detected: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {
            "head_facing_screen": self.head_facing_screen,
            "head_tilted_down": self.head_tilted_down,
            "head_tilted_up": self.head_tilted_up,
            "head_turned_left_right": self.head_turned_left_right,
            "head_tilted_sideways": self.head_tilted_sideways,
            "repeated_head_turns": self.repeated_head_turns,
            "repeated_head_drooping": self.repeated_head_drooping,
            "face_resting_on_hand": self.face_resting_on_hand,
            "face_covered_by_hand": self.face_covered_by_hand,
            "face_covered_by_book_or_object": self.face_covered_by_book_or_object,
            "upright_upper_body": self.upright_upper_body,
            "leaning_forward_or_backward": self.upper_body_leaning_forward_or_backward,
            "shoulders_rotated": self.shoulders_rotated,
            "shoulders_tilted": self.shoulders_tilted,
            "hands_near_lower_boundary": self.hands_moving_near_lower_camera_boundary,
            "hand_touching_chin_or_eyes": self.hand_touching_chin_or_eyes,
            "phone_near_torso": self.phone_held_near_upper_torso,
            "brief_eye_closure": self.brief_eye_closure,
            "normal_blinking": self.normal_blinking,
            "sustained_eye_closure": self.sustained_eye_closure,
            "moving_out_of_frame": self.upper_body_moving_out_of_frame,
            "minimal_movement": self.minimal_upper_body_movement,
            "yawn_detected": self.yawn_detected,
        }


@dataclass
class Observation:
    """Individual independent behavioral signal with confidence, timestamp, and validity."""
    name: str
    value: Any
    confidence: float
    timestamp: float
    valid: bool
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": str(self.value) if not isinstance(self.value, (bool, int, float, str)) else self.value,
            "confidence": round(self.confidence, 3),
            "timestamp": round(self.timestamp, 3),
            "valid": self.valid,
            "details": self.details,
        }


@dataclass
class IndependentObservations:
    """
    Independent behavioral signals required by monitoring policy (Section 2).
    Maintains separate, decoupled observations with confidence and validity.
    """
    timestamp: float
    camera_health: Observation              # valid, frozen, low_vis, inference_err
    person_present: Observation             # True/False with YOLO conf
    face_present: Observation               # True/False with MediaPipe conf
    face_occluded: Observation              # True/False, IoU / cover evidence
    head_direction: Observation             # HeadDirection enum
    eye_state: Observation                  # EyeState enum + EAR
    book_detected: Observation              # True/False with box/conf
    phone_detected: Observation             # True/False with box/conf
    hand_near_face: Observation             # HandActivity / chin / eyes
    body_pose: Observation                  # ShoulderPosture + tilt
    observable_study_activity: Observation  # reading, writing, screen work, desk interaction
    off_task_evidence: Observation          # phone, looking away, room scanning, idle
    detection_confidence: Observation       # overall minimum/aggregate confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_health": self.camera_health.to_dict(),
            "person_present": self.person_present.to_dict(),
            "face_present": self.face_present.to_dict(),
            "face_occluded": self.face_occluded.to_dict(),
            "head_direction": self.head_direction.to_dict(),
            "eye_state": self.eye_state.to_dict(),
            "book_detected": self.book_detected.to_dict(),
            "phone_detected": self.phone_detected.to_dict(),
            "hand_near_face": self.hand_near_face.to_dict(),
            "body_pose": self.body_pose.to_dict(),
            "observable_study_activity": self.observable_study_activity.to_dict(),
            "off_task_evidence": self.off_task_evidence.to_dict(),
            "detection_confidence": self.detection_confidence.to_dict(),
        }


@dataclass
class UpperBodyFeatures:
    """
    Raw extracted signals from head, face, shoulders, chest, and hands.
    Represents missing observations as None (unknown), not negative evidence.
    """
    timestamp: float

    # Camera & Frame Quality
    camera_valid: bool = True
    frame_frozen: bool = False
    low_visibility: bool = False
    mean_intensity: float = 128.0

    # Upper-Body / Person Presence
    person_detected: bool = False
    person_conf: float = 0.0
    person_box: Optional[Tuple[int, int, int, int]] = None

    # Face & Landmarks
    face_detected: bool = False
    face_conf: float = 0.0
    face_box: Optional[Tuple[int, int, int, int]] = None
    landmark_visibility_ratio: float = 0.0  # Fraction of reliable landmarks (0.0 to 1.0)
    head_yaw: Optional[float] = None        # Degrees (- = left, + = right)
    head_pitch: Optional[float] = None      # Degrees (+ = down, - = up)
    head_roll: Optional[float] = None       # Degrees (tilt sideways)

    # Eyes & Gaze
    ear: Optional[float] = None             # Eye Aspect Ratio (None if occluded)
    left_ear: Optional[float] = None        # Left eye aspect ratio
    right_ear: Optional[float] = None       # Right eye aspect ratio
    blink_score: Optional[float] = None     # Blendshape blink probability (0.0=open, 1.0=shut)
    eye_closure_duration: float = 0.0       # Elapsed seconds of continuous closure
    drowsiness_evidence: str = "none"       # Description of validated drowsiness evidence
    landmark_validity: bool = True          # True when face landmarks are valid & unoccluded
    mar: Optional[float] = None             # Mouth Aspect Ratio (for yawning detection)
    yawn_detected: bool = False             # Instantaneous yawn candidate
    gaze_horizontal: Optional[float] = None # Normalized pupil position (-1 = left, 1 = right)
    gaze_vertical: Optional[float] = None   # Normalized pupil position (-1 = up, 1 = down)

    # Shoulders & Upper Torso (Camera Constraint: head, neck, shoulders, chest)
    shoulders_detected: bool = False
    left_shoulder: Optional[Tuple[float, float, float]] = None   # (x, y, z) normalized
    right_shoulder: Optional[Tuple[float, float, float]] = None  # (x, y, z) normalized
    shoulder_tilt_deg: Optional[float] = None                    # Angle of shoulder line
    shoulder_width_norm: Optional[float] = None                  # Distance between shoulders
    upper_body_motion: float = 0.0                               # Motion magnitude

    # Hands (Hands may be partially or completely out of frame)
    hands_visible_count: int = 0
    hands_near_lower_border: bool = False
    hand_to_face_iou: float = 0.0
    hand_near_chin: bool = False
    hand_near_eyes: bool = False

    # Detected Objects
    book_detected: bool = False
    book_box: Optional[Tuple[int, int, int, int]] = None
    phone_detected: bool = False
    phone_box: Optional[Tuple[int, int, int, int]] = None
    phone_interaction: PhoneInteractionStatus = PhoneInteractionStatus.NONE
    laptop_detected: bool = False

    # Independent Multi-Label Categoricals
    head_direction: HeadDirection = HeadDirection.UNKNOWN
    eye_state: EyeState = EyeState.UNKNOWN
    shoulder_posture: ShoulderPosture = ShoulderPosture.UNKNOWN
    hand_activity: HandActivity = HandActivity.UNKNOWN
    object_state: ObjectState = ObjectState.NONE

    # Observable Pose Features
    pose_features: ObservablePoseFeatures = field(default_factory=ObservablePoseFeatures)

    # Decoupled Observations & Error Flags
    observations: Optional[IndependentObservations] = None
    inference_error: bool = False


@dataclass
class UpperBodyDecision:
    """Authoritative decision output with multi-label behavior support."""
    primary_state: BehaviorLabel
    active_behaviors: Set[BehaviorLabel]
    confidence: float
    duration_in_primary: float
    trigger_condition: str
    features: UpperBodyFeatures
    pose_features: ObservablePoseFeatures
    behavior_category: BehaviorCategory = BehaviorCategory.PRODUCTIVE_STUDYING
    phone_status: PhoneInteractionStatus = PhoneInteractionStatus.NONE
    transitioned: bool = False
    prev_state: Optional[BehaviorLabel] = None
    recovery_reason: Optional[str] = None
    observations: Optional[IndependentObservations] = None
    diagnostic_reason: str = ""
    alert_eligible: bool = False
    alert_rejection_reason: Optional[str] = None
