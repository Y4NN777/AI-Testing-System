import subprocess
import os
import time
from PIL import Image
import io

class ScreenCapture:
    def __init__(self, temp_dir="./temp"):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        
    def capture_screen(self):
        """Capture current screen from connected Android device/emulator"""
        timestamp = int(time.time())
        screenshot_path = f"{self.temp_dir}/screen_{timestamp}.png"
        
        # Use ADB to capture screenshot
        subprocess.run([
            "adb", "exec-out", "screencap -p"
        ], stdout=open(screenshot_path, "wb"))
        
        return screenshot_path
    
    def get_screen_as_bytes(self):
        """Get screen capture as bytes for direct use with vision models"""
        screenshot_path = self.capture_screen()
        with open(screenshot_path, "rb") as f:
            return f.read()