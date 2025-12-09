import subprocess
import wave
import json
from vosk import Model, KaldiRecognizer
from pydub import AudioSegment
import os
import time

from ai_talk import getSekaiResponse
from typecast_api import text_to_speech_api
from get_intent import getSekaiIntent
from intent_text import get_intent

def convert_to_mono(input_wav, output_wav):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_wav,
        "-ac", "1",
        "-ar", "16000",
        output_wav
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def boost_volume(input_wav, output_wav, boost_db=20):
    audio = AudioSegment.from_wav(input_wav)
    louder = audio + boost_db
    louder.export(output_wav, format="wav")


def transcribe_audio(wav_path, model_path="vosk-model-small-en-us-0.15"):
    wf = wave.open(wav_path, "rb")

    if wf.getnchannels() != 1:
        return ""

    model = Model(model_path)
    rec = KaldiRecognizer(model, wf.getframerate())

    final_text = ""

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break

        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            final_text += result.get("text", "") + " "

    result = json.loads(rec.FinalResult())
    final_text += result.get("text", "")

    return final_text.strip()


# ----------------------------------------------------
# MAIN FUNCTION YOU WILL CALL FROM OTHER FILES
# ----------------------------------------------------
def transcribe_wav(input_wav, boost_db=15):
    temp_mono = "converted.wav"
    temp_loud = "loud.wav"

    convert_to_mono(input_wav, temp_mono)
    boost_volume(temp_mono, temp_loud, boost_db=boost_db)

    text = transcribe_audio(temp_loud)
    return text

def main():
    start_time = time.time()  # Start the timer

    result = transcribe_wav("voiceRecord.wav")
    current_mood = "happy"

    if get_intent(result) in ["display_weather", "display_calendar"]:
        print("Open calendar")
        end_time = time.time()
        print(f"Finished in {end_time - start_time:.2f} seconds")
        return

    if result:
        print("Transcription:")
        print(result)

        API_KEY = "__pltMzLwjRtejoHYcjCEi984cBgKa6qMU6EiSkEs2Xne"
    
        ai_intent = getSekaiIntent(result)

        print(ai_intent)
        data = json.loads(ai_intent)  
        command_value = data["command"]  

        ai_response = getSekaiResponse(result, current_mood)

        audio_file = text_to_speech_api(ai_response, API_KEY)
        
        if audio_file and os.path.exists(audio_file):
            print(f"\n🎵 To play the audio on Raspberry Pi:")
            print(f"   aplay {audio_file}")
            try:
                subprocess.run(['aplay', audio_file], check=True)
            except:
                print("   Could not play audio automatically")
        else:
            print("Transcription failed.")

    end_time = time.time()  # End the timer
    print(f"\nFinished in {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
