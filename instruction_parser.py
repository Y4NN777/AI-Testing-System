import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import re # Import re for robust JSON parsing fallback

# Load environment variables from .env file (specifically GEMINI_API_KEY)
load_dotenv()

class InstructionParser:
    def __init__(self):
        """
        Initializes the InstructionParser.
        Configures the Google Gemini API with the provided API key.
        """
        # Retrieve the Gemini API key from environment variables.
        genai_api_key = os.getenv("GEMINI_API_KEY")
        if not genai_api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your .env file.")
            
        genai.configure(api_key=genai_api_key)
        # Initialize the GenerativeModel using 'gemini-pro' for text generation.
        self.model = genai.GenerativeModel('gemini-pro')
        
    def parse_instruction(self, instruction, screen_analysis):
        """
        Parses a natural language test instruction into a list of structured test steps.
        It uses the Google Gemini API, providing context from the current screen analysis.
        Args:
            instruction (str): The natural language test instruction (e.g., "Tap on the login button").
            screen_analysis (dict): A dictionary containing 'elements' and 'app_state' from VisionAnalyzer.
        Returns:
            list: A JSON array of test steps, each with 'action', 'target', 'value', and 'description'.
        """
        # Prepare context for the Gemini API call based on the screen analysis.
        elements_context = "\n".join([
            f"- {el.get('type', 'Element')}: '{el.get('text', '')}' at position {el.get('position', 'unknown')}"
            for el in screen_analysis.get("elements", [])
        ])
        
        # Construct the prompt for Gemini, including current app state and visible elements.
        context = f"""
You are an AI assistant that converts natural language mobile app test instructions into structured test steps.
The current app state is: {screen_analysis.get('app_state', 'unknown')}
Visible elements on the screen are:
{elements_context}

Based on this screen information, parse the following test instruction into a sequence of atomic test steps.
Each step should be a JSON object with the following fields:
- action: The type of action (e.g., "tap", "swipe", "type", "assert").
- target: A concise description of the UI element to interact with (e.g., "Login button", "Username input field", "screen").
- value: For "type" actions, the text to enter. For "swipe" actions, the direction (e.g., "UP", "DOWN", "LEFT", "RIGHT"). For "assert" actions, the text or element to check for visibility. Leave empty if not applicable.
- description: A human-readable summary of what this step accomplishes.

Return only a JSON array of these test step objects. Do not include any other text or explanation.

Example of expected output:
[
    {{"action": "tap", "target": "Login button", "value": "", "description": "Tap on the login button"}},
    {{"action": "type", "target": "Username input field", "value": "testuser", "description": "Enter 'testuser' into the username field"}},
    {{"action": "swipe", "target": "screen", "value": "UP", "description": "Swipe up on the screen"}},
    {{"action": "assert", "target": "Welcome message", "value": "Welcome!", "description": "Verify 'Welcome!' message is visible"}}
]

Now, parse the instruction:
"{instruction}"
        """
        
        try:
            # Call the Gemini API to generate content based on the constructed context.
            response = self.model.generate_content(context)
            
            # Extract the raw text response from Gemini.
            response_text = response.text
            
            # Parse the response to extract the structured JSON test steps.
            return self._parse_llm_response(response_text)
        except Exception as e:
            print(f"Error calling Gemini API for instruction parsing: {e}")
            return [] # Return an empty list of steps on error.
    
    def _parse_llm_response(self, text):
        """
        Parses the raw text response from the LLM to extract a JSON array of test steps.
        This function is designed to be robust, attempting to find the JSON array even if
        it's embedded within other conversational text.
        Args:
            text (str): The raw text response from the LLM.
        Returns:
            list: A list of parsed test step dictionaries, or an empty list if parsing fails.
        """
        try:
            # Attempt to find the first '[' and last ']' to extract the potential JSON array.
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            # If direct JSON parsing fails, try a more lenient approach to extract individual JSON objects.
            print(f"Warning: Direct JSON parsing failed. Attempting fallback parsing for: {text}")
            steps = []
            # Use regex to find potential JSON objects that start with {"action": ...
            step_matches = re.finditer(r'{\s*"action":\s*"([^"]+)"', text)
            
            for match in step_matches:
                step_start = match.start()
                brace_count = 0
                step_end = step_start
                
                # Iterate to find the matching closing brace for the current JSON object.
                for i in range(step_start, len(text)):
                    if text[i] == '{':
                        brace_count += 1
                    elif text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            step_end = i + 1
                            break # Found the end of the current JSON object.
                
                if step_end > step_start:
                    try:
                        step_json = text[step_start:step_end]
                        step = json.loads(step_json)
                        steps.append(step)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing individual step JSON: {e} in '{step_json}'")
                        pass # Skip this malformed step and continue.
                        
            if steps:
                return steps # Return successfully parsed steps.
            
        # Return an empty array if all parsing attempts failed.
        return []
