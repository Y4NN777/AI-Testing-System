# vision_analyzer.py
import os
import base64
import json
import easyocr
import cv2
import numpy as np
from PIL import Image
import requests
from dotenv import load_dotenv
from screen_capture import ScreenCapture

# Load environment variables from .env file
load_dotenv()

class VisionAnalyzer:
    def __init__(self):
        self.screen_capture = ScreenCapture()
        
        # Initialize EasyOCR for text detection
        # Supports multiple languages - add more as needed
        self.reader = easyocr.Reader(['en'])
        
        # Set up Hugging Face API access if available
        self.hf_api_key = os.getenv("HF_API_KEY")
        
        # Set up Replicate API access if available
        self.replicate_api_key = os.getenv("REPLICATE_API_KEY")
        
    def analyze_screen(self):
        """Analyze the current screen and identify UI elements using open source tools"""
        # Capture current screen
        screenshot_path = self.screen_capture.capture_screen()
        
        # Step 1: Use EasyOCR to detect text
        image = cv2.imread(screenshot_path)
        text_results = self.reader.readtext(image)
        
        # Step 2: Perform simple UI element detection with OpenCV
        # Look for rectangular shapes that could be buttons
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours to find potential UI elements (buttons, input fields)
        ui_elements = []
        for contour in contours:
            # Approximate the contour to a polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            # If it's a rectangle (4 points) and large enough to be a UI element
            if len(approx) == 4 and cv2.contourArea(contour) > 1000:
                x, y, w, h = cv2.boundingRect(contour)
                ui_elements.append({
                    "type": "ui_element",
                    "position": self._get_position_description_from_coords(x, y, w, h, image.shape[1], image.shape[0])
                })
        
        # Step 3: Use a high-level vision model if API keys are available
        llm_analysis = self._get_llm_analysis(screenshot_path)
        
        # Combine all results
        elements = []
        
        # Add text elements from EasyOCR
        for (bbox, text, prob) in text_results:
            if prob > 0.5:  # Only include text detected with reasonable confidence
                x_min = min(point[0] for point in bbox)
                y_min = min(point[1] for point in bbox)
                x_max = max(point[0] for point in bbox)
                y_max = max(point[1] for point in bbox)
                w = x_max - x_min
                h = y_max - y_min
                
                elements.append({
                    "type": "text",
                    "text": text,
                    "position": self._get_position_description_from_coords(
                        x_min, y_min, w, h, image.shape[1], image.shape[0]
                    )
                })
        
        # Add UI elements from contour detection
        for ui in ui_elements:
            elements.append(ui)
        
        # If we have LLM analysis, use that instead as it's more comprehensive
        if llm_analysis:
            return llm_analysis
        
        # Otherwise return our simplified analysis
        return {
            "elements": elements,
            "app_state": self._guess_app_state(elements)
        }
    
    def _get_position_description_from_coords(self, x, y, w, h, img_width, img_height):
        """Convert coordinates to position description"""
        # Calculate center point
        x_center = x + w/2
        y_center = y + h/2
        
        # Determine position based on center point
        x_pos = "center"
        if x_center < (img_width / 3):
            x_pos = "left"
        elif x_center > (2 * img_width / 3):
            x_pos = "right"
            
        y_pos = "middle"
        if y_center < (img_height / 3):
            y_pos = "top"
        elif y_center > (2 * img_height / 3):
            y_pos = "bottom"
            
        return f"{y_pos}-{x_pos}"
    
    def _guess_app_state(self, elements):
        """Make a simple guess at the app state based on detected elements"""
        text_elements = [e for e in elements if e.get("type") == "text"]
        texts = [e.get("text", "").lower() for e in text_elements]
        
        # Look for common app states
        if any("login" in t for t in texts) or any("sign in" in t for t in texts):
            return "login_screen"
        elif any("register" in t for t in texts) or any("sign up" in t for t in texts):
            return "registration_screen"
        elif any("settings" in t for t in texts):
            return "settings_screen"
        elif any("profile" in t for t in texts):
            return "profile_screen"
        elif any("home" in t for t in texts):
            return "home_screen"
        else:
            return "unknown"
    
    def _get_llm_analysis(self, screenshot_path):
        """Get high-level analysis from vision model if API keys are available"""
        if self.hf_api_key:
            return self._analyze_with_huggingface(screenshot_path)
        elif self.replicate_api_key:
            return self._analyze_with_replicate(screenshot_path)
        else:
            return None
    
    def _analyze_with_huggingface(self, screenshot_path):
        """Use Hugging Face Inference API for screen analysis"""
        # HF API endpoint for image analysis
        api_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
        
        headers = {"Authorization": f"Bearer {self.hf_api_key}"}
        
        with open(screenshot_path, "rb") as f:
            image_data = f.read()
        
        # Get a caption from the image
        try:
            response = requests.post(api_url, headers=headers, data=image_data)
            caption_result = response.json()
            
            if isinstance(caption_result, list) and len(caption_result) > 0:
                caption = caption_result[0].get("generated_text", "")
            else:
                caption = str(caption_result)
            
            # Use a second prompt to extract UI elements
            analysis_prompt = f"""
            Based on this caption of a mobile app screen: "{caption}"
            
            Extract all UI elements and determine the app state.
            Format as JSON with:
            - elements: array of objects with type, text, position
            - app_state: string describing current screen
            """
            
            # Use HF text generation model for analysis
            text_api_url = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-70b-chat-hf"
            text_response = requests.post(
                text_api_url, 
                headers=headers, 
                json={"inputs": analysis_prompt}
            )
            
            analysis_text = text_response.json()[0].get("generated_text", "")
            return self._parse_llm_response(analysis_text)
            
        except Exception as e:
            print(f"Error using Hugging Face API: {e}")
            return None
    
    def _analyze_with_replicate(self, screenshot_path):
        """Use Replicate API for screen analysis"""
        try:
            # Convert image to base64
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            headers = {
                "Authorization": f"Token {self.replicate_api_key}",
                "Content-Type": "application/json"
            }
            
            # Use a Replicate vision-language model
            payload = {
                "version": "f4e2de70d66816a838a89eeeb621910adffb0dd0baba3976c96980970978018d",
                "input": {
                    "image": f"data:image/jpeg;base64,{image_data}",
                    "prompt": "Analyze this mobile app screen. List all UI elements (buttons, text fields, labels) with their positions and determine the current app state.",
                    "max_tokens": 512
                }
            }
            
            response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json=payload
            )
            
            prediction = response.json()
            if "error" in prediction:
                print(f"Replicate API error: {prediction['error']}")
                return None
                
            # Get prediction ID
            prediction_id = prediction.get("id")
            if not prediction_id:
                return None
                
            # Poll for results
            for _ in range(30):  # Try for 30 seconds
                poll_response = requests.get(
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    headers=headers
                )
                poll_data = poll_response.json()
                
                if poll_data.get("status") == "succeeded":
                    output = poll_data.get("output", "")
                    return self._parse_llm_response(output)
                    
                if poll_data.get("status") == "failed":
                    print(f"Replicate prediction failed: {poll_data.get('error')}")
                    return None
                    
                time.sleep(1)  # Wait before polling again
                
            return None
            
        except Exception as e:
            print(f"Error using Replicate API: {e}")
            return None
    
    def _parse_llm_response(self, text):
        """Parse the LLM response to extract structured data"""
        try:
            # Try to find JSON in the response
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback approach: try to extract information with regular expression
            pass
            
        # Return a simple structure if JSON parsing failed
        return None