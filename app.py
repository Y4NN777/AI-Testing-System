from screen_capture import ScreenCapture
from vision_analyzer import VisionAnalyzer
from instruction_parser import InstructionParser
from maestro_generator import MaestroGenerator
from execution_engine import ExecutionEngine
import time
import os
import json  
from dotenv import load_dotenv

# Load environment variables from .env file.
load_dotenv()

# Retrieve API keys for vision models.
HF_API_KEY = os.getenv("HF_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Check for Gemini API key as well.
MAESTRO_APP_ID = os.getenv("MAESTRO_APP_ID")  # Retrieve Maestro App ID


# Path to the Maestro command specifications file.
MAESTRO_COMMANDS_PATH = "maestro_commands.json" 

# Provide startup messages based on API key availability.
print("--- AI-Powered Mobile App Testing Assistant ---")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found. Instruction parsing will be limited.")
else:
    print("Gemini API key detected for instruction parsing.")

if not HF_API_KEY and not REPLICATE_API_KEY:
    print("No Hugging Face or Replicate API keys detected for vision analysis.")
    print("Vision analysis will rely on basic EasyOCR and OpenCV (less detailed).")
    print("For enhanced vision, add HF_API_KEY or REPLICATE_API_KEY to your .env file.")
else:
    print("Hugging Face or Replicate API key detected for enhanced vision analysis.")

if MAESTRO_APP_ID:
    print(f"Maestro will attempt to launch app with ID: {MAESTRO_APP_ID}")
else:
    print("No MAESTRO_APP_ID found in .env. Maestro will operate on the currently foregrounded app.")

class AITestAssistant:
    def __init__(self):
        """
        Initializes the AI Test Assistant, creating instances of all core modules.
        """
        self.screen_capture = ScreenCapture()
        self.vision_analyzer = VisionAnalyzer()
        self.instruction_parser = InstructionParser()
        
        # Initialize MaestroGenerator with command specs path
        self.maestro_generator = MaestroGenerator(
            output_dir="./maestro_flows",
            maestro_commands_path=MAESTRO_COMMANDS_PATH
        )
        
        self.execution_engine = ExecutionEngine()
        
    def run_test_instruction(self, instruction):
        """
        Processes a natural language test instruction through the entire pipeline:
        screen capture -> vision analysis -> instruction parsing -> Maestro flow generation -> execution.
        Args:
            instruction (str): The natural language instruction provided by the user.
        Returns:
            dict: The result of the test execution (success status, output, error).
        """
        print(f"\nProcessing instruction: '{instruction}'")
        
        # Step 1: Analyze the current screen.
        print("1. Analyzing current screen...")
        screen_analysis = self.vision_analyzer.analyze_screen()
        print(f"   Screen analysis result: {json.dumps(screen_analysis, indent=2)}")
        
        # Step 2: Parse the instruction into structured test steps.
        print("2. Parsing instruction into test steps...")
        test_steps = self.instruction_parser.parse_instruction(instruction, screen_analysis)
        if not test_steps:
            print("   Failed to parse instruction into valid test steps. Please refine your instruction.")
            return {"success": False, "error": "Failed to parse instruction."}
        print(f"   Parsed test steps: {json.dumps(test_steps, indent=2)}")
        
        # Step 3: Generate the Maestro flow file from the parsed steps.
        # Updated to use the new MaestroGenerator interface
        print("3. Generating Maestro flow...")
        flow_name = f"test_{int(time.time())}"  # Unique name for each flow.
        # Pass the MAESTRO_APP_ID to the generator using the updated parameter structure
        flow_path = self.maestro_generator.generate_flow(test_steps, flow_name, MAESTRO_APP_ID)
        print(f"   Maestro flow generated at: {flow_path}")
        
        # Step 4: Execute the generated Maestro flow.
        print(f"4. Executing flow: {flow_path}...")
        result = self.execution_engine.execute_flow(flow_path)
        
        # Step 5: Generate test report if execution was completed
        if result:
            print("5. Generating test report...")
            report_path = self.execution_engine.generate_report(result)
            if report_path:
                print(f"   Test report generated at: {report_path}")
                result["report_path"] = report_path
        
        # Report the execution result.
        if result["success"]:
            print("Test execution successful!")
            print(f"Execution time: {result.get('execution_time', 'N/A')}s")
            if result.get("screenshots"):
                print(f"Screenshots captured: {len(result['screenshots'])}")
        else:
            print(f"Test execution failed!")
            if result.get("errors"):
                for error in result["errors"]:
                    print(f"Error ({error.get('source', 'unknown')}): {error.get('message', 'No details')}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
            
        return result

    def interactive_mode(self):
        """
        Run the assistant in interactive mode, processing user instructions until exit command.
        """
        print("\n=== Interactive Mode ===")
        print("Enter test instructions or commands. Type 'exit' to quit.")
        print("Other commands: 'screenshot' to capture screen, 'analyze' to analyze current screen.")
        
        while True:
            instruction = input("\nEnter test instruction: ")
            instruction = instruction.strip()
            
            if instruction.lower() == 'exit':
                break
                
            elif instruction.lower() == 'screenshot':
                screenshot_path = self.screen_capture.capture_screen()
                print(f"Screenshot captured: {screenshot_path}")
                
            elif instruction.lower() == 'analyze':
                screen_analysis = self.vision_analyzer.analyze_screen()
                print("Screen analysis result:")
                print(json.dumps(screen_analysis, indent=2))
                
            elif instruction:
                self.run_test_instruction(instruction)
                
        print("Exiting interactive mode.")

def main():
    """
    Main function to run the AI Test Assistant.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='AI-Powered Mobile App Testing Assistant')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
    parser.add_argument('--instruction', '-t', type=str, help='Single test instruction to execute')
    
    args = parser.parse_args()
    
    assistant = AITestAssistant()
    
    if args.instruction:
        # Run a single test instruction
        assistant.run_test_instruction(args.instruction)
    elif args.interactive:
        # Run in interactive mode
        assistant.interactive_mode()
    else:
        # Default to interactive mode if no arguments provided
        assistant.interactive_mode()

if __name__ == "__main__":
    main()