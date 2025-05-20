import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

class InstructionParser:
    def __init__(self):
        # Configure the Gemini API
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-pro')
        
    def parse_instruction(self, instruction, screen_analysis):
        """Parse natural language instruction into structured test steps using Google Gemini API"""
        # Prepare context from screen analysis
        elements_context = "\n".join([
            f"- {el.get('type', 'Element')}: '{el.get('text', '')}' at position {el.get('position', 'unknown')}"
            for el in screen_analysis.get("elements", [])
        ])
        
        context = f"""
Current app state: {screen_analysis.get('app_state', 'unknown')}
Visible elements:
{elements_context}

Based on this screen information, parse the following test instruction:
"{instruction}"

Return a JSON array of test steps with these fields:
- action: The type of action (tap, swipe, type, assert)
- target: Description of the UI element to interact with
- value: For type actions, the text to enter. For assertions, what to check.
- description: Human-readable description of this step
        """
        
        # Call Gemini API to parse the instruction
        response = self.model.generate_content(context)
        
        # Extract and parse the response
        response_text = response.text
        return self._parse_llm_response(response_text)
    
    def _parse_llm_response(self, text):
        """Parse the LLM response to extract test steps"""
        try:
            # Try to find JSON in the response
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback for failed parsing
            pass
            
        # Return empty array if parsing failed
        return []