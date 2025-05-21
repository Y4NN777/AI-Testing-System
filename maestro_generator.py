import os
import yaml
import json
import re
from typing import Dict, List, Any, Optional, Union



class MaestroGenerator:
    """
    Enhanced Maestro flow generator with optimized usage of command specifications.
    Handles conversion of test steps to proper Maestro YAML flow format.
    """
    
    def __init__(self, output_dir: str = "./maestro_flows", maestro_commands_path: str = "maestro_commands.json"):
        """
        Initialize the Maestro flow generator with command specifications.
        
        Args:
            output_dir: Directory where generated flows will be saved
            maestro_commands_path: Path to the Maestro commands JSON specification
        """
        # Create output directory if it doesn't exist
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Load and process Maestro commands
        self.command_specs = self._load_command_specs(maestro_commands_path)
        
    def _load_command_specs(self, commands_path: str) -> Dict[str, Dict]:
        """
        Load and process Maestro commands from JSON file into a lookup dictionary.
        
        Args:
            commands_path: Path to the Maestro commands JSON specification
            
        Returns:
            Dictionary of command specifications indexed by lowercase command name
        """
        command_specs = {}
        
        try:
            with open(commands_path, 'r') as f:
                maestro_commands = json.load(f)
                
            # Process each command into a lookup dictionary
            for cmd in maestro_commands.get("commands", []):
                name = cmd.get("name", "")
                if name:
                    # Store command info with lowercase key for case-insensitive lookup
                    command_specs[name.lower()] = {
                        "name": name,  # Preserve original casing for output
                        "description": cmd.get("description", ""),
                        "parameters": cmd.get("parameters", {}),
                        "examples": cmd.get("examples", [])
                    }
        except Exception as e:
            print(f"Warning: Could not load Maestro commands: {e}")
        
        return command_specs
    
    def generate_flow(self, test_steps: List[Dict], flow_name: str = "test_flow", app_id: Optional[str] = None) -> str:
        """
        Generate a Maestro flow YAML file from test steps.
        
        Args:
            test_steps: List of test step dictionaries (action, target, value)
            flow_name: Name for the generated flow file
            app_id: Optional application ID for launchApp command
            
        Returns:
            Path to the generated flow file
        """
        flow_path = f"{self.output_dir}/{flow_name}.yaml"
        flow = []
        
        # Add launchApp if app_id provided
        if app_id:
            flow.append({
                "launchApp": {
                    "appId": app_id
                }
            })
        
        # Process each test step
        for step in test_steps:
            action = step.get("action", "").lower()
            target = step.get("target", "")
            value = step.get("value", "")
            
            # Handle special case for inputText which requires a tap first
            if action == "inputtext":
                # First add a tap command if target is specified
                if target:
                    tap_step = self._format_command("tapon", target, "")
                    if tap_step:
                        flow.append(tap_step)
                
                # Then add the inputText command
                input_step = self._format_command(action, "", value)
                if input_step:
                    flow.append(input_step)
            else:
                # Format and add the command
                maestro_step = self._format_command(action, target, value)
                if maestro_step:
                    flow.append(maestro_step)
        
        # Write flow to YAML file
        with open(flow_path, 'w') as f:
            yaml.dump(flow, f, sort_keys=False)
        
        return flow_path
    
    def _format_command(self, action: str, target: str, value: str) -> Optional[Dict]:
        """
        Format a command into proper Maestro format using command specifications.
        
        Args:
            action: The command/action name
            target: The UI element to target
            value: Additional value for the command
            
        Returns:
            Formatted Maestro command dictionary or None if invalid
        """
        # Normalize action name
        action = action.lower()
        
        # Handle command aliases (common alternative names)
        action_aliases = {
            "tap": "tapon", 
            "click": "tapon",
            "press": "tapon",
            "touch": "tapon",
            "select": "tapon",
            
            "type": "inputtext",
            "enter": "inputtext",
            "input": "inputtext",
            "write": "inputtext",
            "fill": "inputtext",
            
            "check": "assertvisible",
            "verify": "assertvisible",
            "assert": "assertvisible",
            "validate": "assertvisible",
            "checkvisible": "assertvisible",
            
            "checknotvisible": "assertnotvisible",
            "verifyhidden": "assertnotvisible",
            "asserthidden": "assertnotvisible",
            
            "longpress": "longtapon",
            "longclick": "longtapon",
            "holdtap": "longtapon",
            
            "doubletap": "doubletapon",
            "doubleclick": "doubletapon",
            
            "swipeup": "swipe",
            "swipedown": "swipe",
            "swipeleft": "swipe",
            "swiperight": "swipe",
            
            "scrollup": "scroll",
            "scrolldown": "scroll",
            "scrollleft": "scroll",
            "scrollright": "scroll",
            
            "scrollto": "scrolluntilvisible",
            "scrolltill": "scrolluntilvisible",
            "scrolluntil": "scrolluntilvisible",
            "scrollfind": "scrolluntilvisible",
            
            "wait": "wait",
            "pause": "wait",
            "delay": "wait",
            
            "erase": "erasetext",
            "clear": "erasetext",
            "delete": "erasetext",
            
            "screenshot": "takescreenshot",
            "capture": "takescreenshot",
            
            "goback": "back",
            "return": "back",
            
            "close": "closeapp",
            "exit": "closeapp",
            "quit": "closeapp",
            
            "launch": "launchapp",
            "open": "launchapp",
            "start": "launchapp",
            
            "tappoint": "taponpoint",
            "clickpoint": "taponpoint",
            "tapcoordinates": "taponpoint",
            
            "evaluate": "evaluate",
            "exec": "evaluate",
            "execute": "evaluate",
            
            "repeat": "repeat",
            "loop": "repeat",
            "iterate": "repeat",
            
            "hideKeyboard": "hidekeyboard",
            "dismissKeyboard": "hidekeyboard",
        }
        
        # Normalize action name using aliases
        if action in action_aliases:
            action = action_aliases[action]
        
        # Use specific handlers for common commands
        if hasattr(self, f"_handle_{action}"):
            return getattr(self, f"_handle_{action}")(target, value)
        
        # For commands in our specification
        if action in self.command_specs:
            spec = self.command_specs[action]
            original_name = spec["name"]  # Use original casing from JSON
            parameters = spec["parameters"]
            
            # Handle simple commands with no parameters
            if not parameters:
                return {original_name: {}}
            
            # If target exists but no parameters, use target as main value
            if target and not parameters and not value:
                return {original_name: target}
            
            # Build parameter structure based on command specs
            params = {}
            
            # Match parameters based on name patterns
            for param_name in parameters:
                param_lower = param_name.lower()
                
                # Text parameters
                if "text" in param_lower and value:
                    params[param_name] = value
                # Element parameters
                elif any(term in param_lower for term in ["element", "id", "selector"]) and target:
                    # Handle ID or element path formats
                    if target.startswith("/"):
                        params[param_name] = target
                    elif "id=" in target:
                        id_value = target.split("id=")[1].strip("'\"")
                        if param_name.lower() == "id":
                            params[param_name] = id_value
                        else:
                            params[param_name] = target
                    else:
                        params[param_name] = target
                # Direction parameters
                elif "direction" in param_lower and value.upper() in ["UP", "DOWN", "LEFT", "RIGHT"]:
                    params[param_name] = value.upper()
            
            # If no specific parameters but we have a target
            if not params and target:
                # Use target directly if the command examples show this pattern
                for example in spec.get("examples", []):
                    if ":" in example and not "{" in example:
                        return {original_name: target}
                
                # Otherwise use empty params
                return {original_name: {}}
            
            return {original_name: params or {}}
        
        # Default fallback for unrecognized commands
        return {action: {}} if action else None
    
    # Handler functions for specific commands
    
    def _handle_tapon(self, target: str, value: str) -> Dict:
        """Handle the tapOn command with proper formatting."""
        # Use ID-based selector if available
        if "id=" in target:
            id_value = re.search(r'id=[\'"](.*?)[\'"]', target)
            if id_value:
                return {"tapOn": {"id": id_value.group(1)}}
        
        # Use element path if it looks like one
        if target.startswith("/"):
            return {"tapOn": {"element": target}}
        
        # Use text-based targeting as fallback
        return {"tapOn": target}
    
    def _handle_inputtext(self, target: str, value: str) -> Dict:
        """Handle the inputText command."""
        return {"inputText": value}
    
    def _handle_assertvisible(self, target: str, value: str) -> Dict:
        """Handle the assertVisible command with proper formatting."""
        # Use ID-based selector if available
        if "id=" in target:
            id_value = re.search(r'id=[\'"](.*?)[\'"]', target)
            if id_value:
                return {"assertVisible": {"id": id_value.group(1)}}
        
        # Use element path if it looks like one
        if target.startswith("/"):
            return {"assertVisible": {"element": target}}
        
        # Use text-based targeting as fallback
        return {"assertVisible": target}
    
    def _handle_assertnotvisible(self, target: str, value: str) -> Dict:
        """Handle the assertNotVisible command with proper formatting."""
        # Use ID-based selector if available
        if "id=" in target:
            id_value = re.search(r'id=[\'"](.*?)[\'"]', target)
            if id_value:
                return {"assertNotVisible": {"id": id_value.group(1)}}
        
        # Use element path if it looks like one
        if target.startswith("/"):
            return {"assertNotVisible": {"element": target}}
        
        # Use text-based targeting as fallback
        return {"assertNotVisible": target}
    
    def _handle_scroll(self, target: str, value: str) -> Dict:
        """Handle the scroll command."""
        direction = value.upper() if value else "DOWN"
        return {"scroll": {"direction": direction}}
    
    def _handle_swipe(self, target: str, value: str) -> Dict:
        """Handle the swipe command with support for direction or coordinates."""
        if value.upper() in ["UP", "DOWN", "LEFT", "RIGHT"]:
            return {"swipe": {"direction": value.upper()}}
        
        # Try to parse complex swipe params
        try:
            # If value is a JSON string, parse it
            swipe_params = json.loads(value) if value else {"direction": "DOWN"}
            return {"swipe": swipe_params}
        except:
            # Default to downward swipe
            return {"swipe": {"direction": "DOWN"}}
    
    def _handle_scrolluntilvisible(self, target: str, value: str) -> Dict:
        """Handle the scrollUntilVisible command."""
        return {
            "scrollUntilVisible": {
                "element": target,
                "direction": value.upper() if value else "DOWN"
            }
        }
    
    def _handle_back(self, target: str, value: str) -> Dict:
        """Handle the back command."""
        return {"back": {}}
    
    def _handle_hidekeyboard(self, target: str, value: str) -> Dict:
        """Handle the hideKeyboard command."""
        return {"hideKeyboard": {}}
    
    def _handle_presskey(self, target: str, value: str) -> Dict:
        """Handle the pressKey command."""
        return {"pressKey": value or target}
    
    def _handle_launchapp(self, target: str, value: str) -> Dict:
        """Handle the launchApp command."""
        return {"launchApp": {"appId": value or target}}
    
    def _handle_erasetext(self, target: str, value: str) -> Dict:
        """Handle the eraseText command."""
        if value and value.isdigit():
            return {"eraseText": {"charactersToRemove": int(value)}}
        return {"eraseText": {}}
    
    def _handle_closeapp(self, target: str, value: str) -> Dict:
        """Handle the closeApp command."""
        return {"closeApp": {}}
    
    def _handle_takescreenshot(self, target: str, value: str) -> Dict:
        """Handle the takeScreenshot command."""
        if target or value:
            name = value or target
            return {"takeScreenshot": {"name": name}}
        return {"takeScreenshot": {}}
    
    def _handle_waitforanimationtoend(self, target: str, value: str) -> Dict:
        """Handle the waitForAnimationToEnd command."""
        if value and value.isdigit():
            return {"waitForAnimationToEnd": {"timeout": int(value)}}
        return {"waitForAnimationToEnd": {}}
    
    def _handle_longtapon(self, target: str, value: str) -> Dict:
        """Handle the longTapOn command."""
        # Use ID-based selector if available
        if "id=" in target:
            id_value = re.search(r'id=[\'"](.*?)[\'"]', target)
            if id_value:
                params = {"id": id_value.group(1)}
                if value and value.isdigit():
                    params["duration"] = int(value)
                return {"longTapOn": params}
        
        # Use element path if it looks like one
        if target.startswith("/"):
            params = {"element": target}
            if value and value.isdigit():
                params["duration"] = int(value)
            return {"longTapOn": params}
        
        # Use text-based targeting as fallback
        if value and value.isdigit():
            return {"longTapOn": {"text": target, "duration": int(value)}}
        return {"longTapOn": target}
    
    def _handle_doubletapon(self, target: str, value: str) -> Dict:
        """Handle the doubleTapOn command."""
        # Use ID-based selector if available
        if "id=" in target:
            id_value = re.search(r'id=[\'"](.*?)[\'"]', target)
            if id_value:
                return {"doubleTapOn": {"id": id_value.group(1)}}
        
        # Use element path if it looks like one
        if target.startswith("/"):
            return {"doubleTapOn": {"element": target}}
        
        # Use text-based targeting as fallback
        return {"doubleTapOn": target}
    
    def _handle_taponpoint(self, target: str, value: str) -> Dict:
        """Handle the tapOnPoint command."""
        # Try to parse coordinates from target or value
        coords = {}
        
        # Try parsing from JSON format
        try:
            coord_str = value or target
            if coord_str:
                # Handle JSON format like "{x: 0.5, y: 0.8}"
                if coord_str.startswith("{") and coord_str.endswith("}"):
                    coord_json = json.loads(coord_str.replace("'", "\""))
                    coords = {
                        "x": coord_json.get("x", 0.5),
                        "y": coord_json.get("y", 0.5)
                    }
                # Handle simple comma-separated format like "0.5,0.8"
                elif "," in coord_str:
                    x, y = coord_str.split(",", 1)
                    coords = {"x": float(x.strip()), "y": float(y.strip())}
        except:
            # Default to center of screen if parsing fails
            coords = {"x": 0.5, "y": 0.5}
        
        # If no coords were parsed, use defaults
        if not coords:
            coords = {"x": 0.5, "y": 0.5}
            
        return {"tapOnPoint": coords}
    
    def _handle_runflow(self, target: str, value: str) -> Dict:
        """Handle the runFlow command."""
        file_path = value or target
        return {"runFlow": {"file": file_path}}
    
    def _handle_wait(self, target: str, value: str) -> Dict:
        """Handle the wait command."""
        # Default to 1000ms if no time specified
        wait_time = 1000
        
        # Try to parse wait time from value or target
        time_value = value or target
        if time_value:
            try:
                # Handle numeric input
                if time_value.isdigit():
                    wait_time = int(time_value)
                # Handle JSON format like "{time: 2000}"
                elif time_value.startswith("{") and time_value.endswith("}"):
                    time_json = json.loads(time_value.replace("'", "\""))
                    wait_time = time_json.get("time", 1000)
            except:
                # Use default if parsing fails
                wait_time = 1000
                
        return {"wait": {"time": wait_time}}
    
    def _handle_evaluate(self, target: str, value: str) -> Dict:
        """Handle the evaluate command."""
        expression = value or target
        return {"evaluate": {"expression": expression}}
    
    def _handle_extendedwaituntil(self, target: str, value: str) -> Dict:
        """Handle the extendedWaitUntil command."""
        # Try to parse options from target/value
        params = {}
        
        # The condition is mandatory
        params["condition"] = target
        
        # Try to parse timeout and pollInterval from value
        if value:
            try:
                # Handle JSON format
                if value.startswith("{") and value.endswith("}"):
                    value_json = json.loads(value.replace("'", "\""))
                    if "timeout" in value_json:
                        params["timeout"] = value_json["timeout"]
                    if "pollInterval" in value_json:
                        params["pollInterval"] = value_json["pollInterval"]
            except:
                # No additional parameters if parsing fails
                pass
                
        return {"extendedWaitUntil": params}
    
    def _handle_repeat(self, target: str, value: str) -> Dict:
        """Handle the repeat command."""
        # Default parameters
        params = {
            "times": 1,
            "commands": []
        }
        
        # Try to parse from value
        if value:
            try:
                # Handle JSON format
                if value.startswith("{") and value.endswith("}"):
                    value_json = json.loads(value.replace("'", "\""))
                    if "times" in value_json:
                        params["times"] = value_json["times"]
                    if "commands" in value_json:
                        params["commands"] = value_json["commands"]
            except:
                # Use defaults if parsing fails
                pass
        
        return {"repeat": params}