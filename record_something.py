import tkinter as tk
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import RPi.GPIO as GPIO
import threading
import os
import queue
import subprocess
from PIL import Image, ImageTk

# ============================================================================
# GLOBAL VARIABLES AND SHARED STATE
# ============================================================================

# ----------------------------
# LED Setup
# ----------------------------
LED_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)  # Start with LED off

# ----------------------------
# I2C Setup for ADS1115
# ----------------------------
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)

# ----------------------------
# FSR on channel 0 (A0)
# ----------------------------
fsr_channel = AnalogIn(ads, 0)

# ----------------------------
# FSR Thresholds
# ----------------------------
FSR_THRESHOLD = 100
FSR_DOUBLE_TAP_TIMEOUT = 0.5
FSR_COOLDOWN = 2.0

# FSR state tracking
fsr_last_tap_time = 0
fsr_tap_count = 0
fsr_last_state = False
fsr_cooldown_until = 0

# Thread-safe communication queue
fsr_event_queue = queue.Queue()
ui_command_queue = queue.Queue()

# Thread control flag
fsr_thread_running = True

# Tkinter references
root = None
face_label = None
current_mood = "happy"
current_photo = None

# Screen dimensions
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

# Audio device (update if needed)
AUDIO_DEVICE = "plughw:2,0"

# Image cache
image_cache = {}

# ============================================================================
# IMAGE LOADING FUNCTIONS
# ============================================================================

def load_face_image(mood):
    """Load face image from sekai_faces folder"""
    global image_cache
    
    # Check cache first
    if mood in image_cache:
        return image_cache[mood]
    
    # Try to find the image file
    sekai_faces_dir = "sekai_faces"
    
    # Possible filenames for each mood
    mood_files = {
        'happy': ['happy.jpg', 'happy.JPG', 'hapy.jpg', 'smile.jpg'],
        'angry': ['angry.jpg', 'angry.JPG', 'mad.jpg'],
        'recording': ['recording.jpg', 'listen.jpg', 'microphone.jpg']
    }
    
    image_path = None
    
    if mood in mood_files:
        for filename in mood_files[mood]:
            test_path = os.path.join(sekai_faces_dir, filename)
            if os.path.exists(test_path):
                image_path = test_path
                print(f"[Image] Found {mood} image: {filename}")
                break
    
    if not image_path:
        # If no image found, create a colored fallback
        print(f"[Image] No image found for {mood}, using fallback")
        return create_fallback_image(mood)
    
    try:
        # Load and resize image
        img = Image.open(image_path)
        
        # Calculate scaling to fit screen while maintaining aspect ratio
        img_width, img_height = img.size
        screen_ratio = SCREEN_WIDTH / SCREEN_HEIGHT
        img_ratio = img_width / img_height
        
        if img_ratio > screen_ratio:
            # Image is wider than screen
            new_width = SCREEN_WIDTH
            new_height = int(SCREEN_WIDTH / img_ratio)
        else:
            # Image is taller than screen
            new_height = SCREEN_HEIGHT
            new_width = int(SCREEN_HEIGHT * img_ratio)
        
        # Resize with high-quality filtering
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(img)
        
        # Cache the image
        image_cache[mood] = photo
        
        print(f"[Image] Loaded {mood} image: {img_width}x{img_height} -> {new_width}x{new_height}")
        return photo
        
    except Exception as e:
        print(f"[Image] Error loading {mood} image: {e}")
        return create_fallback_image(mood)

def create_fallback_image(mood):
    """Create a fallback image if real image not found"""
    colors = {
        'happy': '#4CAF50',  # Green
        'angry': '#F44336',  # Red
        'recording': '#FF9800'  # Orange
    }
    
    color = colors.get(mood, '#9E9E9E')  # Gray as default
    
    # Create a simple colored image with text
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color)
    
    try:
        # Try to add text
        from PIL import ImageDraw, ImageFont
        
        draw = ImageDraw.Draw(img)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
            except:
                font = ImageFont.load_default()
        
        text = f"Sekai is {mood}"
        
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        x = (SCREEN_WIDTH - text_width) // 2
        y = (SCREEN_HEIGHT - text_height) // 2
        
        draw.text((x, y), text, fill="white", font=font)
        
    except Exception as e:
        print(f"[Image] Error creating fallback: {e}")
    
    photo = ImageTk.PhotoImage(img)
    return photo

# ============================================================================
# MODULAR DISPLAY FUNCTIONS
# ============================================================================

def show_happy_face():
    """Show happy face - call this function"""
    global current_mood, current_photo
    print("[UI] Showing happy face")
    current_mood = "happy"
    update_face_display("happy")
    return True

def show_angry_face():
    """Show angry face - call this function"""
    global current_mood, current_photo
    print("[UI] Showing angry face")
    current_mood = "angry"
    update_face_display("angry")
    return True

def show_recording_face():
    """Show recording face - call this function"""
    print("[UI] Showing recording face")
    update_face_display("recording")
    return True

def update_face_display(mood):
    """Update the face display with current mood"""
    global face_label, current_photo
    
    if face_label and face_label.winfo_exists():
        # Load the appropriate image
        photo = load_face_image(mood)
        
        if photo:
            # Update the label with the image
            face_label.config(image=photo, bg="black")
            face_label.image = photo  # Keep a reference!
            current_photo = photo
            
            # Add text overlay for recording
            if mood == "recording":
                # Add text label on top of image
                face_label.config(text="🎤 RECORDING\nSpeak now!", 
                                compound="center",
                                fg="white",
                                font=("Arial", 24, "bold"),
                                bg="black")
            else:
                # Clear text for other moods
                face_label.config(text="", compound="center")

# ============================================================================
# AUDIO RECORDING FUNCTIONS
# ============================================================================

def record_audio():
    """Record audio for 5 seconds with flashing LED"""
    print("\n" + "="*50)
    print("STARTING 5-SECOND AUDIO RECORDING")
    print("="*50)
    
    # Show recording face
    ui_command_queue.put(('show_face', 'recording'))
    
    # Start LED flashing in a separate thread
    flash_thread = threading.Thread(target=flash_led_while_recording, daemon=True)
    flash_thread.start()
    
    # Record for 5 seconds
    recording_file = "test_recording.wav"
    print(f"[Recording] Saving to: {recording_file}")
    
    # Record command with your audio device
    record_command = f"arecord -d 5 -f S16_LE -r 16000 -c 1 -D {AUDIO_DEVICE} {recording_file}"
    print(f"[Recording] Command: {record_command}")
    
    # Start recording
    start_time = time.time()
    print(f"[Recording] Starting recording at: {time.strftime('%H:%M:%S')}")
    
    try:
        # This runs in the recording thread, blocks for 5 seconds
        result = subprocess.run(record_command, shell=True, capture_output=True, text=True)
        end_time = time.time()
        
        recording_time = end_time - start_time
        print(f"[Recording] Recording finished at: {time.strftime('%H:%M:%S')}")
        print(f"[Recording] Duration: {recording_time:.2f} seconds")
        
        if result.returncode == 0:
            print("[Recording] ✅ Recording successful!")
            
            if os.path.exists(recording_file):
                file_size = os.path.getsize(recording_file)
                print(f"[Recording] 📁 File size: {file_size} bytes")
                
                # Play back the recording
                print("[Recording] Playing back recording...")
                play_command = f"aplay {recording_file}"
                play_result = subprocess.run(play_command, shell=True, capture_output=True, text=True)
                
                if play_result.returncode == 0:
                    print("[Recording] ✅ Playback successful!")
                else:
                    print(f"[Recording] ❌ Playback failed: {play_result.stderr[:100]}")
            else:
                print(f"[Recording] ❌ File not created")
        else:
            print(f"[Recording] ❌ Recording failed!")
            print(f"[Recording] Error: {result.stderr[:200]}")
            
    except Exception as e:
        print(f"[Recording] ❌ Exception: {e}")
    
    # Stop LED flashing and turn off
    ui_command_queue.put(('stop_led',))
    
    print("\n" + "="*50)
    print("RECORDING COMPLETE")
    print("="*50 + "\n")
    
    # Return to happy face after a delay
    ui_command_queue.put(('delayed_happy',))

def flash_led_while_recording():
    """Flash LED while recording is in progress"""
    print("[LED] Starting LED flash pattern")
    
    try:
        flash_duration = 5.0  # Match recording duration
        start_time = time.time()
        
        while time.time() - start_time < flash_duration:
            # Flash pattern: on for 0.2s, off for 0.2s
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.2)
            
    except Exception as e:
        print(f"[LED] Error in flash thread: {e}")
    finally:
        # Ensure LED is off
        GPIO.output(LED_PIN, GPIO.LOW)

# ============================================================================
# THREAD 1: FSR MONITORING (Separate Thread)
# ============================================================================

def fsr_monitoring_thread():
    """Monitor FSR sensor in separate thread"""
    global fsr_last_tap_time, fsr_tap_count, fsr_last_state, fsr_cooldown_until
    global fsr_thread_running
    
    print("[FSR Thread] Starting FSR monitoring...")
    
    while fsr_thread_running:
        try:
            current_time = time.time()
            fsr_value = fsr_channel.value
            
            # Check if we're in cooldown period
            if current_time < fsr_cooldown_until:
                fsr_last_state = False
                time.sleep(0.05)
                continue
            
            # Check if FSR is being pressed
            fsr_pressed = fsr_value > FSR_THRESHOLD
            
            # Detect press start (rising edge)
            if fsr_pressed and not fsr_last_state:
                print(f"[FSR Thread] FSR pressed: {fsr_value}")
                fsr_last_state = True
                
                # Check for double tap
                time_since_last_tap = current_time - fsr_last_tap_time
                
                if time_since_last_tap < FSR_DOUBLE_TAP_TIMEOUT:
                    fsr_tap_count += 1
                    print(f"[FSR Thread] Double tap count: {fsr_tap_count}")
                    
                    # Double tap detected - start recording sequence
                    if fsr_tap_count >= 2:
                        print("[FSR Thread] ✅ Double tap detected! Starting recording...")
                        
                        # Send event to UI thread
                        fsr_event_queue.put(('fsr_detected',))
                        
                        # Reset for next time
                        fsr_tap_count = 0
                        fsr_cooldown_until = current_time + FSR_COOLDOWN
                else:
                    # First tap
                    fsr_tap_count = 1
                    print("[FSR Thread] First tap detected")
                
                fsr_last_tap_time = current_time
            
            # Detect release (falling edge)
            elif not fsr_pressed and fsr_last_state:
                fsr_last_state = False
                print("[FSR Thread] FSR released")
            
            # Reset tap count if too much time has passed
            if current_time - fsr_last_tap_time > FSR_DOUBLE_TAP_TIMEOUT * 2:
                if fsr_tap_count > 0:
                    print(f"[FSR Thread] Tap timeout - resetting")
                    fsr_tap_count = 0
            
            time.sleep(0.05)  # 50ms sampling rate
            
        except Exception as e:
            print(f"[FSR Thread] Error: {e}")
            time.sleep(0.1)
    
    print("[FSR Thread] Thread stopped")

# ============================================================================
# UI COMMAND PROCESSING (Main Thread)
# ============================================================================

def process_ui_commands():
    """Process commands from other threads (runs in main thread)"""
    global root
    
    # Process UI commands
    try:
        while not ui_command_queue.empty():
            command = ui_command_queue.get_nowait()
            
            if command[0] == 'show_face':
                mood = command[1]
                if mood == 'happy':
                    show_happy_face()
                elif mood == 'angry':
                    show_angry_face()
                elif mood == 'recording':
                    show_recording_face()
                    
            elif command[0] == 'stop_led':
                GPIO.output(LED_PIN, GPIO.LOW)
                print("[UI] LED turned off")
                
            elif command[0] == 'delayed_happy':
                # Return to happy face after 2 seconds
                if root and root.winfo_exists():
                    root.after(2000, show_happy_face)
                    
    except queue.Empty:
        pass
    
    # Process FSR events
    try:
        while not fsr_event_queue.empty():
            event = fsr_event_queue.get_nowait()
            
            if event[0] == 'fsr_detected':
                print("[UI Thread] FSR double-tap detected!")
                
                # Show angry face immediately
                show_angry_face()
                
                # Start recording after 3 seconds
                if root and root.winfo_exists():
                    root.after(3000, start_recording)
                
    except queue.Empty:
        pass
    
    # Schedule next check
    if root and root.winfo_exists():
        root.after(100, process_ui_commands)

def start_recording():
    """Start the recording sequence"""
    print("[UI Thread] Starting recording sequence...")
    
    # Start recording in a separate thread
    recording_thread = threading.Thread(target=record_audio, daemon=True)
    recording_thread.start()

# ============================================================================
# TKINTER UI SETUP
# ============================================================================

def setup_tkinter_ui():
    """Setup Tkinter UI on main thread"""
    global root, face_label
    
    root = tk.Tk()
    root.title("Sekai Face Test")
    
    # Set fixed screen size
    root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    root.resizable(False, False)
    root.configure(bg="black")
    
    # Single frame for face display
    container = tk.Frame(root, bg="black")
    container.grid(row=0, column=0, sticky="nsew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    
    # Face label (will display images)
    face_label = tk.Label(
        container,
        bg="black"
    )
    face_label.grid(row=0, column=0, sticky="nsew")
    
    # Start with happy face
    show_happy_face()
    
    # Start UI command processor
    root.after(100, process_ui_commands)
    
    return root

# ============================================================================
# CLEANUP AND EXIT
# ============================================================================

def cleanup_and_exit():
    """Cleanup and exit the application"""
    global fsr_thread_running
    
    print("\n[Cleanup] Cleaning up resources...")
    
    # Stop FSR thread
    fsr_thread_running = False
    
    # Cleanup GPIO
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
    
    # Destroy Tkinter window
    if root and root.winfo_exists():
        root.destroy()
    
    print("[Cleanup] Exiting application")
    
    # Exit the program
    import sys
    sys.exit(0)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main function to start the test"""
    print("="*60)
    print("SEKAI FACE & RECORDING TEST")
    print("="*60)
    print("Image files expected in: sekai_faces/")
    print("Expected: happy.jpg, angry.jpg")
    print("\nInstructions:")
    print("1. App starts with happy face")
    print("2. Double-tap FSR sensor quickly")
    print("3. Face changes to angry face for 3 seconds")
    print("4. Recording starts - shows recording indicator")
    print("5. LED flashes while recording (5 seconds)")
    print("6. Recording plays back automatically")
    print("7. Returns to happy face")
    print("="*60)
    
    # Check if image directory exists
    if not os.path.exists("sekai_faces"):
        print("❌ ERROR: 'sekai_faces' directory not found!")
        print("Please create a 'sekai_faces' folder with:")
        print("  - happy.jpg")
        print("  - angry.jpg")
        return
    
    # List files in sekai_faces for debugging
    print("[Main] Files in sekai_faces directory:")
    try:
        files = os.listdir("sekai_faces")
        for file in files:
            print(f"  - {file}")
    except Exception as e:
        print(f"  Error listing files: {e}")
    
    # Setup Tkinter UI
    root = setup_tkinter_ui()
    
    # Setup cleanup on window close
    root.protocol("WM_DELETE_WINDOW", cleanup_and_exit)
    
    # Start FSR monitoring thread
    print("\n[Main] Starting FSR monitoring thread...")
    fsr_thread = threading.Thread(target=fsr_monitoring_thread, daemon=False)
    fsr_thread.start()
    
    # Start main loop
    print("\n[Main] Starting Tkinter main loop...")
    print("[Main] Double-tap FSR to begin recording test\n")
    
    try:
        root.mainloop()
        
        # Wait for FSR thread to finish
        if fsr_thread.is_alive():
            print("[Main] Waiting for FSR thread to finish...")
            fsr_thread.join(timeout=2.0)
            
    except KeyboardInterrupt:
        print("\n[Main] Keyboard interrupt received")
        cleanup_and_exit()
    except Exception as e:
        print(f"\n[Main] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        cleanup_and_exit()

if __name__ == "__main__":
    main()