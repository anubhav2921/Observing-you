"""
upper_body_detector.py — Multi-Label Feature Extraction Pipeline.
Extracts facial landmarks, solvePnP head pose, eye state/gaze, shoulder posture,
hand interactions, object context, and temporal signal dynamics under upper-body
camera constraints (head, face, shoulders, chest, upper arms).
"""

from __future__ import annotations

import math
import os
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.core import base_options as mp_base
    _MP_OK = True
except ImportError:
    _MP_OK = False

import backend.app.core.config as config
from backend.app.services.behavior.behavior_types import (
    EyeState,
    HandActivity,
    HeadDirection,
    IndependentObservations,
    ObjectState,
    ObservablePoseFeatures,
    Observation,
    PhoneInteractionStatus,
    ShoulderPosture,
    UpperBodyFeatures,
)


# Canonical 3D facial points for solvePnP head-pose
_POSE_IDX = [1, 152, 33, 263, 61, 291]
_MODEL_PTS = np.array([
    [  0.0,    0.0,    0.0],   # nose tip
    [  0.0, -330.0,  -65.0],   # chin
    [-225.0, 170.0, -135.0],   # left eye corner
    [ 225.0, 170.0, -135.0],   # right eye corner
    [-150.0,-150.0, -125.0],   # left mouth corner
    [ 150.0,-150.0, -125.0],   # right mouth corner
], dtype=np.float64)

_LEFT_EYE  = [33, 160, 158, 133, 153, 144]
_RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)


def _compute_ear(landmarks, indices: List[int], w: int, h: int) -> float:
    pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in indices]
    a = _dist(pts[1], pts[5])
    b = _dist(pts[2], pts[4])
    c = _dist(pts[0], pts[3])
    return (a + b) / (2.0 * c + 1e-6)


def _compute_box_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = max(1, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(1, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    return interArea / float(boxAArea + boxBArea - interArea)


class UpperBodyDetector:
    """
    Multi-modal detector tailored for upper-body framing.
    Integrates MediaPipe FaceLandmarker, PoseLandmarker (Lite), HandLandmarker,
    and YOLOv8 detections.
    """

    def __init__(self) -> None:
        self._face_landmarker = None
        self._pose_landmarker = None
        self._hand_landmarker = None

        self._prev_small_gray: Optional[np.ndarray] = None
        self._last_frame_hash: Optional[int] = None
        self._frozen_frame_start: Optional[float] = None

        # Temporal signal history for frequency/oscillation dynamics (3.0s window)
        self._history_yaw: deque[Tuple[float, float]] = deque(maxlen=90)
        self._history_pitch: deque[Tuple[float, float]] = deque(maxlen=90)
        self._history_ear: deque[Tuple[float, float]] = deque(maxlen=90)
        self._history_motion: deque[Tuple[float, float]] = deque(maxlen=90)

        # Baseline shoulder height tracking for forward/backward lean
        self._shoulder_height_baseline: Optional[float] = None

        # Eye tracker & baseline calibration
        self._eye_closed_tracker_start: Optional[float] = None
        self._baseline_open_ear: float = getattr(config, "BASELINE_OPEN_EAR", 0.28)
        self._calibrated_ear: Optional[float] = None

        self._init_models()

    def set_calibrated_ear(self, ear: float) -> None:
        """Set user-calibrated baseline open EAR."""
        if ear > 0.15:
            self._calibrated_ear = ear
            self._baseline_open_ear = ear

    def _init_models(self) -> None:
        if not _MP_OK:
            print("[UpperBodyDetector] MediaPipe not installed.")
            return

        face_path = getattr(config, "FACE_LANDMARKER_MODEL", "")
        if not face_path or not os.path.isfile(face_path):
            face_path = str(config.MODELS_DIR / "face_landmarker.task")

        pose_path = getattr(config, "POSE_LANDMARKER_MODEL", "")
        if not pose_path or not os.path.isfile(pose_path):
            pose_path = str(config.MODELS_DIR / "pose_landmarker.task")

        hand_path = getattr(config, "HAND_LANDMARKER_MODEL", "")
        if not hand_path or not os.path.isfile(hand_path):
            hand_path = str(config.MODELS_DIR / "hand_landmarker.task")

        # 1. Face Landmarker
        if os.path.isfile(face_path):
            try:
                face_opts = mp_vision.FaceLandmarkerOptions(
                    base_options=mp_base.BaseOptions(model_asset_path=face_path),
                    output_face_blendshapes=True,
                    num_faces=1,
                    min_face_detection_confidence=0.45,
                    min_face_presence_confidence=0.45,
                    running_mode=mp_vision.RunningMode.IMAGE,
                )
                self._face_landmarker = mp_vision.FaceLandmarker.create_from_options(face_opts)
                print(f"[UpperBodyDetector] Loaded FaceLandmarker from '{face_path}'")
            except Exception as e:
                print(f"[UpperBodyDetector] FaceLandmarker init failed: {e}")
        else:
            print(f"[UpperBodyDetector] WARNING: FaceLandmarker model file not found at '{face_path}'")

        # 2. Pose Landmarker (Upper body shoulders/arms)
        if os.path.isfile(pose_path):
            try:
                pose_opts = mp_vision.PoseLandmarkerOptions(
                    base_options=mp_base.BaseOptions(model_asset_path=pose_path),
                    num_poses=1,
                    min_pose_detection_confidence=0.45,
                    min_pose_presence_confidence=0.45,
                    running_mode=mp_vision.RunningMode.IMAGE,
                )
                self._pose_landmarker = mp_vision.PoseLandmarker.create_from_options(pose_opts)
                print(f"[UpperBodyDetector] Loaded PoseLandmarker from '{pose_path}'")
            except Exception as e:
                print(f"[UpperBodyDetector] PoseLandmarker init failed: {e}")
        else:
            print(f"[UpperBodyDetector] WARNING: PoseLandmarker model file not found at '{pose_path}'")

        # 3. Hand Landmarker
        if os.path.isfile(hand_path):
            try:
                hand_opts = mp_vision.HandLandmarkerOptions(
                    base_options=mp_base.BaseOptions(model_asset_path=hand_path),
                    num_hands=2,
                    min_hand_detection_confidence=0.45,
                    min_hand_presence_confidence=0.45,
                    running_mode=mp_vision.RunningMode.IMAGE,
                )
                self._hand_landmarker = mp_vision.HandLandmarker.create_from_options(hand_opts)
                print(f"[UpperBodyDetector] Loaded HandLandmarker from '{hand_path}'")
            except Exception as e:
                print(f"[UpperBodyDetector] HandLandmarker init failed: {e}")
        else:
            print(f"[UpperBodyDetector] WARNING: HandLandmarker model file not found at '{hand_path}'")

    # ──────────────────────────────────────────────────────────────────
    def extract_features(
        self,
        bgr_frame: Optional[np.ndarray],
        yolo_info: Optional[Dict[str, Any]] = None,
        camera_valid: bool = True,
        timestamp: Optional[float] = None,
    ) -> UpperBodyFeatures:
        """
        Run multi-label feature extraction for a single frame.
        Represents unavailable signals as None (unknown).
        """
        now = timestamp if timestamp is not None else time.monotonic()

        # Handle camera faults
        if not camera_valid or bgr_frame is None or bgr_frame.size == 0:
            obs = IndependentObservations(
                timestamp=now,
                camera_health=Observation(name="camera_health", value="DISCONNECTED", confidence=1.0, timestamp=now, valid=False, details="No valid frame received"),
                person_present=Observation(name="person_present", value=False, confidence=0.0, timestamp=now, valid=False),
                face_present=Observation(name="face_present", value=False, confidence=0.0, timestamp=now, valid=False),
                face_occluded=Observation(name="face_occluded", value=False, confidence=0.0, timestamp=now, valid=False),
                head_direction=Observation(name="head_direction", value=HeadDirection.UNKNOWN, confidence=0.0, timestamp=now, valid=False),
                eye_state=Observation(name="eye_state", value=EyeState.UNKNOWN, confidence=0.0, timestamp=now, valid=False),
                book_detected=Observation(name="book_detected", value=False, confidence=0.0, timestamp=now, valid=False),
                phone_detected=Observation(name="phone_detected", value=False, confidence=0.0, timestamp=now, valid=False),
                hand_near_face=Observation(name="hand_near_face", value=HandActivity.HANDS_NOT_VISIBLE, confidence=0.0, timestamp=now, valid=False),
                body_pose=Observation(name="body_pose", value=ShoulderPosture.UNKNOWN, confidence=0.0, timestamp=now, valid=False),
                observable_study_activity=Observation(name="observable_study_activity", value=False, confidence=0.0, timestamp=now, valid=False),
                off_task_evidence=Observation(name="off_task_evidence", value=False, confidence=0.0, timestamp=now, valid=False),
                detection_confidence=Observation(name="detection_confidence", value=0.0, confidence=0.0, timestamp=now, valid=False),
            )
            return UpperBodyFeatures(
                timestamp=now,
                camera_valid=False,
                frame_frozen=False,
                low_visibility=False,
                observations=obs,
            )

        h, w = bgr_frame.shape[:2]

        # ── 1. Quality & Freshness ────────────────────────────────────
        small_gray = cv2.cvtColor(cv2.resize(bgr_frame, (160, 120)), cv2.COLOR_BGR2GRAY)
        frame_hash = hash(small_gray.tobytes())
        frame_frozen = False
        if self._last_frame_hash is not None and frame_hash == self._last_frame_hash:
            if self._frozen_frame_start is None:
                self._frozen_frame_start = now
            elif (now - self._frozen_frame_start) >= config.FROZEN_FRAME_TIMEOUT_SEC:
                frame_frozen = True
        else:
            self._frozen_frame_start = None
            self._last_frame_hash = frame_hash

        mean_intensity = float(np.mean(small_gray))
        low_visibility = mean_intensity < config.LOW_LIGHT_THRESHOLD

        # Inter-frame motion
        upper_body_motion = 0.0
        if self._prev_small_gray is not None and not frame_frozen:
            diff = cv2.absdiff(small_gray, self._prev_small_gray)
            upper_body_motion = float(np.mean(diff)) / 255.0
        self._prev_small_gray = small_gray
        self._history_motion.append((now, upper_body_motion))

        # ── 2. YOLO Context ───────────────────────────────────────────
        y_info = yolo_info or {}
        person_detected = y_info.get("person_detected", False)
        person_box = y_info.get("person_box", None)
        person_conf = y_info.get("person_conf", 0.0)

        book_detected = y_info.get("book_detected", False)
        book_box = y_info.get("book_box", None)
        phone_detected = y_info.get("phone_detected", False)
        phone_box = y_info.get("phone_box", None)
        laptop_detected = y_info.get("laptop_detected", False)

        # Convert RGB for MediaPipe
        mp_rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=mp_rgb) if _MP_OK else None

        # ── 3. Face & Head Pose ───────────────────────────────────────
        face_detected = False
        face_conf = 0.0
        face_box: Optional[Tuple[int, int, int, int]] = None
        landmark_vis_ratio = 0.0
        landmark_validity = False
        head_yaw: Optional[float] = None
        head_pitch: Optional[float] = None
        head_roll: Optional[float] = None
        ear: Optional[float] = None
        left_ear: Optional[float] = None
        right_ear: Optional[float] = None
        blink_score: Optional[float] = None
        mar: Optional[float] = None
        yawn_detected: bool = False
        gaze_h: Optional[float] = None
        gaze_v: Optional[float] = None

        inference_error = False
        if self._face_landmarker is not None and mp_img is not None and not low_visibility:
            try:
                face_res = self._face_landmarker.detect(mp_img)
                if face_res.face_landmarks:
                    face_detected = True
                    face_conf = 0.92
                    lm = face_res.face_landmarks[0]
                    landmark_vis_ratio = 1.0  # Dense mesh detected

                    xs = [p.x * w for p in lm]
                    ys = [p.y * h for p in lm]
                    x1, y1 = max(0, int(min(xs))), max(0, int(min(ys)))
                    x2, y2 = min(w, int(max(xs))), min(h, int(max(ys)))
                    face_box = (x1, y1, x2, y2)
                    fb_w = x2 - x1
                    fb_h = y2 - y1
                    if fb_w >= 40 and fb_h >= 40:
                        landmark_validity = True

                    # SolvePnP head pose: yaw, pitch, roll
                    pose_pts = np.array(
                        [(lm[i].x * w, lm[i].y * h) for i in _POSE_IDX],
                        dtype=np.float64,
                    )
                    focal = float(w)
                    cam_mat = np.array([[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]], dtype=np.float64)
                    dist_coeff = np.zeros((4, 1), dtype=np.float64)

                    ok, rvec, _ = cv2.solvePnP(_MODEL_PTS, pose_pts, cam_mat, dist_coeff, flags=cv2.SOLVEPNP_ITERATIVE)
                    if ok:
                        rmat, _ = cv2.Rodrigues(rvec)
                        sy = math.sqrt(rmat[0, 0]**2 + rmat[1, 0]**2)
                        if sy > 1e-6:
                            head_yaw = math.degrees(math.atan2(rmat[1, 0], rmat[0, 0]))
                            head_pitch = math.degrees(math.atan2(-rmat[2, 0], sy))
                            head_roll = math.degrees(math.atan2(rmat[2, 1], rmat[2, 2]))
                        else:
                            head_yaw = math.degrees(math.atan2(-rmat[2, 1], rmat[1, 1]))
                            head_pitch = math.degrees(math.atan2(-rmat[2, 0], sy))
                            head_roll = 0.0

                    # EAR calculation for each eye
                    left_ear = _compute_ear(lm, _LEFT_EYE, w, h)
                    right_ear = _compute_ear(lm, _RIGHT_EYE, w, h)
                    ear = (left_ear + right_ear) / 2.0

                    # Blendshapes blink probability (3D facial blendshape neural head)
                    if hasattr(face_res, "face_blendshapes") and face_res.face_blendshapes:
                        b_left = 0.0
                        b_right = 0.0
                        for cat in face_res.face_blendshapes[0]:
                            if cat.category_name == "eyeBlinkLeft":
                                b_left = cat.score
                            elif cat.category_name == "eyeBlinkRight":
                                b_right = cat.score
                        blink_score = (b_left + b_right) / 2.0

                    # MAR (Mouth Aspect Ratio for yawning detection)
                    mar = None
                    yawn_detected = False
                    if len(lm) >= 292:
                        m_h = math.hypot((lm[14].x - lm[13].x) * w, (lm[14].y - lm[13].y) * h)
                        m_w = math.hypot((lm[291].x - lm[61].x) * w, (lm[291].y - lm[61].y) * h)
                        mar = float(m_h / max(1e-5, m_w))
                        if mar > 0.48:
                            yawn_detected = True

                    # Gaze estimation via pupil/iris relative position
                    if len(lm) >= 478:
                        left_pupil = lm[468]
                        eye_l_inner = lm[133]
                        eye_l_outer = lm[33]
                        eye_width = max(1e-5, abs(eye_l_inner.x - eye_l_outer.x))
                        gaze_h = ((left_pupil.x - min(eye_l_inner.x, eye_l_outer.x)) / eye_width) - 0.5
            except Exception as e:
                print(f"[UpperBodyDetector] Face mesh exception: {e}")
                inference_error = True

        if head_yaw is not None:
            self._history_yaw.append((now, head_yaw))
        if head_pitch is not None:
            self._history_pitch.append((now, head_pitch))
        if ear is not None:
            self._history_ear.append((now, ear))

        # ── 4. Shoulders & Upper Torso ────────────────────────────────
        shoulders_detected = False
        left_shoulder: Optional[Tuple[float, float, float]] = None
        right_shoulder: Optional[Tuple[float, float, float]] = None
        shoulder_tilt_deg: Optional[float] = None
        shoulder_width_norm: Optional[float] = None

        if self._pose_landmarker is not None and mp_img is not None and not low_visibility:
            try:
                pose_res = self._pose_landmarker.detect(mp_img)
                if pose_res.pose_landmarks:
                    p_lm = pose_res.pose_landmarks[0]
                    # Landmark 11 = Left shoulder, 12 = Right shoulder
                    ls = p_lm[11]
                    rs = p_lm[12]
                    # Visibility / presence check
                    ls_vis = getattr(ls, "visibility", 1.0) or 1.0
                    rs_vis = getattr(rs, "visibility", 1.0) or 1.0

                    if ls_vis > 0.4 and rs_vis > 0.4:
                        shoulders_detected = True
                        left_shoulder = (ls.x, ls.y, ls.z)
                        right_shoulder = (rs.x, rs.y, rs.z)
                        dx = rs.x - ls.x
                        dy = rs.y - ls.y
                        shoulder_width_norm = math.sqrt(dx**2 + dy**2)
                        shoulder_tilt_deg = math.degrees(math.atan2(dy, dx))

                        mid_y = (ls.y + rs.y) / 2.0
                        if self._shoulder_height_baseline is None:
                            self._shoulder_height_baseline = mid_y
                        else:
                            # Slow adaptive baseline
                            self._shoulder_height_baseline = 0.99 * self._shoulder_height_baseline + 0.01 * mid_y
            except Exception as e:
                print(f"[UpperBodyDetector] Pose landmarker exception: {e}")
                inference_error = True

        # ── 5. Hands & Hand-to-Face Overlap ───────────────────────────
        hands_visible_count = 0
        hands_near_lower_border = False
        hand_to_face_iou = 0.0
        hand_near_chin = False
        hand_near_eyes = False

        if self._hand_landmarker is not None and mp_img is not None and not low_visibility:
            try:
                hand_res = self._hand_landmarker.detect(mp_img)
                if hand_res.hand_landmarks:
                    hands_visible_count = len(hand_res.hand_landmarks)
                    for h_lm in hand_res.hand_landmarks:
                        h_ys = [p.y * h for p in h_lm]
                        h_xs = [p.x * w for p in h_lm]
                        hx1, hy1 = int(min(h_xs)), int(min(h_ys))
                        hx2, hy2 = int(max(h_xs)), int(max(h_ys))
                        h_box = (hx1, hy1, hx2, hy2)

                        # Check lower border proximity (typing/desk work near bottom 15% of frame)
                        if max(h_ys) > 0.82 * h:
                            hands_near_lower_border = True

                        # Determine target head box: detected face box or estimated head region
                        target_head_box = face_box
                        if target_head_box is None:
                            if shoulders_detected and left_shoulder is not None and right_shoulder is not None:
                                mx = (left_shoulder[0] + right_shoulder[0]) / 2.0 * w
                                my = (left_shoulder[1] + right_shoulder[1]) / 2.0 * h
                                sw = max(abs(right_shoulder[0] - left_shoulder[0]) * w, 50.0)
                                target_head_box = (
                                    max(0, int(mx - sw * 0.45)),
                                    max(0, int(my - sw * 1.10)),
                                    min(w, int(mx + sw * 0.45)),
                                    max(0, int(my + sw * 0.10)),
                                )
                            elif person_box is not None:
                                px1, py1, px2, py2 = person_box
                                p_h = py2 - py1
                                target_head_box = (px1, py1, px2, int(py1 + 0.35 * p_h))

                        # Check overlap with face / head box
                        if target_head_box is not None:
                            iou = _compute_box_iou(h_box, target_head_box)
                            if iou > hand_to_face_iou:
                                hand_to_face_iou = iou

                            # Check proximity to chin (bottom 35% of head box)
                            chin_y = target_head_box[1] + 0.65 * (target_head_box[3] - target_head_box[1])
                            if hy1 <= target_head_box[3] and hy2 >= chin_y and abs(hx1 - target_head_box[0]) < (target_head_box[2] - target_head_box[0]):
                                hand_near_chin = True

                            # Check proximity to eyes (top 50% of head box)
                            eye_y = target_head_box[1] + 0.50 * (target_head_box[3] - target_head_box[1])
                            if hy1 <= eye_y and hy2 >= target_head_box[1] and iou > 0.15:
                                hand_near_eyes = True
            except Exception as e:
                print(f"[UpperBodyDetector] Hand landmarker exception: {e}")
                inference_error = True

        # ── 6. Independent Multi-Label Categoricals ───────────────────
        # Head direction
        head_dir = HeadDirection.UNKNOWN
        if head_yaw is not None and head_pitch is not None:
            if abs(head_yaw) <= 18.0 and -10.0 <= head_pitch <= 14.0:
                head_dir = HeadDirection.FACING_SCREEN
            elif head_pitch > 14.0:
                head_dir = HeadDirection.TILTED_DOWN
            elif head_pitch < -12.0:
                head_dir = HeadDirection.TILTED_UP
            elif head_yaw < -18.0:
                head_dir = HeadDirection.TURNED_LEFT
            elif head_yaw > 18.0:
                head_dir = HeadDirection.TURNED_RIGHT
            elif head_roll is not None and abs(head_roll) > 15.0:
                head_dir = HeadDirection.TILTED_SIDEWAYS

        # Eye state (missing/obscured landmarks are UNKNOWN, not closed)
        # Account for head pitch foreshortening, calibrated open EAR, and MediaPipe blendshapes
        eye_state = EyeState.UNKNOWN
        if landmark_validity and face_detected and ear is not None:
            # Check if hand directly obscures eye region
            if hand_near_eyes and hand_to_face_iou > 0.25:
                eye_state = EyeState.UNKNOWN
            else:
                base_ear = self._calibrated_ear or self._baseline_open_ear
                # Pitch foreshortening compensation: looking down tilts eye plane
                pitch_comp = 0.0
                if head_pitch is not None and head_pitch > 8.0:
                    pitch_comp = max(0.0, min(0.08, (head_pitch - 8.0) * 0.003))

                close_threshold = max(config.EAR_CLOSE_THRESHOLD, (base_ear * 0.65) - pitch_comp)

                if blink_score is not None:
                    # MediaPipe 3D Neural Blendshapes: blink probability [0.0, 1.0]
                    if blink_score >= getattr(config, "BLINK_BLENDSHAPE_THRESHOLD", 0.58):
                        eye_state = EyeState.EYES_CLOSED
                    elif blink_score <= 0.35:
                        eye_state = EyeState.EYES_OPEN
                    else:
                        # Ambiguous blendshape: consult pitch-compensated EAR
                        eye_state = EyeState.EYES_CLOSED if ear < close_threshold else EyeState.EYES_OPEN
                else:
                    # Fallback to calibrated EAR
                    eye_state = EyeState.EYES_CLOSED if ear < close_threshold else EyeState.EYES_OPEN

        # Shoulder posture
        shoulder_posture = ShoulderPosture.UNKNOWN
        if shoulders_detected and left_shoulder is not None and right_shoulder is not None:
            mid_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
            base_y = self._shoulder_height_baseline or mid_y
            z_diff = abs(left_shoulder[2] - right_shoulder[2])

            if z_diff > 0.18:
                shoulder_posture = ShoulderPosture.SHOULDERS_ROTATED
            elif shoulder_tilt_deg is not None and abs(shoulder_tilt_deg) > 10.0:
                shoulder_posture = ShoulderPosture.SHOULDERS_TILTED
            elif mid_y > base_y + 0.06:
                shoulder_posture = ShoulderPosture.LEANING_FORWARD
            elif mid_y < base_y - 0.06:
                shoulder_posture = ShoulderPosture.LEANING_BACKWARD
            else:
                shoulder_posture = ShoulderPosture.UPRIGHT

        # Hand activity
        hand_act = HandActivity.HANDS_NOT_VISIBLE
        if hands_visible_count > 0:
            if hand_to_face_iou > 0.40 or (hand_to_face_iou > 0.20 and not face_detected):
                hand_act = HandActivity.HAND_COVERING_FACE
            elif hand_near_chin:
                hand_act = HandActivity.HAND_AT_CHIN
            elif hand_near_eyes:
                hand_act = HandActivity.HAND_AT_EYES
            elif hands_near_lower_border:
                hand_act = HandActivity.HANDS_NEAR_LOWER_BORDER
            elif phone_detected:
                hand_act = HandActivity.HAND_HOLDING_PHONE
            else:
                hand_act = HandActivity.UNKNOWN

        # Dedicated Phone Interaction Detection (Section 4)
        phone_interaction = PhoneInteractionStatus.NONE
        phone_actively_used = False
        phone_near_torso = False
        book_near_torso = False
        hand_holding = False
        obj_state = ObjectState.NONE

        if phone_detected and phone_box is not None:
            phone_interaction = PhoneInteractionStatus.PHONE_VISIBLE
            # Check overlap with hands (phone held/handled)
            for h_box in hand_boxes:
                if self._compute_box_iou(phone_box, h_box) > 0.08:
                    hand_holding = True
                    break

            if hand_holding:
                phone_interaction = PhoneInteractionStatus.PHONE_HELD
                # Check gaze or head tilt directed toward phone (active usage)
                gaze_to_phone = (head_dir in (HeadDirection.TILTED_DOWN, HeadDirection.FACING_SCREEN))
                if gaze_to_phone or (head_pitch is not None and head_pitch > 8.0):
                    phone_interaction = PhoneInteractionStatus.PHONE_IN_USE
                    phone_actively_used = True
            elif person_box is not None and phone_box[1] < person_box[3]:
                # Phone near torso area
                phone_near_torso = True
                if head_pitch is not None and head_pitch > 12.0:
                    phone_interaction = PhoneInteractionStatus.PHONE_IN_USE
                    phone_actively_used = True

            if person_box is not None and phone_box[1] < person_box[3]:
                phone_near_torso = True
                obj_state = ObjectState.PHONE_NEAR_TORSO

        if hand_holding:
            hand_act = HandActivity.HAND_HOLDING_PHONE

        if book_detected and book_box is not None:
            book_near_torso = True
            obj_state = ObjectState.BOOK_NEAR_TORSO
        elif laptop_detected:
            obj_state = ObjectState.LAPTOP_VISIBLE

        # ── 7. Observable Pose Features (Section D) ───────────────────
        # Temporal analysis: repeated head turns / droops over last 2.5s
        cutoff = now - 2.5
        recent_yaws = [y for t_val, y in self._history_yaw if t_val >= cutoff]
        recent_pitches = [p for t_val, p in self._history_pitch if t_val >= cutoff]

        repeated_turns = False
        room_scan_yaw = getattr(config, "HEAD_TURN_ROOM_SCAN_YAW_DEG", 30.0)
        if len(recent_yaws) >= 15:
            # Require wide yaw swings across room (not small glances across screen)
            flips = sum(1 for i in range(1, len(recent_yaws)) if (recent_yaws[i] > room_scan_yaw and recent_yaws[i - 1] < -room_scan_yaw) or (recent_yaws[i] < -room_scan_yaw and recent_yaws[i - 1] > room_scan_yaw))
            if flips >= 2:
                repeated_turns = True

        repeated_droops = False
        droop_deg = getattr(config, "HEAD_DROOP_CYCLIC_PITCH_DEG", 26.0)
        if len(recent_pitches) >= 15:
            # Count pitch oscillations between level (<12 deg) and downward droop (>26 deg)
            droop_peaks = sum(1 for i in range(1, len(recent_pitches) - 1) if recent_pitches[i] > droop_deg and recent_pitches[i] > recent_pitches[i - 1] and recent_pitches[i] > recent_pitches[i + 1])
            if droop_peaks >= 2:
                repeated_droops = True

        # Minimal movement
        recent_motions = [m for t_val, m in self._history_motion if t_val >= cutoff]
        minimal_movement = False
        if len(recent_motions) >= 10 and np.mean(recent_motions) < config.MOTION_STILL_THRESHOLD:
            minimal_movement = True

        # Temporal Eye closure duration & Blinking distinction
        brief_eye_close = False
        sustained_eye_close = False
        normal_blinking = False
        eye_closure_duration = 0.0

        if eye_state == EyeState.EYES_CLOSED:
            if self._eye_closed_tracker_start is None:
                self._eye_closed_tracker_start = now
            eye_closure_duration = now - self._eye_closed_tracker_start

            if eye_closure_duration <= getattr(config, "BRIEF_BLINK_MAX_SECS", 0.5):
                brief_eye_close = True
                normal_blinking = True
                sustained_eye_close = False
            elif eye_closure_duration >= getattr(config, "DROWSINESS_SUSTAINED_SECS", 2.0):
                brief_eye_close = False
                normal_blinking = False
                sustained_eye_close = True
            else:
                # In between 0.5s and 2.0s: closing in progress, not yet sustained
                brief_eye_close = False
                normal_blinking = False
                sustained_eye_close = False
        else:
            self._eye_closed_tracker_start = None
            eye_closure_duration = 0.0
            brief_eye_close = False
            normal_blinking = False
            sustained_eye_close = False

        drowsiness_evidence = "none"
        if sustained_eye_close:
            drowsiness_evidence = f"Sustained eye closure for {eye_closure_duration:.1f}s"
        elif repeated_droops:
            drowsiness_evidence = "Repeated head drooping (nodding off)"
        elif hand_near_eyes and (ear is not None and ear < getattr(config, "BORDERLINE_EAR_THRESHOLD", 0.22)):
            drowsiness_evidence = "Eye rubbing with fatigue signs"

        pose_features = ObservablePoseFeatures(
            head_facing_screen=(head_dir == HeadDirection.FACING_SCREEN),
            head_tilted_down=(head_pitch is not None and head_pitch > 14.0),
            head_tilted_up=(head_pitch is not None and head_pitch < -12.0),
            head_turned_left_right=(head_yaw is not None and abs(head_yaw) > 18.0),
            head_tilted_sideways=(head_roll is not None and abs(head_roll) > 15.0),
            repeated_head_turns=repeated_turns,
            repeated_head_drooping=repeated_droops,
            face_resting_on_hand=hand_near_chin,
            face_covered_by_hand=(
                hand_to_face_iou > 0.35
                or hand_act == HandActivity.HAND_COVERING_FACE
                or (not face_detected and hand_to_face_iou > 0.20 and (person_detected or shoulders_detected))
            ),
            face_covered_by_book_or_object=(book_detected and not face_detected and (person_detected or shoulders_detected)),
            upright_upper_body=(shoulder_posture == ShoulderPosture.UPRIGHT),
            upper_body_leaning_forward_or_backward=(shoulder_posture in (ShoulderPosture.LEANING_FORWARD, ShoulderPosture.LEANING_BACKWARD)),
            shoulders_rotated=(shoulder_posture == ShoulderPosture.SHOULDERS_ROTATED),
            shoulders_tilted=(shoulder_posture == ShoulderPosture.SHOULDERS_TILTED),
            hands_moving_near_lower_camera_boundary=hands_near_lower_border,
            hand_touching_chin_or_eyes=(hand_near_chin or hand_near_eyes),
            phone_held_near_upper_torso=phone_near_torso,
            phone_actively_used=phone_actively_used,
            brief_eye_closure=brief_eye_close,
            normal_blinking=normal_blinking,
            sustained_eye_closure=sustained_eye_close,
            upper_body_moving_out_of_frame=(not person_detected and not shoulders_detected),
            minimal_upper_body_movement=minimal_movement,
            yawn_detected=yawn_detected,
        )

        # ── 8. Independent Observations (Section 2) ───────────────────
        cam_health_val = "OK"
        if not camera_valid:
            cam_health_val = "DISCONNECTED"
        elif frame_frozen:
            cam_health_val = "FROZEN"
        elif low_visibility:
            cam_health_val = "LOW_LIGHT"
        elif inference_error:
            cam_health_val = "INFERENCE_ERROR"

        study_activity = "none"
        if book_detected:
            study_activity = "reading_book"
        elif laptop_detected:
            study_activity = "laptop_work"
        elif hands_near_lower_border:
            study_activity = "desk_hand_activity"
        elif head_dir == HeadDirection.FACING_SCREEN and not phone_detected and not low_visibility:
            study_activity = "screen_study"

        off_task_ev = "none"
        if phone_detected or pose_features.phone_held_near_upper_torso:
            off_task_ev = "cell_phone"
        elif head_dir in (HeadDirection.TURNED_LEFT, HeadDirection.TURNED_RIGHT):
            off_task_ev = "head_turned_away"
        elif pose_features.repeated_head_turns:
            off_task_ev = "scanning_room"
        elif pose_features.face_resting_on_hand:
            off_task_ev = "resting_on_hand"
        elif shoulder_posture == ShoulderPosture.LEANING_BACKWARD:
            off_task_ev = "leaning_back_inactive"
        elif pose_features.minimal_upper_body_movement and study_activity == "none":
            off_task_ev = "motionless_idle"

        obs = IndependentObservations(
            timestamp=now,
            camera_health=Observation(
                name="camera_health",
                value=cam_health_val,
                confidence=1.0 if cam_health_val == "OK" else 0.95,
                timestamp=now,
                valid=(cam_health_val == "OK"),
                details=f"mean_intensity={mean_intensity:.1f}, frozen={frame_frozen}",
            ),
            person_present=Observation(
                name="person_present",
                value=bool(person_detected or face_detected or shoulders_detected),
                confidence=person_conf if person_detected else (0.85 if shoulders_detected else 0.0),
                timestamp=now,
                valid=True,
                details=f"box={person_box}" if person_box else "shoulders/face detected",
            ),
            face_present=Observation(
                name="face_present",
                value=face_detected,
                confidence=face_conf,
                timestamp=now,
                valid=face_detected,
                details=f"box={face_box}, vis_ratio={landmark_vis_ratio:.2f}",
            ),
            face_occluded=Observation(
                name="face_occluded",
                value=bool(pose_features.face_covered_by_hand or pose_features.face_covered_by_book_or_object or (not face_detected and (person_detected or shoulders_detected))),
                confidence=0.90 if pose_features.face_covered_by_hand else 0.70,
                timestamp=now,
                valid=True,
                details=f"hand_to_face_iou={hand_to_face_iou:.2f}, by_hands={pose_features.face_covered_by_hand}",
            ),
            head_direction=Observation(
                name="head_direction",
                value=head_dir,
                confidence=0.88 if head_yaw is not None else 0.0,
                timestamp=now,
                valid=(head_yaw is not None),
                details=f"yaw={head_yaw:.1f}deg, pitch={head_pitch:.1f}deg" if head_yaw is not None else "landmarks unavailable",
            ),
            eye_state=Observation(
                name="eye_state",
                value=eye_state,
                confidence=0.90 if ear is not None else 0.0,
                timestamp=now,
                valid=(ear is not None),
                details=f"EAR={ear:.3f}" if ear is not None else "eyes occluded/unavailable",
            ),
            book_detected=Observation(
                name="book_detected",
                value=book_detected,
                confidence=0.85 if book_detected else 0.0,
                timestamp=now,
                valid=True,
                details=f"box={book_box}" if book_box else "no book",
            ),
            phone_detected=Observation(
                name="phone_detected",
                value=phone_detected,
                confidence=0.90 if phone_detected else 0.0,
                timestamp=now,
                valid=True,
                details=f"box={phone_box}" if phone_box else "no phone",
            ),
            hand_near_face=Observation(
                name="hand_near_face",
                value=hand_act,
                confidence=0.85 if hands_visible_count > 0 else 0.0,
                timestamp=now,
                valid=(hands_visible_count > 0),
                details=f"hands_visible={hands_visible_count}, chin={hand_near_chin}, eyes={hand_near_eyes}",
            ),
            body_pose=Observation(
                name="body_pose",
                value=shoulder_posture,
                confidence=0.85 if shoulders_detected else 0.0,
                timestamp=now,
                valid=shoulders_detected,
                details=f"tilt={shoulder_tilt_deg:.1f}deg" if shoulder_tilt_deg is not None else "shoulders unavailable",
            ),
            observable_study_activity=Observation(
                name="observable_study_activity",
                value=(study_activity != "none"),
                confidence=0.88,
                timestamp=now,
                valid=True,
                details=study_activity,
            ),
            off_task_evidence=Observation(
                name="off_task_evidence",
                value=(off_task_ev != "none"),
                confidence=0.88 if off_task_ev != "none" else 0.10,
                timestamp=now,
                valid=True,
                details=off_task_ev,
            ),
            detection_confidence=Observation(
                name="detection_confidence",
                value=min(person_conf if person_detected else 1.0, face_conf if face_detected else 1.0),
                confidence=0.95,
                timestamp=now,
                valid=True,
                details="Aggregate confidence across active detectors",
            ),
        )

        return UpperBodyFeatures(
            timestamp=now,
            camera_valid=(not inference_error and cam_health_val != "DISCONNECTED"),
            frame_frozen=frame_frozen,
            low_visibility=low_visibility,
            mean_intensity=mean_intensity,
            person_detected=person_detected or face_detected or shoulders_detected,
            person_conf=person_conf if person_detected else 0.85,
            person_box=person_box,
            face_detected=face_detected,
            face_conf=face_conf,
            face_box=face_box,
            landmark_visibility_ratio=landmark_vis_ratio,
            head_yaw=head_yaw,
            head_pitch=head_pitch,
            head_roll=head_roll,
            ear=ear,
            left_ear=left_ear,
            right_ear=right_ear,
            blink_score=blink_score,
            eye_closure_duration=eye_closure_duration,
            drowsiness_evidence=drowsiness_evidence,
            landmark_validity=landmark_validity,
            mar=mar,
            yawn_detected=yawn_detected,
            gaze_horizontal=gaze_h,
            gaze_vertical=gaze_v,
            shoulders_detected=shoulders_detected,
            left_shoulder=left_shoulder,
            right_shoulder=right_shoulder,
            shoulder_tilt_deg=shoulder_tilt_deg,
            shoulder_width_norm=shoulder_width_norm,
            upper_body_motion=upper_body_motion,
            hands_visible_count=hands_visible_count,
            hands_near_lower_border=hands_near_lower_border,
            hand_to_face_iou=hand_to_face_iou,
            hand_near_chin=hand_near_chin,
            hand_near_eyes=hand_near_eyes,
            book_detected=book_detected,
            book_box=book_box,
            phone_detected=phone_detected,
            phone_box=phone_box,
            phone_interaction=phone_interaction,
            laptop_detected=laptop_detected,
            head_direction=head_dir,
            eye_state=eye_state,
            shoulder_posture=shoulder_posture,
            hand_activity=hand_act,
            object_state=obj_state,
            pose_features=pose_features,
            observations=obs,
            inference_error=inference_error,
        )

    def close(self) -> None:
        """Release MediaPipe detector instances."""
        if self._face_landmarker is not None:
            try:
                self._face_landmarker.close()
            except Exception:
                pass
        if self._pose_landmarker is not None:
            try:
                self._pose_landmarker.close()
            except Exception:
                pass
        if self._hand_landmarker is not None:
            try:
                self._hand_landmarker.close()
            except Exception:
                pass
