import subprocess
import os
import time
import json
from PIL import Image
import io
import re

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
    
    def get_screen_hierarchy(self):
        """Capture the UI hierarchy using Maestro's hierarchy command"""
        hierarchy_path = f"{self.temp_dir}/hierarchy_{int(time.time())}.json"
        
        try:
            # Execute maestro hierarchy command and redirect output to file
            # Note: The actual output format depends on Maestro's implementation
            result = subprocess.run(
                ["maestro", "hierarchy"],
                capture_output=True,
                text=True
            )
            
            # Parse the hierarchy output
            hierarchy_data = self._parse_hierarchy_output(result.stdout)
            
            # Save the parsed hierarchy as JSON
            with open(hierarchy_path, 'w') as f:
                json.dump(hierarchy_data, f, indent=2)
                
            return hierarchy_data
            
        except Exception as e:
            print(f"Error capturing screen hierarchy: {e}")
            return None
    
    def _parse_hierarchy_output(self, hierarchy_text):
        """
        Parse the text output from Maestro's hierarchy command into a structured format.
        This is a simplified implementation - actual parsing depends on Maestro's output format.
        """
        elements = []
        lines = hierarchy_text.strip().split('\n')
        
        current_depth = 0
        parent_stack = [{"elements": elements}]
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
                
            # Determine element's depth in the hierarchy based on indentation
            indent_match = re.match(r'^(\s*)', line)
            depth = len(indent_match.group(1)) // 2 if indent_match else 0
            
            # Extract element properties
            # This regex pattern needs to be adjusted based on actual Maestro output
            props_match = re.search(r'(\w+)(?:\[([^\]]+)\])?', line.strip())
            if not props_match:
                continue
                
            element_type = props_match.group(1)
            attributes_str = props_match.group(2) if props_match.group(2) else ""
            
            # Parse attributes (simplified)
            attributes = {}
            for attr in attributes_str.split(','):
                if '=' in attr:
                    key, value = attr.split('=', 1)
                    attributes[key.strip()] = value.strip().strip('"\'')
            
            # Create element object
            element = {
                "type": element_type,
                "attributes": attributes,
                "elements": []  # For child elements
            }
            
            # Adjust parent stack based on depth
            if depth > current_depth:
                parent_stack.append(parent_stack[-1]["elements"][-1])
            elif depth < current_depth:
                for _ in range(current_depth - depth):
                    parent_stack.pop()
            
            # Add element to its parent
            parent_stack[-1]["elements"].append(element)
            current_depth = depth
            
        return elements
        
    def capture_screen_and_hierarchy(self):
        """Capture both screenshot and hierarchy in one operation"""
        screenshot_path = self.capture_screen()
        hierarchy_data = self.get_screen_hierarchy()
        
        return {
            "screenshot_path": screenshot_path,
            "hierarchy": hierarchy_data
        }