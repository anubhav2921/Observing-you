# Place your custom audio files here.
#
# Expected files:
#   distraction.wav   — played when sustained distraction indicators are detected
#   sleepiness.wav    — played when prolonged eye-closure indicators are detected
#   occlusion.wav     — played when face is intensely covered or hidden
#
# Supported format: WAV (PCM, 16-bit recommended) or MP3
# Convert MP3 → WAV with: ffmpeg -i alert.mp3 -ar 44100 -ac 1 distraction.wav
#
# Audio paths can be changed in config.py:
#   AUDIO_DISTRACTION_FILE
#   AUDIO_SLEEPINESS_FILE
#   AUDIO_OCCLUSION_FILE
