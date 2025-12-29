#!/usr/bin/env python3
import time
import subprocess
import os
import signal
import sys

# Configuration
GPIO_START_PIN = 23 # Pin 16
GPIO_LED_PIN = 27   # Pin 13
DEBOUNCE_TIME = 0.5

def setup_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_START_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # Setup LED and force OFF initially
        GPIO.setup(GPIO_LED_PIN, GPIO.OUT)
        GPIO.output(GPIO_LED_PIN, GPIO.LOW)
        return GPIO
    except ImportError:
        print("RPi.GPIO not found. Running in simulation mode (waiting for Enter).")
        return None

def main():
    print("Invenova Launcher Service Started.")
    print(f"Waiting for Button Press on GPIO {GPIO_START_PIN}...")
    
    GPIO = setup_gpio()
    assistant_process = None
    
    try:
        while True:
            should_launch = False
            
            if GPIO:
                # Button pressed (LOW because pull-up)
                if GPIO.input(GPIO_START_PIN) == GPIO.LOW:
                    # ONLY print if we are about to do something, or if it's a new press (debounce handling logic is simple here)
                    # For toggle switches, this is always True. We handle spam below.
                    should_launch = True
                    time.sleep(DEBOUNCE_TIME) # Debounce
            else:
                # Sim mode
                i = input("Press Enter to launch assistant (Sim Mode)...")
                should_launch = True
                
            if should_launch:
                if assistant_process and assistant_process.poll() is None:
                    # Already running.
                    pass
                else:
                    print("Start Button Pressed! Launching Assistant...")
                    
                    # 1. Release GPIO resources so the Assistant can use them exclusively
                    if GPIO:
                        GPIO.cleanup()
                        GPIO = None # Flag that we don't have GPIO access anymore
                        
                    # 2. Run run.sh
                    try:
                        # Use setsid to start a new session
                        assistant_process = subprocess.Popen(["./run.sh"], cwd=os.getcwd(), preexec_fn=os.setsid)
                    except Exception as e:
                        print(f"Failed to launch: {e}")
            
            else:
                # Button NOT pressed (or we are in Passive Mode without GPIO)
                
                # Check if process died
                if assistant_process and assistant_process.poll() is not None:
                     print("Assistant exited. Resetting state.")
                     assistant_process = None
                     
                     # 3. Restore GPIO for next launch
                     if GPIO is None:
                         GPIO = setup_gpio()
                     
                     # Force LED OFF
                     if GPIO:
                        GPIO.output(GPIO_LED_PIN, GPIO.LOW)
            
            # If in Passive Mode (GPIO is None), we just sleep and check process
            time.sleep(0.5 if GPIO is None else 0.1)
            
    except KeyboardInterrupt:
        print("Launcher stopped.")
    finally:
        if GPIO:
            GPIO.cleanup()

if __name__ == "__main__":
    main()
