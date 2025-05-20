# maestro_generator.py
import os
import yaml 
from dotenv import load_dotenv # Import load_dotenv

load_dotenv() # Load environment variables

class MaestroGenerator:
    def __init__(self, output_dir="./maestro_flows"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.app_id = os.getenv("MAESTRO_APP_ID") # Get app_id from .env
        
    def generate_flow(self, test_steps, flow_name="test_flow"):
        """Generate a Maestro flow from test steps"""
        flow_path = f"{self.output_dir}/{flow_name}.yaml"
        
        # Create flow structure
        flow_commands = [] # Use a temporary list for commands
        
        # Add the launchApp command with appId at the beginning
        if self.app_id:
            flow_commands.append({
                "launchApp": {
                    "appId": self.app_id
                }
            })
            
        for step in test_steps:
            action = step.get("action", "").lower()
            target = step.get("target", "")
            value = step.get("value", "")
            
            if action == "tap":
                flow_commands.append({ # Append to flow_commands
                    "tapOn": target
                })
            elif action == "type":
                flow_commands.append({ # Append to flow_commands
                    "tapOn": target
                })
                flow_commands.append({ # Append to flow_commands
                    "inputText": value
                })
            elif action == "swipe":
                # Simple implementation - can be enhanced
                flow_commands.append({ # Append to flow_commands
                    "swipe": {
                        "direction": value or "UP"
                    }
                })
            elif action == "assert":
                flow_commands.append({ # Append to flow_commands
                    "assertVisible": target
                })
            
        # Write flow to file
        with open(flow_path, 'w') as f:
            yaml.dump(flow_commands, f) # Dump flow_commands
            
        return flow_path