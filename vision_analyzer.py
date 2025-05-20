import os
import base64
import json
from dotenv import load_dotenv
from screen_capture import ScreenCapture
from google.cloud import vision
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

class VisionAnalyzer:
    def __init__(self):
        self.screen_capture = ScreenCapture()
        
        # Google Cloud Vision setup
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.vision_client = vision.ImageAnnotatorClient()
        
        # Google Gemini API setup
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.gemini_model = genai.GenerativeModel('gemini-pro-vision')
        
    def analyze_screen(self):
        """Analyze the current screen and identify UI elements using Google Vision API"""
        # Capture current screen
        screenshot_path = self.screen_capture.capture_screen()
        
        # Step 1: Use Google Cloud Vision API to detect text and objects
        with open(screenshot_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Get text detection results
        text_detection = self.vision_client.text_detection(image=image)
        texts = text_detection.text_annotations
        
        # Get object detection results
        object_detection = self.vision_client.object_localization(image=image)
        objects = object_detection.localized_object_annotations
        
        # Step 2: Use Gemini API for higher-level understanding
        with open(screenshot_path, "rb") as img_file:
            image_data = img_file.read()
            
        prompt = """Analyze this mobile app screen. Identify:
        1. All visible UI elements (buttons, text fields, labels)
        2. Their approximate positions (use top-left, center, bottom-right, etc.)
        3. Current app state or context (login screen, dashboard, settings, etc.)
        
        Format your response as JSON with these keys: 
        elements (array of objects with type, text, position), 
        app_state (string)"""
        
        response = self.gemini_model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_data}
        ])
        
        # Parse the response from Gemini
        try:
            # Extract JSON from the response
            response_text = response.text
            return self._parse_llm_response(response_text)
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            
            # Fallback: Create structured data from Vision API results
            elements = []
            
            # Add text elements
            for text in texts[1:]:  # Skip the first one which contains all text
                elements.append({
                    "type": "text",
                    "text": text.description,
                    "position": self._get_position_description(text.bounding_poly)
                })
            
            # Add object elements
            for obj in objects:
                elements.append({
                    "type": "ui_element",
                    "text": obj.name,
                    "position": self._get_position_description_from_object(obj)
                })
            
            return {
                "elements": elements,
                "app_state": "unknown"  # Without Gemini analysis, we can't determine the app state
            }
    
    def _get_position_description(self, bounding_poly):
        """Convert bounding polygon to position description"""
        vertices = bounding_poly.vertices
        if not vertices:
            return "unknown"
            
        # Calculate center point
        x_sum = sum(vertex.x for vertex in vertices)
        y_sum = sum(vertex.y for vertex in vertices)
        x_avg = x_sum / len(vertices)
        y_avg = y_sum / len(vertices)
        
        # Determine position based on center point
        # Assuming a standard screen size (adjust as needed)
        screen_width = 1080
        screen_height = 1920
        
        x_pos = "center"
        if x_avg < (screen_width / 3):
            x_pos = "left"
        elif x_avg > (2 * screen_width / 3):
            x_pos = "right"
            
        y_pos = "middle"
        if y_avg < (screen_height / 3):
            y_pos = "top"
        elif y_avg > (2 * screen_height / 3):
            y_pos = "bottom"
            
        return f"{y_pos}-{x_pos}"
    
    def _get_position_description_from_object(self, obj):
        """Convert object bounding box to position description"""
        # The normalized vertices go from 0 to 1
        vertices = obj.bounding_poly.normalized_vertices
        if not vertices:
            return "unknown"
            
        # Calculate center point
        x_sum = sum(vertex.x for vertex in vertices)
        y_sum = sum(vertex.y for vertex in vertices)
        x_avg = x_sum / len(vertices)
        y_avg = y_sum / len(vertices)
        
        # Determine position based on center point
        x_pos = "center"
        if x_avg < 0.33:
            x_pos = "left"
        elif x_avg > 0.66:
            x_pos = "right"
            
        y_pos = "middle"
        if y_avg < 0.33:
            y_pos = "top"
        elif y_avg > 0.66:
            y_pos = "bottom"
            
        return f"{y_pos}-{x_pos}"
    
    def _parse_llm_response(self, text):
        """Parse the LLM response to extract structured data"""
        try:
            # Try to find JSON in the response
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse Gemini response as JSON. Error: {e}. Raw response: {text}")
            # Fallback for failed parsing            
            
        # Return a simple structure if JSON parsing failed
        return {
            "elements": [],
            "app_state": "unknown"
        }