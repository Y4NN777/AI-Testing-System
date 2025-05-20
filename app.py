# app.py
from screen_capture import ScreenCapture
from vision_analyzer import VisionAnalyzer
from instruction_parser import InstructionParser
from maestro_generator import MaestroGenerator
from execution_engine import ExecutionEngine
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for API keys and MAESTRO_APP_ID
if not os.getenv("GEMINI_API_KEY"):
    print("ERROR: GEMINI_API_KEY environment variable not set.")
    print("Please create a .env file with your Google Gemini API key.")
    print("Example: GEMINI_API_KEY=...")
    exit(1)

if not os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")):
    print("ERROR: GOOGLE_APPLICATION_CREDENTIALS environment variable not set or file not found.")
    print("Please create a .env file with the path to your Google Cloud credentials JSON file.")
    print("Example: GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json")
    exit(1)

if not os.getenv("MAESTRO_APP_ID"):
    print("ERROR: MAESTRO_APP_ID environment variable not set.")
    print("Please add MAESTRO_APP_ID=com.your.app.package.name to your .env file.")
    exit(1)

class AITestAssistant:
    def __init__(self):
        self.screen_capture = ScreenCapture()
        self.vision_analyzer = VisionAnalyzer()
        self.instruction_parser = InstructionParser()
        self.maestro_generator = MaestroGenerator()
        self.execution_engine = ExecutionEngine()
        
    def run_test_instruction(self, instruction):
        """Process a natural language test instruction"""
        print(f"Processing instruction: {instruction}")
        
        # Step 1: Analyze current screen
        print("Analyzing current screen...")
        screen_analysis = self.vision_analyzer.analyze_screen()
        
        # Step 2: Parse the instruction into test steps
        print("Parsing instruction...")
        test_steps = self.instruction_parser.parse_instruction(instruction, screen_analysis)
        
        # Step 3: Generate Maestro flow
        print("Generating Maestro flow...")
        flow_name = f"test_{int(time.time())}"
        flow_path = self.maestro_generator.generate_flow(test_steps, flow_name)
        
        # Step 4: Execute the flow
        print(f"Executing flow: {flow_path}...")
        result = self.execution_engine.run_flow(flow_path)
        
        if result["success"]:
            print("Test execution successful!")
        else:
            print(f"Test execution failed: {result.get('error', 'Unknown error')}")
            
        return result

if __name__ == "__main__":
    assistant = AITestAssistant()
    
    # Simple CLI interface
    while True:
        instruction = input("\nEnter test instruction (or 'exit' to quit): ")
        if instruction.lower() == 'exit':
            break
            
        assistant.run_test_instruction(instruction)