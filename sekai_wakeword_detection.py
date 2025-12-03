import pvporcupine
from pvrecorder import PvRecorder
import struct
import threading
import time
import os
import wave
import numpy as np

class SekaiVoiceAssistant:
    def __init__(self, access_key, ppn_file_path="hello-sec-ai_en_raspberry-pi_v3_0_0.ppn", test_mode=False):
        """
        Voice assistant with "hello sekai" wake word
        
        Args:
            access_key: Your Picovoice AccessKey
            ppn_file_path: Path to downloaded .ppn file
            test_mode: If True, only prints detection messages (no recording)
        """
        self.access_key = access_key
        self.ppn_file_path = ppn_file_path
        self.is_listening = False
        self.test_mode = test_mode
        
        if self.test_mode:
            print("🧪 TEST MODE ENABLED - Will only print detection messages")
        
        # Initialize wake word detector
        self.init_wake_detector()
        
        # Response tracking
        self.last_wake_time = 0
        self.wake_cooldown = 3  # seconds between detections
        
        print(f"✅ Sekai Voice Assistant initialized")
        print(f"   Wake word: 'hello sekai'")
        print(f"   Test mode: {test_mode}")
        
    def init_wake_detector(self):
        """Initialize Picovoice with custom wake word"""
        try:
            # Check if custom wake word file exists
            if not os.path.exists(self.ppn_file_path):
                print(f"❌ Wake word file not found: {self.ppn_file_path}")
                print("Please download from Picovoice Console")
                print("Falling back to 'computer' wake word")
                
                # Fallback to built-in wake word
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=["computer"],
                    sensitivities=[0.7]
                )
                print("⚠️  Using 'computer' instead of 'hello sekai' for testing")
            else:
                # Use custom "hello sekai" wake word
                print(f"📁 Loading wake word from: {self.ppn_file_path}")
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keyword_paths=[self.ppn_file_path],
                    sensitivities=[0.7]  # Adjust as needed
                )
            
            # Initialize audio recorder
            self.recorder = PvRecorder(
                device_index=-1,  # Auto-select microphone
                frame_length=self.porcupine.frame_length,
                buffer_size_msec=1000,
                log_overflow=False
            )
            
            # Get available devices for debugging
            print("\n🎤 Available audio devices:")
            devices = PvRecorder.get_available_devices()
            for idx, device in enumerate(devices):
                print(f"  {idx}: {device}")
                if "USB" in device or "mic" in device.lower():
                    print(f"    → Suggest using index {idx} for better quality")
            
            # Ask user to select device if multiple
            if len(devices) > 1:
                print(f"\n🔍 To use a specific device, enter its index (0-{len(devices)-1})")
                print("   Or press Enter to use auto-selection")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize wake detector: {e}")
            print("\n⚠️  Troubleshooting tips:")
            print("1. Check your Picovoice AccessKey")
            print("2. Make sure .ppn file is in the correct directory")
            print("3. Run: pip3 install --upgrade pvporcupine pvrecorder")
            print("4. Check audio permissions: sudo usermod -a -G audio $USER")
            print("5. Reboot after changing audio permissions")
            return False
    
    def on_wake_word_detected(self):
        """Called when "hello sekai" is detected"""
        current_time = time.time()
        
        # Prevent multiple rapid detections
        if current_time - self.last_wake_time < self.wake_cooldown:
            print(f"⏳ Cooldown active, ignoring wake word")
            return
        
        self.last_wake_time = current_time
        
        # SIMPLE TEST MODE: Just print detection
        print("\n" + "="*60)
        print("✅✅✅ WAKE WORD DETECTED! ✅✅✅")
        print("   You said: 'hello sekai'")
        print("   Microphone is working correctly!")
        print("="*60 + "\n")
        
        # If test mode, just print and return (no recording)
        if self.test_mode:
            # Also print timestamp for logging
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] Detection #{(self.detection_count if hasattr(self, 'detection_count') else 0) + 1}")
            
            # Count detections
            if not hasattr(self, 'detection_count'):
                self.detection_count = 0
            self.detection_count += 1
            
            # Don't record in test mode
            return
        
        # Original behavior (for when you integrate with main script)
        print(f"\n{'='*50}")
        print("🎯 HELLO SEKAI detected! Sekai is listening...")
        print(f"{'='*50}")
        
        # Play wake sound if available
        self.play_wake_sound()
        
        # Update GUI/robot state
        self.trigger_wake_actions()
        
        # Start command recording
        self.record_command()
    
    def play_wake_sound(self):
        """Play Sekai's wake sound"""
        try:
            # Try to play a sound response
            wake_sounds = [
                "sekai_faces/wake.mp3",
                "sekai_faces/wake.wav",
                "voices_happy/wake1.wav",
                "voices_happy/wake2.wav"
            ]
            
            for sound_file in wake_sounds:
                if os.path.exists(sound_file):
                    os.system(f"aplay {sound_file} 2>/dev/null || mpv {sound_file} --no-video 2>/dev/null")
                    print(f"🔊 Played wake sound: {sound_file}")
                    break
        except:
            pass  # Silent wake is okay
    
    def trigger_wake_actions(self):
        """Trigger robot wake-up actions"""
        # These should be connected to your main GUI
        print("🤖 Triggering wake actions:")
        print("  - Setting mood to 'happy'")
        print("  - Turning on LED")
        print("  - Showing face view")
        
        # Callbacks to main application (you'll connect these)
        if hasattr(self, 'on_wake_callback'):
            self.on_wake_callback()
    
    def record_command(self):
        """Record voice command after wake word"""
        print("\n🎤 Recording command (3 seconds)...")
        
        try:
            # Record for 3 seconds
            sample_rate = 16000
            duration = 3
            frames_to_record = int(sample_rate / self.porcupine.frame_length * duration)
            
            frames = []
            for i in range(frames_to_record):
                audio_frame = self.recorder.read()
                frames.append(audio_frame)
                
                # Show recording progress
                if i % 50 == 0:
                    progress = (i / frames_to_record) * 100
                    print(f"  Recording... {progress:.0f}%", end='\r')
            
            print("  Recording... 100%")
            
            # Save audio file for Whisper
            audio_data = np.concatenate(frames)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            audio_file = f"command_{timestamp}.wav"
            
            with wave.open(audio_file, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
            
            print(f"✅ Command saved: {audio_file}")
            
            # Process with Whisper (you'll add this)
            self.process_command_audio(audio_file)
            
        except Exception as e:
            print(f"❌ Command recording failed: {e}")
    
    def process_command_audio(self, audio_file):
        """Process recorded command with Whisper"""
        print(f"🤔 Processing command with Whisper...")
        
        # TODO: Add your Whisper integration here
        # For now, just simulate processing
        time.sleep(1)
        
        # Example command mapping
        commands = {
            "weather": "show_weather",
            "calendar": "show_calendar", 
            "time": "show_time",
            "happy": "set_happy_mood",
            "angry": "set_angry_mood",
            "sleep": "go_to_sleep"
        }
        
        # Simulated command recognition
        simulated_command = "weather"  # Replace with Whisper output
        
        if simulated_command in commands:
            print(f"📝 Recognized command: '{simulated_command}'")
            print(f"   Action: {commands[simulated_command]}")
            
            # Trigger the command action
            self.execute_command(commands[simulated_command])
        else:
            print("⚠️  Command not recognized")
    
    def execute_command(self, command_action):
        """Execute the recognized command"""
        print(f"🚀 Executing: {command_action}")
        
        # Callback to main application
        if hasattr(self, 'on_command_callback'):
            self.on_command_callback(command_action)
    
    def start_listening(self):
        """Start continuous wake word detection"""
        if not hasattr(self, 'porcupine'):
            print("❌ Detector not initialized")
            return
        
        print("\n👂 Starting wake word detection...")
        if self.test_mode:
            print("   TEST MODE: Say 'hello sekai' to test detection")
            print("   Each detection will print: 'WAKE WORD DETECTED!'")
        else:
            print("   Say 'hello sekai' to activate")
        print("   Press Ctrl+C to stop\n")
        
        # Show status indicator
        print("Status: ", end='', flush=True)
        
        self.is_listening = True
        self.recorder.start()
        
        try:
            frame_count = 0
            while self.is_listening:
                # Read audio frame
                pcm = self.recorder.read()
                
                # Convert format for Picovoice
                pcm = struct.pack("h" * len(pcm), *pcm)
                
                # Detect wake word
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    self.on_wake_word_detected()
                
                # Show listening status animation
                frame_count += 1
                if frame_count % 100 == 0:  # Update every 100 frames
                    status_chars = ["-", "\\", "|", "/"]
                    status = status_chars[(frame_count // 100) % 4]
                    print(f"\rStatus: Listening {status} ", end='', flush=True)
                
                # Small delay to prevent CPU hogging
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping by user request...")
        except Exception as e:
            print(f"\n❌ Listening error: {e}")
        finally:
            self.stop()
    
    def start_background_listening(self):
        """Start listening in background thread"""
        def listen_thread():
            self.start_listening()
        
        self.listener_thread = threading.Thread(target=listen_thread, daemon=True)
        self.listener_thread.start()
        print("✅ Wake word detection running in background")
    
    def stop(self):
        """Cleanup resources"""
        self.is_listening = False
        time.sleep(0.1)
        
        if hasattr(self, 'recorder') and self.recorder.is_recording:
            self.recorder.stop()
        
        print("✅ Voice assistant stopped")


# ============================================
# TEST SCRIPT - Run this to test your setup
# ============================================

def test_wake_word_detection():
    """
    Simple test function to verify wake word detection works
    """
    print("\n" + "="*70)
    print("🧪 HELLO SEKAI - WAKE WORD TEST")
    print("="*70)
    
    # Check for Picovoice AccessKey
    access_key = "VM996Z/2j8ghpUlIqlqxMmVAOxOHHCMujdWtGLAZ3i43Q0vTinykmg=="
    
    if not access_key:
        print("\n❌ No Picovoice AccessKey found!")
        print("Please set your AccessKey in one of these ways:")
        print("1. Export as environment variable:")
        print("   export PICOVOICE_ACCESS_KEY='your-key-here'")
        print("2. Enter it when prompted below")
        print("\nGet your free key from: https://console.picovoice.ai/")
        print("\nEnter your Picovoice AccessKey (or press Ctrl+C to cancel):")
        access_key = input("> ").strip()
        
        if not access_key:
            print("No key provided. Exiting.")
            return
    
    # Check for .ppn file
    ppn_files = []
    possible_names = [
        "hello-sec-ai_en_raspberry-pi_v3_0_0.ppn",
        "*.ppn",  # Any .ppn file
    ]
    
    for name in possible_names:
        if "*" in name:
            import glob
            ppn_files.extend(glob.glob(name))
        elif os.path.exists(name):
            ppn_files.append(name)
    
    if not ppn_files:
        print("\n⚠️  No .ppn wake word file found!")
        print("Please download 'hello_sekai_raspberry-pi.ppn' from Picovoice Console")
        print("and place it in this directory.")
        print("\nFor now, we'll test with built-in 'computer' wake word.")
        ppn_file = None
    else:
        ppn_file = ppn_files[0]
        print(f"\n📁 Found wake word file: {ppn_file}")
    
    # Run microphone test first
    print("\n" + "-"*70)
    print("🎤 MICROPHONE TEST")
    print("-"*70)
    
    try:
        # Quick test to see if we can access audio
        recorder = PvRecorder(device_index=-1, frame_length=512)
        devices = PvRecorder.get_available_devices()
        
        print(f"✓ Found {len(devices)} audio device(s):")
        for idx, device in enumerate(devices):
            indicator = " ← DEFAULT" if idx == -1 else ""
            print(f"  [{idx}] {device}{indicator}")
        
        recorder.delete()
        
    except Exception as e:
        print(f"✗ Microphone test failed: {e}")
        print("\n⚠️  Audio setup issues detected!")
        print("Try these fixes:")
        print("1. Check microphone is plugged in")
        print("2. Run: sudo raspi-config → Audio → Force 3.5mm jack")
        print("3. Reboot Raspberry Pi")
        return
    
    # Create assistant in TEST MODE
    print("\n" + "-"*70)
    print("🔊 WAKE WORD DETECTION TEST")
    print("-"*70)
    print("This will run for 60 seconds or until Ctrl+C is pressed.")
    print("Speak clearly and say 'hello sekai' (or 'computer' if using fallback).")
    print("You should see 'WAKE WORD DETECTED!' when it hears you.")
    print("-"*70 + "\n")
    
    try:
        assistant = SekaiVoiceAssistant(
            access_key=access_key,
            ppn_file_path=ppn_file if ppn_file else "dummy.ppn",
            test_mode=True  # <-- IMPORTANT: Test mode enabled!
        )
        
        # Set a timeout for the test
        test_duration = 60  # seconds
        
        def timeout_handler():
            print(f"\n\n⏰ Test timeout ({test_duration} seconds reached)")
            assistant.stop()
        
        # Start timeout timer
        timeout_timer = threading.Timer(test_duration, timeout_handler)
        timeout_timer.daemon = True
        timeout_timer.start()
        
        # Start listening
        assistant.start_listening()
        
    except KeyboardInterrupt:
        print("\n\n👋 Test stopped by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("\n💡 Troubleshooting tips:")
        print("1. Make sure your Picovoice AccessKey is correct")
        print("2. Check internet connection (needed for first-time setup)")
        print("3. Try: pip3 install --upgrade pvporcupine")
        print("4. Run: sudo usermod -a -G audio $USER && reboot")
    finally:
        print("\n" + "="*70)
        print("🧪 TEST COMPLETE")
        print("="*70)


# ============================================
# QUICK MICROPHONE CHECK SCRIPT
# ============================================

def quick_mic_check():
    """
    Very simple microphone check - no Picovoice needed
    """
    print("\n🔍 QUICK MICROPHONE CHECK")
    print("This will list available audio devices only.")
    
    try:
        from pvrecorder import PvRecorder
        devices = PvRecorder.get_available_devices()
        
        if not devices:
            print("❌ No audio devices found!")
            print("Check microphone connection and run:")
            print("  arecord -l  # Should list devices")
        else:
            print(f"✅ Found {len(devices)} audio device(s):")
            for idx, device in enumerate(devices):
                print(f"  [{idx}] {device}")
                
            print("\nTo test recording, run in terminal:")
            print("  arecord --duration=3 --format=cd test.wav")
            print("  aplay test.wav")
            
    except ImportError:
        print("❌ pvrecorder not installed. Run:")
        print("  pip3 install pvrecorder")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    import sys
    
    print("\n" + "="*70)
    print("🤖 SEKAI ROBOT - Voice Assistant Testing")
    print("="*70)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--mic-check":
            quick_mic_check()
            sys.exit(0)
        elif sys.argv[1] == "--help":
            print("\nUsage:")
            print("  python3 sekai_voice_test.py          # Full wake word test")
            print("  python3 sekai_voice_test.py --mic-check  # Quick microphone check")
            print("  python3 sekai_voice_test.py --help       # This message")
            sys.exit(0)
    
    # Run the full test
    test_wake_word_detection()