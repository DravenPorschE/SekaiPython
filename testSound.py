from google.cloud import texttospeech
import pygame

# Authenticate with JSON key
client = texttospeech.TextToSpeechClient.from_service_account_file("path/to/key.json")

synthesis_input = texttospeech.SynthesisInput(text="Hello from Google Cloud TTS!")

voice = texttospeech.VoiceSelectionParams(
    language_code="en-US", 
    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
)

audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3
)

response = client.synthesize_speech(
    input=synthesis_input, voice=voice, audio_config=audio_config
)

# Save the file
with open("speech.mp3", "wb") as out:
    out.write(response.audio_content)

# Play it
pygame.mixer.init()
pygame.mixer.music.load("speech.mp3")
pygame.mixer.music.play()
while pygame.mixer.music.get_busy():
    pygame.time.Clock().tick(10)
