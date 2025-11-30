import pyttsx3
import os

# Initialize TTS engine
engine = pyttsx3.init()

# ----------------------------
# Optional: choose a female voice
# ----------------------------
voices = engine.getProperty('voices')
female_voice = None
for voice in voices:
    if "f" in voice.id.lower():  # 'english+f1', 'english+f2', etc.
        female_voice = voice.id
        break

if female_voice:
    engine.setProperty('voice', female_voice)

# Optional: set speed and volume
engine.setProperty('rate', 150)    # words per minute
engine.setProperty('volume', 0.8)  # 0.0 to 1.0

# ----------------------------
# Text you want to speak
# ----------------------------
text_to_speak = "Hello! This is a female voice speaking through the USB headphones."

# Save to WAV file (for reliable USB playback)
wav_file = "/home/pi/output.wav"  # use absolute path
engine.save_to_file(text_to_speak, wav_file)
engine.runAndWait()  # ensure file is fully written

# ----------------------------
# Play through USB headphones
# ----------------------------
os.system(f"aplay -D plughw:1,0 {wav_file}")
+