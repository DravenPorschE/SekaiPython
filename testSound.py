import pyttsx3
import os
import time

# Initialize engine
engine = pyttsx3.init()

# List available voices
voices = engine.getProperty('voices')
for idx, voice in enumerate(voices):
    print(f"{idx}: {voice.name} - {voice.id}")

# Choose a voice by index (e.g., 1)
engine.setProperty('voice', voices[1].id)

# Optional: change speed and volume
engine.setProperty('rate', 150)    # Speed
engine.setProperty('volume', 0.8)  # Volume 0.0 to 1.0

# Convert text to WAV
engine.save_to_file("Hello, USB headphones with a new voice!", "output.wav")
engine.runAndWait()

while not os.path.exists("output.wav"):
    time.sleep(0.1)

# Play through USB headphones
os.system("aplay -D plughw:1,0 output.wav")
