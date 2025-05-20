import subprocess
import os

class ExecutionEngine:
    def __init__(self):
        pass
        
    def run_flow(self, flow_path):
        """Run a Maestro flow on the connected device/emulator"""
        # Check if the flow file exists
        if not os.path.exists(flow_path):
            return {
                "success": False,
                "error": f"Flow file {flow_path} not found"
            }
            
        # Run the Maestro flow
        try:
            result = subprocess.run(
                ["maestro", "test", flow_path],
                capture_output=True,
                text=True
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }