import tkinter as tk
import calendar
from datetime import date
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
import pyaudio

# ============================================================================
# GLOBAL VARIABLES AND SHARED STATE
# ============================================================================
today = date.today()
year = today.year
month = today.month
day = today.day

# ----------------------------
# LED Setup
# ----------------------------
LED_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

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
fsr_is_active = False

# Thread-safe communication queues
fsr_event_queue = queue.Queue()
ui_command_queue = queue.Queue()

# Thread control flags
fsr_thread_running = True

# Tkinter references
root = None
frames = None

# Audio device - using your discovered device
AUDIO_DEVICE = "plughw:2,0"  # Your working audio device
audio_device_found = True
audio_device_name = AUDIO_DEVICE

# ============================================================================
# AUDIO DEVICE DETECTION
# ============================================================================
def check_audio_devices():
    """Check available audio devices"""
    global audio_device_found, audio_device_name
    
    print("\n" + "="*60)
    print("[Audio] AUDIO DEVICE CONFIGURATION")
    print("="*60)
    
    print(f"[Audio] Using specified device: {AUDIO_DEVICE}")
    
    # Test the device
    print(f"[Audio] Testing device: {AUDIO_DEVICE}")
    
    # Create a simple test recording
    test_file = "/tmp/audio_test.wav"
    test_command = f"arecord -d 2 -f S16_LE -r 16000 -c 1 -D {AUDIO_DEVICE} {test_file}"
    
    print(f"[Audio] Test command: {test_command}")
    
    try:
        # Try to record for 2 seconds
        print("[Audio] Starting 2-second test recording...")
        result = subprocess.run(test_command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[Audio] ✅ Test recording successful!")
            
            # Check if file was created
            if os.path.exists(test_file):
                file_size = os.path.getsize(test_file)
                print(f"[Audio] Test file created: {test_file} ({file_size} bytes)")
                
                # Try to play it back
                print("[Audio] Playing back test recording...")
                play_result = subprocess.run(f"aplay {test_file}", shell=True, capture_output=True, text=True)
                if play_result.returncode == 0:
                    print("[Audio] ✅ Playback successful!")
                else:
                    print(f"[Audio] Playback failed: {play_result.stderr[:100]}")
            else:
                print("[Audio] ⚠️ Test file not created")
        else:
            print(f"[Audio] ❌ Test recording failed: {result.stderr[:200]}")
            
            # Try alternative formats
            print("[Audio] Trying alternative audio formats...")
            formats = ['S16_LE', 'S32_LE', 'cd', 'dat']
            rates = [16000, 44100, 48000]
            
            for fmt in formats:
                for rate in rates:
                    alt_command = f"arecord -d 1 -f {fmt} -r {rate} -c 1 -D {AUDIO_DEVICE} /tmp/test_{fmt}_{rate}.wav 2>&1"
                    alt_result = subprocess.run(alt_command, shell=True, capture_output=True, text=True)
                    if alt_result.returncode == 0:
                        print(f"[Audio] ✅ Alternative works: format={fmt}, rate={rate}")
                        break
                else:
                    continue
                break
            
            audio_device_found = False
            
    except Exception as e:
        print(f"[Audio] Error testing device: {e}")
        audio_device_found = False
    
    # List all available devices for debugging
    print("\n[Audio] Listing all available audio devices:")
    try:
        # List with arecord -L
        list_result = subprocess.run(['arecord', '-L'], capture_output=True, text=True)
        if list_result.returncode == 0:
            lines = list_result.stdout.split('\n')
            for i, line in enumerate(lines[:20]):  # Show first 20 lines
                print(f"  {line}")
            if len(lines) > 20:
                print(f"  ... and {len(lines)-20} more lines")
    except Exception as e:
        print(f"[Audio] Error listing devices: {e}")
    
    print("="*60 + "\n")
    
    return audio_device_found

# ============================================================================
# TKINTER UI SETUP (Main Thread)
# ============================================================================
def setup_tkinter_ui():
    """Setup Tkinter UI on main thread"""
    global root, frames
    
    calendar.setfirstweekday(calendar.SUNDAY)
    
    root = tk.Tk()
    root.title("FSR Recording Test")
    
    # Set fixed screen size
    screen_width = 480
    screen_height = 320
    root.geometry(f"{screen_width}x{screen_height}")
    root.resizable(False, False)
    
    if audio_device_found:
        root.configure(bg="green")  # Green = ready
    else:
        root.configure(bg="orange")  # Orange = no audio device
    
    # GRID SETUP
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    
    # Container for all views
    container = tk.Frame(root, bg=root.cget('bg'))
    container.grid(row=0, column=0, sticky="nsew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    
    # Create a simple UI
    device_status = "✅ Audio: READY" if audio_device_found else "❌ Audio: DEVICE ERROR"
    
    test_label = tk.Label(
        container, 
        text="Touch FSR to start recording test\n(Will record for 5 seconds then exit)",
        bg=root.cget('bg'),
        fg="white",
        font=("Arial", 16, "bold"),
        wraplength=400
    )
    test_label.grid(row=0, column=0, sticky="nsew")
    
    status_label = tk.Label(
        container,
        text=f"Status: {device_status}\nDouble-tap FSR to begin",
        bg=root.cget('bg'),
        fg="white",
        font=("Arial", 14),
        wraplength=400
    )
    status_label.grid(row=1, column=0, sticky="nsew", pady=20)
    
    device_label = tk.Label(
        container,
        text=f"Device: {audio_device_name}",
        bg=root.cget('bg'),
        fg="yellow" if audio_device_found else "red",
        font=("Arial", 12),
        wraplength=400
    )
    device_label.grid(row=2, column=0, sticky="nsew")
    
    # Store frames for later access
    frames = {
        'container': container,
        'root': root,
        'test_label': test_label,
        'status_label': status_label,
        'device_label': device_label
    }
    
    # Start UI command processor
    root.after(100, process_ui_commands)
    
    return frames

def change_background_color(color, text="", status="", device_text=""):
    """Change background color and update text"""
    global frames
    
    if frames:
        frames['root'].configure(bg=color)
        frames['container'].configure(bg=color)
        frames['test_label'].configure(bg=color)
        frames['status_label'].configure(bg=color)
        frames['device_label'].configure(bg=color)
        
        if text:
            frames['test_label'].config(text=text)
        if status:
            frames['status_label'].config(text=status)
        if device_text:
            frames['device_label'].config(text=device_text)
            frames['device_label'].config(fg="yellow")

# ============================================================================
# THREAD 1: FSR MONITORING (Separate Thread)
# ============================================================================
def fsr_monitoring_thread():
    """Monitor FSR sensor in separate thread"""
    global fsr_last_tap_time, fsr_tap_count, fsr_last_state, fsr_cooldown_until
    global fsr_is_active, fsr_thread_running
    
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
                    print(f"[FSR Thread] Double tap detected! Count: {fsr_tap_count}")
                    
                    # Double tap activates recording
                    if fsr_tap_count >= 2 and not fsr_is_active:
                        print("[FSR Thread] Double tap detected! Stopping threads and starting recording...")
                        fsr_is_active = True
                        
                        # Send event to UI thread
                        fsr_event_queue.put(('fsr_detected',))
                        
                        # Stop this thread
                        fsr_thread_running = False
                        fsr_tap_count = 0
                        fsr_cooldown_until = current_time + FSR_COOLDOWN
                        break  # Exit the thread loop
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
# AUDIO RECORDING FUNCTIONS
# ============================================================================
def record_audio():
    """Record audio for 5 seconds using the specified device"""
    print("\n" + "="*60)
    print("STARTING 5-SECOND AUDIO RECORDING")
    print(f"Using device: {AUDIO_DEVICE}")
    print("="*60 + "\n")
    
    # Update UI to show recording
    ui_command_queue.put(('change_color', 'red', '🎤 RECORDING...', 'Status: Recording audio for 5 seconds...'))
    
    # Turn on LED
    GPIO.output(LED_PIN, GPIO.HIGH)
    
    # Record for 5 seconds
    recording_file = "test_recording.wav"
    print(f"[Recording] Saving to: {recording_file}")
    
    # Use your working device parameter
    record_command = f"arecord -d 5 -f S16_LE -r 16000 -c 1 -D {AUDIO_DEVICE} {recording_file}"
    print(f"[Recording] Command: {record_command}")
    
    # Start recording
    start_time = time.time()
    print(f"[Recording] Starting at: {time.strftime('%H:%M:%S')}")
    
    # Run the recording command
    try:
        result = subprocess.run(record_command, shell=True, capture_output=True, text=True)
        end_time = time.time()
        
        recording_time = end_time - start_time
        print(f"[Recording] Recording finished at: {time.strftime('%H:%M:%S')}")
        print(f"[Recording] Duration: {recording_time:.2f} seconds")
        
        if result.returncode == 0:
            print("[Recording] ✅ Recording command successful!")
            
            # Check if file was created
            if os.path.exists(recording_file):
                file_size = os.path.getsize(recording_file)
                print(f"[Recording] 📁 File created: {recording_file}")
                print(f"[Recording] 📏 File size: {file_size} bytes ({file_size/1024:.1f} KB)")
                
                # Update UI
                ui_command_queue.put(('change_color', 'blue', '✅ Recording Complete!', 
                                      f'Status: Recorded {file_size} bytes\nPlaying back...'))
                
                # Play back the recording to verify
                print("[Recording] Playing back recording...")
                play_command = f"aplay {recording_file}"
                print(f"[Recording] Play command: {play_command}")
                
                play_result = subprocess.run(play_command, shell=True, capture_output=True, text=True)
                if play_result.returncode == 0:
                    print("[Recording] ✅ Playback successful!")
                    ui_command_queue.put(('change_color', 'green', '🎵 Playback Complete!', 
                                          'Status: Recording and playback successful!'))
                else:
                    print(f"[Recording] ❌ Playback failed: {play_result.stderr[:200]}")
                    ui_command_queue.put(('change_color', 'orange', '⚠️ Playback Failed', 
                                          f'Status: {play_result.stderr[:100]}'))
            else:
                print(f"[Recording] ❌ File not created: {recording_file}")
                ui_command_queue.put(('change_color', 'orange', '❌ Recording Failed', 
                                      'Status: File not created'))
        else:
            print(f"[Recording] ❌ Recording command failed!")
            print(f"[Recording] Error code: {result.returncode}")
            print(f"[Recording] stderr: {result.stderr[:500]}")
            ui_command_queue.put(('change_color', 'orange', '❌ Recording Failed', 
                                  f'Status: {result.stderr[:100]}'))
            
    except Exception as e:
        print(f"[Recording] ❌ Exception during recording: {e}")
        import traceback
        traceback.print_exc()
        ui_command_queue.put(('change_color', 'orange', '❌ Recording Exception', 
                              f'Status: {str(e)[:100]}'))
    
    # Turn off LED
    GPIO.output(LED_PIN, GPIO.LOW)
    
    print("\n" + "="*60)
    print("RECORDING TEST COMPLETE")
    print("="*60 + "\n")
    
    # Wait a moment then exit
    time.sleep(2)
    ui_command_queue.put(('exit_app',))

# ============================================================================
# UI COMMAND PROCESSING (Main Thread)
# ============================================================================
def process_ui_commands():
    """Process commands from other threads (runs in main thread)"""
    global root, frames
    
    try:
        # Process UI commands
        while not ui_command_queue.empty():
            command = ui_command_queue.get_nowait()
            
            if command[0] == 'change_color':
                color = command[1]
                text = command[2] if len(command) > 2 else ""
                status = command[3] if len(command) > 3 else ""
                device_text = command[4] if len(command) > 4 else ""
                change_background_color(color, text, status, device_text)
                
            elif command[0] == 'exit_app':
                print("[UI Thread] Exiting application...")
                cleanup_and_exit()
                return  # Exit the function
                
    except queue.Empty:
        pass
    
    # Process FSR events
    try:
        while not fsr_event_queue.empty():
            event = fsr_event_queue.get_nowait()
            
            if event[0] == 'fsr_detected':
                print("[UI Thread] FSR detected - stopping threads and starting recording")
                
                # Change UI to indicate detection
                change_background_color('yellow', '✅ FSR Detected!', 'Status: Preparing to record...')
                
                # Schedule recording to start after a brief delay
                root.after(1000, start_recording_sequence)
                
    except queue.Empty:
        pass
    
    # Schedule next check if root still exists
    if root and root.winfo_exists():
        root.after(100, process_ui_commands)

def start_recording_sequence():
    """Start the recording sequence"""
    print("[UI Thread] Starting recording sequence...")
    
    # Update UI
    change_background_color('orange', 'Starting recording in 3...', 'Status: Get ready to speak...')
    
    # Countdown
    def countdown(remaining):
        if remaining > 0:
            change_background_color('orange', f'Starting recording in {remaining}...', 'Status: Get ready to speak...')
            root.after(1000, lambda: countdown(remaining - 1))
        else:
            # Start recording in a separate thread to not block UI
            change_background_color('red', '🎤 RECORDING NOW!', 'Status: Speak now! Recording...')
            recording_thread = threading.Thread(target=record_audio, daemon=True)
            recording_thread.start()
    
    countdown(3)

# ============================================================================
# CLEANUP AND EXIT
# ============================================================================
def cleanup_and_exit():
    """Cleanup and exit the application"""
    global fsr_thread_running, root
    
    print("\n[Cleanup] Cleaning up resources...")
    
    # Stop threads
    fsr_thread_running = False
    
    # Cleanup GPIO
    GPIO.cleanup()
    
    # Destroy Tkinter window
    if root and root.winfo_exists():
        root.after(1000, root.destroy)  # Give time for UI updates
    
    print("[Cleanup] Exiting application")
    
    # Exit the program
    import sys
    sys.exit(0)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    """Main function to start the test"""
    print("="*70)
    print("FSR TOUCH RECORDING TEST")
    print("="*70)
    print(f"Audio Device: {AUDIO_DEVICE}")
    print("\nInstructions:")
    print("1. Double-tap the FSR sensor quickly")
    print("2. UI will change colors to indicate status")
    print("3. After 3-second countdown, 5-second recording starts")
    print("4. Recording will play back automatically")
    print("5. App will exit automatically")
    print("="*70)
    
    # Check audio devices
    check_audio_devices()
    
    if not audio_device_found:
        print("❌ Audio device test failed!")
        print("Please check your audio configuration.")
        print("Try running: arecord -L")
        return
    
    # Setup Tkinter UI
    frames = setup_tkinter_ui()
    
    # Setup cleanup on window close
    frames['root'].protocol("WM_DELETE_WINDOW", cleanup_and_exit)
    
    # Start FSR monitoring thread
    print("\n[Main] Starting FSR monitoring thread...")
    fsr_thread = threading.Thread(target=fsr_monitoring_thread, daemon=False)  # Not daemon so we can join it
    fsr_thread.start()
    
    # Start main loop
    print("\n[Main] Starting Tkinter main loop...")
    print("[Main] Double-tap FSR to begin test\n")
    
    try:
        frames['root'].mainloop()
        
        # Wait for FSR thread to finish if it's still running
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