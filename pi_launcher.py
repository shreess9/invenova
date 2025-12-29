#!/usr/bin/env python3
import time
import subprocess
import os
import signal
import sys

# Configuration
GPIO_START_PIN = 23 # Pin 16
DEBOUNCE_TIME = 0.5

def setup_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_START_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
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
                    print("Start Button Pressed!")
                    should_launch = True
                    time.sleep(DEBOUNCE_TIME) # Debounce
            else:
                # Sim mode
                i = input("Press Enter to launch assistant (Sim Mode)...")
                should_launch = True
                
            if should_launch:
                if assistant_process and assistant_process.poll() is None:
                    print("Assistant is already running.")
                else:
                    print("Launching Assistant...")
                    # Run run.sh
                    try:
                        # Use setsid to start a new session so we can kill easily if needed
                        assistant_process = subprocess.Popen(["./run.sh"], cwd=os.getcwd(), preexec_fn=os.setsid)
                    except Exception as e:
                        print(f"Failed to launch: {e}")
                        
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("Launcher stopped.")
    finally:
        if GPIO:
            GPIO.cleanup()

if __name__ == "__main__":
    main()
