#!/usr/bin/env python3
"""
whisper_audio_transcribe.py
Transcribe audio using faster-whisper and return text
"""

from faster_whisper import WhisperModel
import os
import time
import logging

# Suppress verbose logs
logging.getLogger("faster_whisper").setLevel(logging.WARNING)

def transcribe_wav_file(file_path, model_size="small", language="en"):
    """
    Transcribe a WAV file using faster-whisper
    
    Args:
        file_path: Path to WAV file
        model_size: "tiny", "base", "small", "medium", "large-v2" (default: "small")
        language: Language code (default: "en" for English)
    
    Returns:
        str: Transcribed text or empty string if error
    """
    
    if not os.path.exists(file_path):
        print(f"[Whisper] Error: File not found: {file_path}")
        return ""
    
    print(f"[Whisper] Transcribing: {file_path}")
    print(f"[Whisper] Model: {model_size}, Language: {language}")
    
    try:
        # Start timer
        start_time = time.time()
        
        # Load model (optimized for Raspberry Pi CPU)
        model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",  # Fastest on CPU
            cpu_threads=4,        # Use 4 CPU threads
            num_workers=1,
            download_root="./whisper_models"  # Save models locally
        )
        
        load_time = time.time() - start_time
        print(f"[Whisper] Model loaded in {load_time:.1f}s")
        
        # Transcribe the audio
        transcribe_start = time.time()
        
        # Options optimized for 5-second audio
        segments, info = model.transcribe(
            file_path,
            language=language,
            beam_size=3,           # Smaller = faster
            best_of=3,             # Smaller = faster
            temperature=0.0,       # Deterministic
            vad_filter=True,       # Remove silence
            vad_parameters={
                "min_silence_duration_ms": 300,
                "speech_pad_ms": 200
            },
            word_timestamps=False, # Disable for speed
            suppress_blank=True,
            without_timestamps=True,
            max_initial_timestamp=5.0  # For 5-second audio
        )
        
        # Collect all text
        transcription_parts = []
        for segment in segments:
            transcription_parts.append(segment.text.strip())
        
        # Join segments
        full_transcription = " ".join(transcription_parts).strip()
        
        transcribe_time = time.time() - transcribe_start
        total_time = time.time() - start_time
        
        print(f"[Whisper] Transcription time: {transcribe_time:.1f}s")
        print(f"[Whisper] Total time: {total_time:.1f}s")
        print(f"[Whisper] Result: {full_transcription}")
        
        return full_transcription
        
    except Exception as e:
        print(f"[Whisper] Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        return ""

def test_transcription():
    """Test function for quick verification"""
    test_file = "test_recording.wav"
    
    if os.path.exists(test_file):
        print("Testing transcription...")
        result = transcribe_wav_file(test_file)
        print(f"Test result: '{result}'")
        return result
    else:
        print(f"Test file {test_file} not found")
        return ""

if __name__ == "__main__":
    # Command line interface
    import argparse
    
    parser = argparse.ArgumentParser(description="Transcribe WAV file using faster-whisper")
    parser.add_argument("file", help="Path to WAV file")
    parser.add_argument("--model", default="small", 
                       choices=["tiny", "base", "small", "medium", "large-v2"],
                       help="Model size (default: small)")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    
    args = parser.parse_args()
    
    result = transcribe_wav_file(args.file, args.model, args.language)
    
    # Print just the result (for piping to other commands)
    if result:
        print("\n" + "="*50)
        print("TRANSCRIPTION:")
        print(result)
    else:
        print("\nTranscription failed")