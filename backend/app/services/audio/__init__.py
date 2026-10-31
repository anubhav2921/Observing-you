"""
backend/app/services/audio — Central audio management and priority preemption.
"""

from backend.app.services.audio.audio_alerts import CentralAudioManager, build_alerts

STATE_PRIORITY = CentralAudioManager.STATE_PRIORITY

__all__ = ["CentralAudioManager", "STATE_PRIORITY", "build_alerts"]
