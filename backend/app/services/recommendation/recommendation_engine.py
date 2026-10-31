"""
app/recommendation_engine.py — Rules-based, empathetic recommendation engine.
Generates constructive, actionable advice and reasons for the dashboard.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from backend.app.schemas.events import RecommendationData
from backend.app.services.decision.state_machine import StudyState


class RecommendationEngine:
    """
    Evaluates current state, observations, and temporal duration to produce
    dynamic, supportive, and non-shaming guidance for the student.
    """

    @staticmethod
    def get_recommendation(
        state: StudyState,
        diagnostic_reason: str = "",
        duration_seconds: float = 0.0,
        observations: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
    ) -> RecommendationData:
        """Return a structured recommendation with clear reasons and actionable guidance."""
        if not is_active:
            return RecommendationData(
                title="Session Inactive",
                message="Click 'Start Monitoring' to begin tracking your study focus.",
                reason="Monitoring is paused or not yet started.",
                severity="info",
            )

        obs = observations or {}

        # 1. Technical & Camera Issues
        if state == StudyState.CAMERA_ERROR:
            return RecommendationData(
                title="Camera Unavailable",
                message="Video frames are missing. Please check your webcam connection or ensure browser camera permissions are allowed.",
                reason=diagnostic_reason or "Camera stream dropped or hardware device unavailable.",
                severity="critical",
            )

        if state == StudyState.LOW_VISIBILITY:
            return RecommendationData(
                title="Low Lighting Detected",
                message="The study area is too dark for accurate detection. Consider turning on a room light or facing a desk lamp.",
                reason=diagnostic_reason or "Average frame luminance is below the threshold for reliable facial and posture tracking.",
                severity="warning",
            )

        # 2. Absence & Occlusion
        if state == StudyState.STUDENT_ABSENT:
            return RecommendationData(
                title="Desk Unattended",
                message="No student is currently detected in view. Monitoring will resume automatically as soon as you return.",
                reason=diagnostic_reason or f"Person absent from camera frame for {duration_seconds:.1f}s.",
                severity="neutral",
            )

        if state == StudyState.FACE_OCCLUDED:
            return RecommendationData(
                title="Face or Workspace Blocked",
                message="Your face or study area appears obstructed by a book, hand, or object. Adjust your position so your face remains in view.",
                reason=diagnostic_reason or f"Face landmarks concealed while upper-body is present for {duration_seconds:.1f}s.",
                severity="warning",
            )

        if state == StudyState.OCCLUSION_UNCERTAIN:
            return RecommendationData(
                title="Partial View Obstruction",
                message="Parts of your face are partially hidden. If you're reading a book closely, try positioning it slightly below eye level.",
                reason="Partial landmark occlusion detected; tracking is temporarily uncertain.",
                severity="info",
            )

        # 3. Inactivity & Distraction
        if state == StudyState.INACTIVITY_WARNING:
            return RecommendationData(
                title="Sustained Inactivity",
                message="You've been motionless for an extended period. If you're reading or brainstorming, ensure your study materials are visible.",
                reason=diagnostic_reason or f"Motionless posture detected without active study interaction for {duration_seconds:.1f}s.",
                severity="warning",
            )

        if state == StudyState.DISTRACTED:
            if "phone" in diagnostic_reason.lower() or obs.get("phone_detected", False):
                return RecommendationData(
                    title="Phone Observed in View",
                    message="A smartphone was observed in your study zone. Placing it out of reach will help protect your concentration.",
                    reason=diagnostic_reason or "Mobile device detected in active study area.",
                    severity="warning",
                )
            return RecommendationData(
                title="Distraction Detected",
                message="Your focus has shifted away from study tasks. Take a gentle breath and bring your attention back to your materials.",
                reason=diagnostic_reason or "Off-task indicators detected.",
                severity="warning",
            )

        if state == StudyState.LOOKING_AWAY:
            return RecommendationData(
                title="Gaze Drifted Away",
                message="Your gaze has turned away from your desk. When ready, refocus on your screen or reading materials.",
                reason=diagnostic_reason or f"Head or gaze oriented away from study area for {duration_seconds:.1f}s.",
                severity="neutral",
            )

        # 4. Fatigue & Drowsiness
        if state == StudyState.POSSIBLE_DROWSINESS:
            return RecommendationData(
                title="Signs of Fatigue",
                message="Prolonged eye closure or head drooping detected. Take a quick 5-minute break, stretch, or drink a glass of water.",
                reason=diagnostic_reason or f"Drowsiness indicators sustained for {duration_seconds:.1f}s.",
                severity="warning",
            )

        # 5. Unconfirmed Activity
        if state == StudyState.STUDY_ACTIVITY_UNCONFIRMED:
            return RecommendationData(
                title="Align Study Materials",
                message="You are seated at the desk, but no active study interaction (screen, book, or notes) is confirmed yet.",
                reason=diagnostic_reason or "Person present, but observable study indicators are pending verification.",
                severity="info",
            )

        # 6. Recovery & Active Study
        if state == StudyState.RECOVERING:
            return RecommendationData(
                title="Focus Returning",
                message="Good job returning to your study materials. Stabilizing session metrics...",
                reason="Recovery criteria being verified across temporal window.",
                severity="info",
            )

        if state in (StudyState.STUDYING, StudyState.STUDYING_READING, StudyState.STUDYING_WRITING):
            activity_label = "reading" if state == StudyState.STUDYING_READING else ("writing" if state == StudyState.STUDYING_WRITING else "screen study")
            return RecommendationData(
                title="Great Study Flow!",
                message=f"Consistent {activity_label} focus detected. You're in a great concentration rhythm—keep it up!",
                reason="Attentive posture, active eye gaze, and study engagement verified.",
                severity="positive",
            )

        # Fallback
        return RecommendationData(
            title="Monitoring Active",
            message="Your study session is being monitored. Maintain good posture and focus.",
            reason=diagnostic_reason or "Standard monitoring active.",
            severity="info",
        )

