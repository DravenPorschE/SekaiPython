import requests
import os
from typecast_api import text_to_speech_api
from ai_talk import getSekaiResponse
from get_intent import getSekaiIntent
import json

current_mood = "happy"

def transcribe_wav_file(file_path, server_url="https://sekaiserver-production.up.railway.app"):
    """
    Simple function to transcribe a WAV file using the local server
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return None
    
    if not file_path.lower().endswith('.wav'):
        print(f"Error: Only WAV files are accepted: {file_path}")
        return None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'audio/wav')}
            response = requests.post(f"{server_url}/transcribe", files=files, timeout=300)
            
            if response.status_code == 200:
                return response.text.strip()
            else:
                print(f"Server error: {response.status_code} - {response.text}")
                return None
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to transcription server.")
        print("Make sure the server is running: python transcribe_server.py")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


# Quick usage example
if __name__ == "__main__":
    # Test the function
    result = transcribe_wav_file("testRecording.wav")
    
    if result:
        print("Transcription:")
        print(result)

        API_KEY = "__pltMzLwjRtejoHYcjCEi984cBgKa6qMU6EiSkEs2Xne "  # Replace with your actual API key
    
        # Test text
        #test_text = ai_response

        ai_intent = getSekaiIntent(result)

        print(ai_intent)
        data = json.loads(ai_intent)  # Parse JSON string to dictionary
        command_value = data["command"]  # Access the value

        ai_response = getSekaiResponse(result, current_mood)

        # Generate speech
        audio_file = text_to_speech_api(ai_response, API_KEY)
        
        if audio_file and os.path.exists(audio_file):
            print(f"\n🎵 To play the audio on Raspberry Pi:")
            print(f"   aplay {audio_file}")
            
            # Optional: Play it automatically
            import subprocess
            try:
                subprocess.run(['aplay', audio_file], check=True)
            except:
                print("   Could not play audio automatically")
        
        else:
            print("Transcription failed.")