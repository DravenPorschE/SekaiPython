import os
import re
import uuid
import queue
import threading
import requests
from flask import Flask, request, jsonify
import whisper
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import time
import whisper.audio

from datetime import datetime
from datetime import date

import json
from json.decoder import JSONDecodeError

# ----------------------------
# Load Whisper Model
# ----------------------------
print("Loading Whisper model...")
meeting_transcriptor_model = whisper.load_model("small")
model_lock = threading.Lock()
print("Model loaded successfully.")

LANGUAGE = "english"

# ----------------------------
# Flask Setup
# ----------------------------
app = Flask(__name__)
task_queue = queue.Queue()
result_queue = queue.Queue()

def worker():
    while True:
        job_id, file_path = task_queue.get()
        if job_id is None:
            break

        # Measure transcription start time
        start_time = time.time()

        # Load audio to get duration
        audio = whisper.audio.load_audio(file_path)
        duration_seconds = len(audio) / whisper.audio.SAMPLE_RATE
        print(f"🎵 Received audio '{file_path}' with duration: {duration_seconds:.2f} seconds")

        with model_lock:
            result = meeting_transcriptor_model.transcribe(file_path, language=None)

        transcript = result["text"].strip()

        # Measure transcription end time
        end_time = time.time()
        processing_time = end_time - start_time
        print(f"⏱ Transcription completed in {processing_time:.2f} seconds")

        result_queue.put((job_id, transcript))
        task_queue.task_done()

for _ in range(2):
    threading.Thread(target=worker, daemon=True).start()

# ----------------------------
# Endpoints
# ----------------------------
@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    # Check if file is present
    if 'file' not in request.files:
        return "No file part", 400
    
    wav_file = request.files['file']
    
    # Check if file was selected
    if wav_file.filename == '':
        return "No selected file", 400
    
    # Check if file is WAV format
    if not wav_file.filename.lower().endswith('.wav'):
        return "Only WAV files are accepted", 400
    
    # Save the uploaded file temporarily
    temp_path = f"recording_{uuid.uuid4().hex}.wav"
    wav_file.save(temp_path)
    
    # Create job ID and add to queue
    job_id = threading.get_ident()
    task_queue.put((job_id, temp_path))
    
    # Wait for transcription result
    while True:
        rid, transcript = result_queue.get()
        if rid == job_id:
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"Cleanup error: {e}")
            # Print only the transcription output
            print(transcript)
            return transcript

@app.route("/test", methods=["GET"])
def test_connection():
    return "Server is running", 200

# ----------------------------
# Run Server
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)