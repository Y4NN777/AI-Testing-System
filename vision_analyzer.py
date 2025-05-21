import os
import base64
import json
import re
import easyocr
import cv2
import numpy as np
from PIL import Image
import requests
from dotenv import load_dotenv
from screen_capture import ScreenCapture
import time

load_dotenv()

class VisionAnalyzer:
    def __init__(self, maestro_commands_path="maestro_commands.json"):
        """
        Initializes the VisionAnalyzer with access to Maestro commands context.
        """
        self.screen_capture = ScreenCapture()
        self.reader = easyocr.Reader(['en'])
        
        # Load Maestro commands for context
        try:
            with open(maestro_commands_path, 'r') as f:
                self.maestro_commands = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load Maestro commands: {e}")
            self.maestro_commands = {"commands": []}
        
        # Retrieve API keys from environment variables
        self.hf_api_key = os.getenv("HF_API_KEY")
        self.replicate_api_key = os.getenv("REPLICATE_API_KEY")
        
    def analyze_screen(self):
        """
        Enhanced screen analysis combining visual and hierarchy data
        """
        # Capture both screenshot and hierarchy
        capture_result = self.screen_capture.capture_screen_and_hierarchy()
        screenshot_path = capture_result["screenshot_path"]
        hierarchy_data = capture_result["hierarchy"]
        
        # Step 1: Use EasyOCR to detect text on the captured image
        image = cv2.imread(screenshot_path)
        text_results = self.reader.readtext(image)
        
        # Step 2: Extract elements from screen hierarchy
        hierarchy_elements = self._extract_elements_from_hierarchy(hierarchy_data)
        
        # Step 3: Attempt to get high-level analysis from a vision LLM
        llm_analysis = self._get_llm_analysis(screenshot_path, hierarchy_elements)
        
        # Combine all results into a unified structure
        elements = []
        
        # Add text elements detected by EasyOCR
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

        
        # Add UI elements from hierarchy analysis with their properties
        for el in hierarchy_elements:
            if el not in elements:  # Avoid duplicates
                elements.append(el)
        
        # If the LLM analysis was successful, it provides a more comprehensive understanding
        if llm_analysis:
            # Enhance the LLM analysis with hierarchy data
            enriched_analysis = self._enrich_llm_analysis_with_hierarchy(llm_analysis, hierarchy_elements)
            return enriched_analysis
        
        # Otherwise, return the combined analysis
        return {
            "elements": elements,
            "app_state": self._guess_app_state(elements),
            "maestro_commands": [cmd["name"] for cmd in self.maestro_commands["commands"][:5]]  # Top 5 relevant commands
        }


    def _get_position_description_from_coords(self, x, y, w, h, img_width, img_height):
        """
        Converts bounding box coordinates to a descriptive string representing the element's position
        on the screen (e.g., "top-left", "middle-center").
        Args:
            x (int): X-coordinate of the top-left corner of the bounding box.
            y (int): Y-coordinate of the top-left corner of the bounding box.
            w (int): Width of the bounding box.
            h (int): Height of the bounding box.
            img_width (int): Total width of the image.
            img_height (int): Total height of the image.
        Returns:
            str: A string describing the position.
        """
        # Calculate the center point of the element.
        x_center = x + w/2
        y_center = y + h/2
        
        # Determine horizontal position.
        x_pos = "center"
        if x_center < (img_width / 3):
            x_pos = "left"
        elif x_center > (2 * img_width / 3):
            x_pos = "right"
            
        # Determine vertical position.
        y_pos = "middle"
        if y_center < (img_height / 3):
            y_pos = "top"
        elif y_center > (2 * img_height / 3):
            y_pos = "bottom"
            
        return f"{y_pos}-{x_pos}"
    
    def _guess_app_state(self, elements):
        """
        Makes a simple guess about the current application state based on detected text elements.
        This is a fallback if no LLM analysis is performed.
        Args:
            elements (list): A list of detected UI elements, including text.
        Returns:
            str: A guessed app state (e.g., "login_screen", "home_screen", "unknown").
        """
        text_elements = [e for e in elements if e.get("type") == "text"]
        texts = [e.get("text", "").lower() for e in text_elements]
        
        # Check for common keywords to infer app state.
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
            return "unknown" # Default to unknown if no specific state is recognized.
    
    def _get_llm_analysis(self, screenshot_path):
        """
        Attempts to get a high-level screen analysis using either Hugging Face or Replicate
        vision models, if their respective API keys are configured.
        Args:
            screenshot_path (str): Path to the screenshot image.
        Returns:
            dict or None: Structured analysis from the LLM, or None if no API is available
                          or an error occurs.
        """
        if self.hf_api_key:
            return self._analyze_with_huggingface(screenshot_path)
        elif self.replicate_api_key:
            return self._analyze_with_replicate(screenshot_path)
        else:
            return None # No API keys configured for LLM analysis.
    
    def _analyze_with_huggingface(self, screenshot_path):
        """
        Uses the Hugging Face Inference API to get a caption of the image and then
        uses a text generation model to extract UI elements and app state from the caption.
        Args:
            screenshot_path (str): Path to the screenshot image.
        Returns:
            dict or None: Structured analysis from Hugging Face, or None on error.
        """
        # Hugging Face API endpoint for image captioning.
        api_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
        headers = {"Authorization": f"Bearer {self.hf_api_key}"}
        
        with open(screenshot_path, "rb") as f:
            image_data = f.read()
        
        try:
            # First, get a descriptive caption of the image.
            response = requests.post(api_url, headers=headers, data=image_data)
            caption_result = response.json()
            
            if isinstance(caption_result, list) and len(caption_result) > 0:
                caption = caption_result[0].get("generated_text", "")
            else:
                caption = str(caption_result)
            
            # Use a second prompt with a text generation model to extract structured UI elements.
            analysis_prompt = f"""
            Based on this caption of a mobile app screen: "{caption}"
            
            Extract all UI elements (buttons, text fields, labels) with their approximate positions (e.g., top-left, center, bottom-right) and determine the current app state (e.g., login_screen, home_screen, settings_screen).
            Format your response as a JSON object with two top-level keys: "elements" (an array of objects) and "app_state" (a string).
            Example:
            {{
                "elements": [
                    {{"type": "text", "text": "Welcome", "position": "top-center"}},
                    {{"type": "button", "text": "Login", "position": "center"}},
                    {{"type": "input_field", "text": "Username", "position": "middle-left"}}
                ],
                "app_state": "login_screen"
            }}
            """
            
            # Hugging Face API endpoint for text generation (using a large language model).
            text_api_url = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-70b-chat-hf"
            text_response = requests.post(
                text_api_url, 
                headers=headers, 
                json={"inputs": analysis_prompt}
            )
            
            analysis_text = text_response.json()[0].get("generated_text", "")
            return self._parse_llm_response(analysis_text)
            
        except Exception as e:
            print(f"Error using Hugging Face API for vision analysis: {e}")
            return None
    
    def _analyze_with_replicate(self, screenshot_path):
        """
        Uses the Replicate API with a vision-language model to directly analyze the screenshot
        and extract UI elements and app state.
        Args:
            screenshot_path (str): Path to the screenshot image.
        Returns:
            dict or None: Structured analysis from Replicate, or None on error or timeout.
        """
        try:
            # Convert image to base64 for API submission.
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            headers = {
                "Authorization": f"Token {self.replicate_api_key}",
                "Content-Type": "application/json"
            }
            
            # Replicate API payload for a vision-language model (e.g., LLaVA).
            # The 'version' specifies the model and its specific version.
            payload = {
                "version": "f4e2de70d66816a838a89eeeb621910adffb0dd0baba3976c96980970978018d", # Example LLaVA model version
                "input": {
                    "image": f"data:image/jpeg;base64,{image_data}",
                    "prompt": "Analyze this mobile app screen. List all UI elements (buttons, text fields, labels) with their approximate positions (e.g., top-left, center, bottom-right) and determine the current app state (e.g., login_screen, home_screen, settings_screen). Format your response as a JSON object with two top-level keys: 'elements' (an array of objects) and 'app_state' (a string).",
                    "max_tokens": 512 # Limit response length
                }
            }
            
            # Start the prediction.
            response = requests.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json=payload
            )
            
            prediction = response.json()
            if "error" in prediction:
                print(f"Replicate API error: {prediction['error']}")
                return None
                
            prediction_id = prediction.get("id")
            if not prediction_id:
                return None
                
            # Poll for the prediction result as it runs asynchronously.
            for _ in range(30): # Poll for up to 30 seconds.
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
                    
                time.sleep(1) # Wait 1 second before polling again.
                
            print("Replicate API call timed out.")
            return None # Timeout if prediction doesn't succeed within attempts.
            
        except Exception as e:
            print(f"Error using Replicate API for vision analysis: {e}")
            return None
    
    def _parse_llm_response(self, text):
        """
        Parses the raw text response from an LLM to extract a structured JSON object.
        This function is robust to handle cases where the LLM might embed JSON within other text.
        Args:
            text (str): The raw text response from the LLM.
        Returns:
            dict or None: The parsed JSON object, or None if parsing fails.
        """
        try:
            # Attempt to find and parse a JSON object within the text.
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from LLM response: {text}")
            pass # Continue to return None if JSON parsing fails.
    
    def _extract_elements_from_hierarchy(self, hierarchy_data):
        """
        Extract UI elements from the Maestro hierarchy data
        """
        if not hierarchy_data:
            return []
            
        elements = []
        
        def process_element(element, parent_path=""):
            """Recursively process elements in the hierarchy"""
            # Skip if missing critical data
            if not isinstance(element, dict):
                return
                
            # Extract element's type and attributes
            el_type = element.get("type", "unknown")
            attributes = element.get("attributes", {})
            
            # Create path that helps identify this element's position in the hierarchy
            current_path = f"{parent_path}/{el_type}"
            if "id" in attributes:
                current_path += f"[{attributes['id']}]"
            
            # Extract useful properties
            element_data = {
                "type": el_type,
                "path": current_path,
                "id": attributes.get("id", ""),
                "text": attributes.get("text", ""),
                "enabled": attributes.get("enabled", True),
                "clickable": attributes.get("clickable", False),
                "position": attributes.get("bounds", ""),
                "hierarchy_path": current_path  # Important for accurate targeting
            }
            
            # Only add elements that are likely interactive or contain useful information
            if (element_data["clickable"] or 
                element_data["text"] or 
                element_data["id"] or 
                el_type.lower() in ["button", "textfield", "edittext", "imagebutton", "checkbox"]):
                elements.append(element_data)
            
            # Process child elements
            for child in element.get("elements", []):
                process_element(child, current_path)
        
        # Start processing from root elements
        for root_element in hierarchy_data:
            process_element(root_element)
            
        return elements
    
    def _enrich_llm_analysis_with_hierarchy(self, llm_analysis, hierarchy_elements):
        """
        Enhance the LLM's analysis with precise element identifiers from hierarchy
        """
        # Extract elements from LLM analysis
        llm_elements = llm_analysis.get("elements", [])
        
        # For each LLM-detected element, try to find matching hierarchy element
        for llm_el in llm_elements:
            # Extract key properties
            el_text = llm_el.get("text", "").lower()
            el_type = llm_el.get("type", "").lower()
            el_position = llm_el.get("position", "")
            
            # Find potential matches in hierarchy
            matches = []
            for h_el in hierarchy_elements:
                h_text = h_el.get("text", "").lower()
                h_type = h_el.get("type", "").lower()
                
                # Calculate match score
                score = 0
                if el_text and el_text in h_text:
                    score += 3
                if el_type and (el_type in h_type or h_type in el_type):
                    score += 2
                # Position matching could be added with more sophisticated logic
                
                if score > 0:
                    matches.append((h_el, score))
            
            # If matches found, add hierarchy data to the LLM element
            if matches:
                # Sort by score, descending
                matches.sort(key=lambda x: x[1], reverse=True)
                best_match = matches[0][0]
                
                # Add hierarchy data to LLM element
                llm_el["id"] = best_match.get("id", "")
                llm_el["hierarchy_path"] = best_match.get("hierarchy_path", "")
                llm_el["clickable"] = best_match.get("clickable", False)
        
        # Return the enhanced analysis
        return llm_analysis