"""
annotation_schema.py — Documented Annotation Schema & Multi-Session Dataset
for Upper-Body Study Behavior Recognition.

Implements the complete annotation schema (Section E) with positive and negative
examples for every target behavior, independent pose and object annotations,
visibility flags, confidence/ambiguity flags, and train/eval splits.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from behavior_types import (
    BehaviorLabel,
    EyeState,
    HandActivity,
    HeadDirection,
    ObjectState,
    ShoulderPosture,
)


@dataclass
class VisibilityFlags:
    """Visibility flags for upper-body anatomy under camera constraints."""
    face_visible: bool
    eyes_visible: bool
    shoulders_visible: bool
    hands_visible: bool
    chest_visible: bool


@dataclass
class IndependentPoseAnnotations:
    """Independent multi-label pose and object annotations."""
    head_direction: str          # Name of HeadDirection
    eye_state: str               # Name of EyeState
    shoulder_posture: str        # Name of ShoulderPosture
    hand_activity: str           # Name of HandActivity
    object_state: str            # Name of ObjectState
    observable_features: List[str]  # Active ObservablePoseFeatures


@dataclass
class StudyAnnotationRecord:
    """Single annotated clip or sequence interval."""
    annotation_id: str
    session_id: str
    subject_id: str
    split: str                   # "train" or "test" (strictly by session/subject)
    start_time_sec: float
    end_time_sec: float
    primary_behavior: str        # Name of BehaviorLabel
    multi_label_behaviors: List[str]
    visibility: VisibilityFlags
    pose_annotations: IndependentPoseAnnotations
    is_target_behavior: bool     # True if anomaly/alert target; False if normal study
    confidence: float            # 0.0 to 1.0
    ambiguity_flag: bool         # True if visual evidence is inherently ambiguous
    description: str


def get_standard_dataset_sessions() -> List[StudyAnnotationRecord]:
    """
    Generate documented benchmark annotation dataset covering all 13 required scenarios
    with positive and negative controls across 4 independent subjects/sessions.
    """
    records = []

    # ──────────────────────────────────────────────────────────────────
    # Subject 1 (Session 01) — Reading, Writing, and Screen Coding (Split: train)
    # ──────────────────────────────────────────────────────────────────
    records.append(
        StudyAnnotationRecord(
            annotation_id="S01_01_read_face_visible",
            session_id="session_01_reading_lab",
            subject_id="subject_A",
            split="train",
            start_time_sec=0.0,
            end_time_sec=10.0,
            primary_behavior=BehaviorLabel.STUDYING_READING_WRITING.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_READING_WRITING.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=True, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TILTED_DOWN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HANDS_NEAR_LOWER_BORDER.name,
                object_state=ObjectState.BOOK_VISIBLE.name,
                observable_features=["head_tilted_down", "upright_upper_body", "hands_moving_near_lower_camera_boundary"],
            ),
            is_target_behavior=False,
            confidence=0.95,
            ambiguity_flag=False,
            description="Reading physical textbook with face and book both clearly visible.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S01_02_read_face_partially_covered",
            session_id="session_01_reading_lab",
            subject_id="subject_A",
            split="train",
            start_time_sec=10.0,
            end_time_sec=20.0,
            primary_behavior=BehaviorLabel.STUDYING_READING_WRITING.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_READING_WRITING.name, BehaviorLabel.FACE_PARTIALLY_OCCLUDED.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=True, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TILTED_DOWN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.LEANING_FORWARD.name,
                hand_activity=HandActivity.HANDS_NEAR_LOWER_BORDER.name,
                object_state=ObjectState.BOOK_NEAR_TORSO.name,
                observable_features=["head_tilted_down", "upper_body_leaning_forward_or_backward", "face_covered_by_book_or_object"],
            ),
            is_target_behavior=False,
            confidence=0.90,
            ambiguity_flag=False,
            description="Reading while book partly obscures lower chin/mouth.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S01_03_write_notebook_downward_pitch",
            session_id="session_01_reading_lab",
            subject_id="subject_A",
            split="train",
            start_time_sec=20.0,
            end_time_sec=30.0,
            primary_behavior=BehaviorLabel.STUDYING_READING_WRITING.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_READING_WRITING.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=True, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TILTED_DOWN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.LEANING_FORWARD.name,
                hand_activity=HandActivity.HANDS_NEAR_LOWER_BORDER.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_tilted_down", "hands_moving_near_lower_camera_boundary"],
            ),
            is_target_behavior=False,
            confidence=0.92,
            ambiguity_flag=False,
            description="Writing in desk notebook with head tilted down and hands near lower boundary.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S01_04_coding_screen",
            session_id="session_01_reading_lab",
            subject_id="subject_A",
            split="train",
            start_time_sec=30.0,
            end_time_sec=40.0,
            primary_behavior=BehaviorLabel.STUDYING_SCREEN.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_SCREEN.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.FACING_SCREEN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.LAPTOP_VISIBLE.name,
                observable_features=["head_facing_screen", "upright_upper_body"],
            ),
            is_target_behavior=False,
            confidence=0.94,
            ambiguity_flag=False,
            description="Coding while looking directly at computer screen; hands outside camera frame.",
        )
    )

    # ──────────────────────────────────────────────────────────────────
    # Subject 2 (Session 02) — Thinking, Video, Camera Staring (Split: test)
    # ──────────────────────────────────────────────────────────────────
    records.append(
        StudyAnnotationRecord(
            annotation_id="S02_01_thinking_hand_on_chin",
            session_id="session_02_video_lecture",
            subject_id="subject_B",
            split="test",
            start_time_sec=0.0,
            end_time_sec=12.0,
            primary_behavior=BehaviorLabel.STUDYING_SCREEN.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_SCREEN.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=True, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.FACING_SCREEN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HAND_AT_CHIN.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_facing_screen", "face_resting_on_hand", "hand_touching_chin_or_eyes"],
            ),
            is_target_behavior=False,
            confidence=0.88,
            ambiguity_flag=False,
            description="Student thinking deeply with hand resting on chin/cheek while looking toward screen.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S02_02_watching_video_motionless",
            session_id="session_02_video_lecture",
            subject_id="subject_B",
            split="test",
            start_time_sec=12.0,
            end_time_sec=22.0,
            primary_behavior=BehaviorLabel.STUDYING_SCREEN.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_SCREEN.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.FACING_SCREEN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_facing_screen", "minimal_upper_body_movement"],
            ),
            is_target_behavior=False,
            confidence=0.82,
            ambiguity_flag=True,
            description="Watching an online lecture video with minimal upper body movement.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S02_03_camera_staring_inactivity",
            session_id="session_02_video_lecture",
            subject_id="subject_B",
            split="test",
            start_time_sec=22.0,
            end_time_sec=36.0,
            primary_behavior=BehaviorLabel.POSSIBLE_DISTRACTION.name,
            multi_label_behaviors=[BehaviorLabel.POSSIBLE_DISTRACTION.name, BehaviorLabel.ACTIVITY_UNCONFIRMED.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.FACING_SCREEN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_facing_screen", "minimal_upper_body_movement"],
            ),
            is_target_behavior=True,
            confidence=0.88,
            ambiguity_flag=False,
            description="Looking straight into webcam lens for 14 seconds without any study material or activity.",
        )
    )

    # ──────────────────────────────────────────────────────────────────
    # Subject 3 (Session 03) — Gaze Turns, Blinks vs Drowsiness, Phone (Split: test)
    # ──────────────────────────────────────────────────────────────────
    records.append(
        StudyAnnotationRecord(
            annotation_id="S03_01_brief_look_away",
            session_id="session_03_distraction_study",
            subject_id="subject_C",
            split="test",
            start_time_sec=0.0,
            end_time_sec=2.0,
            primary_behavior=BehaviorLabel.STUDYING_SCREEN.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_SCREEN.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TURNED_RIGHT.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_turned_left_right"],
            ),
            is_target_behavior=False,
            confidence=0.90,
            ambiguity_flag=False,
            description="Student briefly looks away for 1.5 seconds (under distraction threshold).",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S03_02_sustained_offtask_gaze",
            session_id="session_03_distraction_study",
            subject_id="subject_C",
            split="test",
            start_time_sec=2.0,
            end_time_sec=14.0,
            primary_behavior=BehaviorLabel.POSSIBLE_DISTRACTION.name,
            multi_label_behaviors=[BehaviorLabel.POSSIBLE_DISTRACTION.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TURNED_RIGHT.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.SHOULDERS_ROTATED.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_turned_left_right", "shoulders_rotated"],
            ),
            is_target_behavior=True,
            confidence=0.92,
            ambiguity_flag=False,
            description="Student turns head 40 degrees away for 12 seconds continuously.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S03_03_normal_blinking",
            session_id="session_03_distraction_study",
            subject_id="subject_C",
            split="test",
            start_time_sec=14.0,
            end_time_sec=20.0,
            primary_behavior=BehaviorLabel.STUDYING_SCREEN.name,
            multi_label_behaviors=[BehaviorLabel.STUDYING_SCREEN.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.FACING_SCREEN.name,
                eye_state=EyeState.BLINKING.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_facing_screen", "brief_eye_closure"],
            ),
            is_target_behavior=False,
            confidence=0.95,
            ambiguity_flag=False,
            description="Normal periodic blinking (200ms closures) during screen work; no sleep alert.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S03_04_prolonged_drowsiness",
            session_id="session_03_distraction_study",
            subject_id="subject_C",
            split="test",
            start_time_sec=20.0,
            end_time_sec=26.0,
            primary_behavior=BehaviorLabel.POSSIBLE_DROWSINESS.name,
            multi_label_behaviors=[BehaviorLabel.POSSIBLE_DROWSINESS.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=False, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TILTED_DOWN.name,
                eye_state=EyeState.EYES_CLOSED.name,
                shoulder_posture=ShoulderPosture.LEANING_FORWARD.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["head_tilted_down", "sustained_eye_closure", "repeated_head_drooping"],
            ),
            is_target_behavior=True,
            confidence=0.94,
            ambiguity_flag=False,
            description="Sustained eye closure (EAR < 0.15 for 2.2s) accompanied by head drooping.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S03_05_phone_distraction",
            session_id="session_03_distraction_study",
            subject_id="subject_C",
            split="test",
            start_time_sec=26.0,
            end_time_sec=34.0,
            primary_behavior=BehaviorLabel.POSSIBLE_DISTRACTION.name,
            multi_label_behaviors=[BehaviorLabel.POSSIBLE_DISTRACTION.name],
            visibility=VisibilityFlags(face_visible=True, eyes_visible=True, shoulders_visible=True, hands_visible=True, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.TILTED_DOWN.name,
                eye_state=EyeState.EYES_OPEN.name,
                shoulder_posture=ShoulderPosture.LEANING_FORWARD.name,
                hand_activity=HandActivity.HAND_HOLDING_PHONE.name,
                object_state=ObjectState.PHONE_NEAR_TORSO.name,
                observable_features=["head_tilted_down", "phone_held_near_upper_torso"],
            ),
            is_target_behavior=True,
            confidence=0.96,
            ambiguity_flag=False,
            description="Cell phone held in front of chest/torso while student interacts off-task.",
        )
    )

    # ──────────────────────────────────────────────────────────────────
    # Subject 4 (Session 04) — Occlusion, Absence, Camera Fault (Split: test)
    # ──────────────────────────────────────────────────────────────────
    records.append(
        StudyAnnotationRecord(
            annotation_id="S04_01_hand_face_concealment",
            session_id="session_04_camera_occlusion",
            subject_id="subject_D",
            split="test",
            start_time_sec=0.0,
            end_time_sec=6.0,
            primary_behavior=BehaviorLabel.FACE_FULLY_OCCLUDED.name,
            multi_label_behaviors=[BehaviorLabel.FACE_FULLY_OCCLUDED.name],
            visibility=VisibilityFlags(face_visible=False, eyes_visible=False, shoulders_visible=True, hands_visible=True, chest_visible=True),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.FACING_SCREEN.name,
                eye_state=EyeState.UNKNOWN.name,
                shoulder_posture=ShoulderPosture.UPRIGHT.name,
                hand_activity=HandActivity.HAND_COVERING_FACE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["face_covered_by_hand"],
            ),
            is_target_behavior=True,
            confidence=0.92,
            ambiguity_flag=False,
            description="Both hands deliberately raised to completely cover face for 4 seconds.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S04_02_student_absent",
            session_id="session_04_camera_occlusion",
            subject_id="subject_D",
            split="test",
            start_time_sec=6.0,
            end_time_sec=16.0,
            primary_behavior=BehaviorLabel.STUDENT_ABSENT.name,
            multi_label_behaviors=[BehaviorLabel.STUDENT_ABSENT.name],
            visibility=VisibilityFlags(face_visible=False, eyes_visible=False, shoulders_visible=False, hands_visible=False, chest_visible=False),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.UNKNOWN.name,
                eye_state=EyeState.UNKNOWN.name,
                shoulder_posture=ShoulderPosture.UNKNOWN.name,
                hand_activity=HandActivity.HANDS_NOT_VISIBLE.name,
                object_state=ObjectState.NONE.name,
                observable_features=["upper_body_moving_out_of_frame"],
            ),
            is_target_behavior=True,
            confidence=0.98,
            ambiguity_flag=False,
            description="Student leaves chair; upper body completely out of frame for 10 seconds.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S04_03_camera_frozen_fault",
            session_id="session_04_camera_occlusion",
            subject_id="subject_D",
            split="test",
            start_time_sec=16.0,
            end_time_sec=22.0,
            primary_behavior=BehaviorLabel.CAMERA_ERROR.name,
            multi_label_behaviors=[BehaviorLabel.CAMERA_ERROR.name],
            visibility=VisibilityFlags(face_visible=False, eyes_visible=False, shoulders_visible=False, hands_visible=False, chest_visible=False),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.UNKNOWN.name,
                eye_state=EyeState.UNKNOWN.name,
                shoulder_posture=ShoulderPosture.UNKNOWN.name,
                hand_activity=HandActivity.UNKNOWN.name,
                object_state=ObjectState.NONE.name,
                observable_features=[],
            ),
            is_target_behavior=True,
            confidence=0.99,
            ambiguity_flag=False,
            description="Camera frame corrupted/frozen for 6 seconds; technical fault.",
        )
    )

    records.append(
        StudyAnnotationRecord(
            annotation_id="S04_04_low_visibility_lighting",
            session_id="session_04_camera_occlusion",
            subject_id="subject_D",
            split="test",
            start_time_sec=22.0,
            end_time_sec=30.0,
            primary_behavior=BehaviorLabel.LOW_VISIBILITY.name,
            multi_label_behaviors=[BehaviorLabel.LOW_VISIBILITY.name],
            visibility=VisibilityFlags(face_visible=False, eyes_visible=False, shoulders_visible=False, hands_visible=False, chest_visible=False),
            pose_annotations=IndependentPoseAnnotations(
                head_direction=HeadDirection.UNKNOWN.name,
                eye_state=EyeState.UNKNOWN.name,
                shoulder_posture=ShoulderPosture.UNKNOWN.name,
                hand_activity=HandActivity.UNKNOWN.name,
                object_state=ObjectState.NONE.name,
                observable_features=[],
            ),
            is_target_behavior=True,
            confidence=0.95,
            ambiguity_flag=False,
            description="Room lights switched off; mean frame intensity drops below 15.0.",
        )
    )

    return records


def export_annotation_schema_json(output_path: str = "dataset_schema.json") -> None:
    """Save documented dataset records to JSON file."""
    records = get_standard_dataset_sessions()
    data = [asdict(r) for r in records]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[Dataset Schema] Exported {len(records)} documented annotation records to {output_path}")


if __name__ == "__main__":
    export_annotation_schema_json()
