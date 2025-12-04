import os
import sys
import zipfile
import requests
import vosk
import json
import pyaudio
import time
import re

print("=" * 60)
print("🎤 SEKAI Wake Word Detector with Vosk - HEY GIRL")
print("=" * 60)

class SekaiDetector:
    def __init__(self, model_name="vosk-model-small-en-us-0.22"):
        self.model_name = model_name
        self.model_path = self.download_or_find_model()
        
        print(f"\n📦 Loading Vosk model...")
        try:
            self.model = vosk.Model(self.model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            print(f"✅ Model loaded: {self.model_name}")
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            print("\n💡 Try downloading manually:")
            print("   1. Go to: https://alphacephei.com/vosk/models")
            print("   2. Download: vosk-model-small-en-us-0.22.zip")
            print("   3. Extract to current directory")
            sys.exit(1)
    
    def download_or_find_model(self):
        """Download model if not found, or find existing one"""
        
        # Check common locations
        possible_paths = [
            self.model_name,
            f"./{self.model_name}",
            f"../{self.model_name}",
            f"vosk-model-small-en-us-0.15",  # Older version
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ Found model at: {path}")
                return path
        
        # No model found - download it
        print(f"❌ Model '{self.model_name}' not found locally")
        response = input("\n📥 Download model now? (42MB) [y/N]: ").strip().lower()
        
        if response == 'y':
            return self.download_model()
        else:
            print("\n❌ Model required. Exiting.")
            sys.exit(1)
    
    def download_model(self):
        """Download Vosk model"""
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.22.zip"
        zip_file = "vosk-model-small-en-us-0.22.zip"
        model_dir = "vosk-model-small-en-us-0.22"
        
        print(f"\n📥 Downloading model (42MB)...")
        print(f"   URL: {model_url}")
        print("   This may take a few minutes...")
        
        try:
            # Download
            response = requests.get(model_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(zip_file, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Progress
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"   Progress: {percent:.1f}%", end="\r")
            
            print("\n✅ Download complete!")
            
            # Extract
            print(f"📦 Extracting {zip_file}...")
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # Clean up
            os.remove(zip_file)
            
            print(f"✅ Model extracted to: {model_dir}")
            return model_dir
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            print("\n💡 Manual download instructions:")
            print(f"   1. Open: {model_url}")
            print("   2. Download the ZIP file")
            print("   3. Extract to current directory")
            print("   4. Make sure folder exists: 'vosk-model-small-en-us-0.22'")
            sys.exit(1)
    
    def contains_hey_girl(self, text):
        """Check if text contains 'hey girl' phonetically"""
        text_lower = text.lower()
        
        # Exact matches
        exact_matches = [
            "hey girl",
            "hey girl",  # doubled for emphasis
            "hey girly",
            "hay girl",
            "hey gal",
            "hey gurl",
            "hey grill",
            "hey girlie",
            "hey girls",
        ]
        
        for phrase in exact_matches:
            if phrase in text_lower:
                return True
        
        # Common mishearings by Vosk for "hey"
        hey_patterns = [
            "hey",
            "hay",
            "he",
            "hai",
            "heh",
            "hee",
            "a",
            "eh",
            "ay",
        ]
        
        # Common mishearings for "girl"
        girl_patterns = [
            "girl",
            "gurl",
            "grill",
            "girly",
            "girls",
            "garl",
            "gal",
            "gerl",
            "gull",
            "gir",
            "garl",
            "go",
            "gur",
            "gil",
            "girls",
            "girly",
            "girlish",
        ]
        
        # Check for combinations
        words = text_lower.split()
        
        for i in range(len(words) - 1):
            current_word = words[i]
            next_word = words[i + 1]
            
            # Check if current word sounds like "hey"
            is_hey_like = any(
                pattern in current_word or 
                current_word.startswith(pattern[:2]) or 
                current_word.endswith(pattern[-2:]) or
                pattern.startswith(current_word[:2])
                for pattern in hey_patterns
            )
            
            # Check if next word sounds like "girl"
            is_girl_like = any(
                pattern in next_word or 
                next_word.startswith(pattern[:2]) or 
                next_word.endswith(pattern[-2:]) or
                pattern.startswith(next_word[:2])
                for pattern in girl_patterns
            )
            
            if is_hey_like and is_girl_like:
                # Additional check: words should be reasonably close
                if len(current_word) >= 2 and len(next_word) >= 3:
                    return True
        
        # Check with simple regex patterns
        hey_girl_patterns = [
            r"hey\s+g[ieaou][rl]{2,3}",  # hey + g + vowel + rl/ll
            r"hay\s+g[ieaou][rl]{2,3}",
            r"he\s+g[ieaou][rl]{2,3}",
            r"hai\s+g[ieaou][rl]{2,3}",
            r"a\s+g[ieaou][rl]{2,3}",
            r"eh\s+g[ieaou][rl]{2,3}",
            r"ay\s+g[ieaou][rl]{2,3}",
            r"hey\s+g[a-z]*rl",  # hey + anything ending with rl
            r"hey\s+g[a-z]*l$",  # hey + anything ending with l
        ]
        
        for pattern in hey_girl_patterns:
            if re.search(pattern, text_lower):
                return True
        
        # Check for single word variations (might be misheard as one word)
        single_word_variations = [
            "heygirl",
            "haygirl",
            "heygurl",
            "haygurl",
            "heygirls",
            "heygirly",
        ]
        
        for variation in single_word_variations:
            if variation in text_lower:
                return True
        
        # Phonetic matching
        # "hey girl" phonetically could be: /heɪ gɝl/
        # Common approximations: "hay gurl", "hey garl", "he gir", etc.
        phonetic_patterns = [
            r"h[aeiouy][\s\-\.]?g[aeiou]r?l",  # h + vowel + g + vowel + r?l
            r"h[aeiouy]+\s?g[aeiou]+r?[le]+",  # h + vowels + g + vowels + r? + le
            r"[ae]?\s?g[aeiou]r?l",  # "a girl", "e girl"
        ]
        
        for pattern in phonetic_patterns:
            if re.search(pattern, text_lower):
                # Check if it's likely "hey girl" and not something else
                match = re.search(pattern, text_lower)
                if match:
                    matched_text = match.group(0)
                    # Simple check: should contain 'g' followed by vowel
                    if 'g' in matched_text and any(vowel in matched_text for vowel in 'aeiou'):
                        # Don't match things like "how are you" or "hi there"
                        not_patterns = [
                            "how are",
                            "hi there",
                            "hello",
                            "good morning",
                            "good day",
                        ]
                        if not any(np in text_lower for np in not_patterns):
                            return True
        
        return False
    
    def list_audio_devices(self):
        """List available audio devices"""
        pa = pyaudio.PyAudio()
        
        print("\n🎤 Available audio devices:")
        input_devices = []
        
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append(i)
                print(f"  [{i}] {info['name']}")
                print(f"      Channels: {info['maxInputChannels']}")
        
        pa.terminate()
        return input_devices
    
    def start_listening(self, device_index=None):
        """Start listening for 'hey girl'"""
        
        pa = pyaudio.PyAudio()
        
        # If no device specified, list and ask
        if device_index is None:
            input_devices = self.list_audio_devices()
            
            if not input_devices:
                print("❌ No audio input devices found!")
                pa.terminate()
                return
            
            try:
                device_index = int(input("\n🎯 Select device number: "))
                if device_index not in input_devices:
                    print(f"⚠️  Device {device_index} may not work")
            except:
                device_index = input_devices[0]
                print(f"⚠️  Using default device: {device_index}")
        
        # Get device info to check available channels
        device_info = pa.get_device_info_by_index(device_index)
        print(f"\n✅ Using: [{device_index}] {device_info['name']}")
        
        # Get available input channels from device
        available_channels = int(device_info['maxInputChannels'])
        
        # Use mono (1 channel) if available, otherwise use whatever channels are available
        channels = 1 if available_channels >= 1 else available_channels
        
        if available_channels == 0:
            print(f"❌ Device has no input channels! Cannot use for recording.")
            pa.terminate()
            return
        
        print(f"📊 Device supports {available_channels} input channel(s)")
        print(f"📊 Using {channels} channel(s) for recording")
        
        # Open audio stream with CORRECT parameters
        stream = pa.open(
            rate=16000,                    # Vosk expects 16kHz, not 48kHz
            channels=channels,            # Use correct channel count
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=2048,
            input_device_index=device_index  # Use the selected device index
        )
        
        print(f"\n{'='*60}")
        print("👂 LISTENING FOR 'HEY GIRL'")
        print("   Say clearly: 'HEY GIRL'")
        print("   Common variations: 'HAY GURL', 'HEY GURLY', 'HEY GIRLIE'")
        print("   Press Ctrl+C to stop")
        print('='*60 + '\n')
        
        detection_count = 0
        
        try:
            while True:
                # Read audio
                data = stream.read(2048, exception_on_overflow=False)
                
                # Process with Vosk
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()
                    
                    if text:
                        print(f"📝 Vosk heard: '{text}'")
                        
                        if self.contains_hey_girl(text):
                            detection_count += 1
                            print(f"\n{'🎯'*20}")
                            print(f"🎯 'HEY GIRL' DETECTED! (#{detection_count})")
                            print(f"🎯 Time: {time.strftime('%H:%M:%S')}")
                            print(f"🎯 Original: '{text}'")
                            print(f"{'🎯'*20}\n")
                            
                            # Robot activation
                            self.on_hey_girl_detected()
                
                # Check partial results for live feedback
                partial = json.loads(self.recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text:
                    print(f"   Processing: '{partial_text}'", end="\r")
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Stopped by user")
            print(f"📊 Total detections: {detection_count}")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            print("✅ Cleanup complete")
    
    def on_hey_girl_detected(self):
        """What happens when 'hey girl' is detected"""
        print("👧 [SEKAI] Hey there! You called?")
        print("   *Activates robot mode*")
        print("   *Shows happy face*")
        print("   *Lights up LED*")
        
        # Add your robot actions here:
        # 1. Play greeting sound
        # 2. Show robot face on screen
        # 3. Turn on LED
        # 4. Start listening for commands
        
        time.sleep(2)  # Cooldown period

# ================= MAIN =================
if __name__ == "__main__":
    # Check for required packages
    try:
        import pyaudio
    except ImportError:
        print("❌ PyAudio not installed!")
        print("💡 Install with: pip install pyaudio")
        sys.exit(1)
    
    try:
        import requests
    except ImportError:
        print("❌ Requests not installed!")
        print("💡 Install with: pip install requests")
        sys.exit(1)
    
    # Create and start detector
    detector = SekaiDetector()
    
    # Ask if user wants to select device
    print("\n" + "="*60)
    print("⚙️  CONFIGURATION")
    print("="*60)
    
    select_device = input("\nSelect audio device? [y/N]: ").strip().lower()
    
    if select_device == 'y':
        detector.start_listening()  # Will show device list
    else:
        detector.start_listening(device_index=0)  # Use default