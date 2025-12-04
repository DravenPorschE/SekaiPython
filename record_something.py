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
wake_detector_running = True

# Tkinter references
root = None
frames = None

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
    root.configure(bg="green")  # Start with green background
    
    # GRID SETUP
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    
    # Container for all views
    container = tk.Frame(root, bg="green")
    container.grid(row=0, column=0, sticky="nsew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    
    # Create a simple UI
    test_label = tk.Label(
        container, 
        text="Touch FSR to start recording test\n(Will record for 5 seconds then exit)",
        bg="green",
        fg="white",
        font=("Arial", 16, "bold")
    )
    test_label.grid(row=0, column=0, sticky="nsew")
    
    status_label = tk.Label(
        container,
        text="Status: Waiting for FSR touch...",
        bg="green",
        fg="white",
        font=("Arial", 14)
    )
    status_label.grid(row=1, column=0, sticky="nsew", pady=20)
    
    # Store frames for later access
    frames = {
        'container': container,
        'root': root,
        'test_label': test_label,
        'status_label': status_label
    }
    
    # Start UI command processor
    root.after(100, process_ui_commands)
    
    return frames

def change_background_color(color, text="", status=""):
    """Change background color and update text"""
    global frames
    
    if frames:
        frames['root'].configure(bg=color)
        frames['container'].configure(bg=color)
        frames['test_label'].configure(bg=color)
        frames['status_label'].configure(bg=color)
        
        if text:
            frames['test_label'].config(text=text)
        if status:
            frames['status_label'].config(text=status)

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
    """Record audio for 5 seconds"""
    print("\n" + "="*50)
    print("STARTING 5-SECOND AUDIO RECORDING TEST")
    print("="*50 + "\n")
    
    # Update UI to show recording
    ui_command_queue.put(('change_color', 'red', 'Recording... Press and hold FSR', 'Status: Recording audio for 5 seconds...'))
    
    # Turn on LED
    GPIO.output(LED_PIN, GPIO.HIGH)
    
    # Record for 5 seconds
    recording_file = "test_recording.wav"
    print(f"[Recording] Saving to: {recording_file}")
    
    # Using arecord with parameters suitable for audio
    arecord_command = f"arecord -d 5 -f S16_LE -t wav -r 16000 -c 1 {recording_file}"
    print(f"[Recording] Command: {arecord_command}")
    
    # Start recording
    start_time = time.time()
    return_code = os.system(arecord_command)
    end_time = time.time()
    
    # Turn off LED
    GPIO.output(LED_PIN, GPIO.LOW)
    
    if return_code == 0:
        recording_time = end_time - start_time
        print(f"[Recording] ✅ Recording finished in {recording_time:.2f} seconds")
        
        if os.path.exists(recording_file):
            file_size = os.path.getsize(recording_file)
            print(f"[Recording] 📁 File size: {file_size} bytes ({file_size/1024:.1f} KB)")
            
            # Play back the recording to verify
            print("[Recording] Playing back recording...")
            os.system(f"aplay {recording_file} 2>/dev/null")
            
            # Update UI
            ui_command_queue.put(('change_color', 'blue', 'Recording complete!', 
                                  f'Status: Recorded {file_size} bytes, playing back...'))
            time.sleep(3)  # Wait for playback to finish
            
        else:
            print(f"[Recording] ⚠️ File created but not found: {recording_file}")
            ui_command_queue.put(('change_color', 'orange', 'Recording error', 'Status: File not found'))
    else:
        print(f"[Recording] ❌ Recording failed with code: {return_code}")
        ui_command_queue.put(('change_color', 'orange', 'Recording failed', f'Status: Error code {return_code}'))
    
    print("\n" + "="*50)
    print("RECORDING TEST COMPLETE - EXITING APP")
    print("="*50 + "\n")
    
    # Exit the app
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
                change_background_color(color, text, status)
                
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
                change_background_color('yellow', 'FSR Detected!', 'Status: Preparing to record...')
                
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
    change_background_color('orange', 'Starting recording in 3...', 'Status: Get ready to speak')
    
    # Countdown
    def countdown(remaining):
        if remaining > 0:
            change_background_color('orange', f'Starting recording in {remaining}...', 'Status: Get ready to speak')
            root.after(1000, lambda: countdown(remaining - 1))
        else:
            # Start recording in a separate thread to not block UI
            recording_thread = threading.Thread(target=record_audio, daemon=True)
            recording_thread.start()
    
    countdown(3)

# ============================================================================
# CLEANUP AND EXIT
# ============================================================================
def cleanup_and_exit():
    """Cleanup and exit the application"""
    global fsr_thread_running, wake_detector_running, root
    
    print("\n[Cleanup] Cleaning up resources...")
    
    # Stop threads
    fsr_thread_running = False
    wake_detector_running = False
    
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
    print("="*60)
    print("FSR TOUCH RECORDING TEST")
    print("="*60)
    print("Instructions:")
    print("1. Double-tap the FSR sensor quickly")
    print("2. UI will change colors to indicate status")
    print("3. After 3-second countdown, 5-second recording starts")
    print("4. Recording will play back automatically")
    print("5. App will exit automatically")
    print("="*60)
    
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