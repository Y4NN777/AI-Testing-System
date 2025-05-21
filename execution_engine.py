import subprocess
import os
import json
import time
import re

class ExecutionEngine:
    def __init__(self, results_dir="./test_results"):
        """
        Initialize the execution engine for running Maestro flows.
        
        Args:
            results_dir (str): Directory to store test execution results
        """
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)
    
    def execute_flow(self, flow_path):
        """
        Execute a Maestro flow and collect results.
        
        Args:
            flow_path (str): Path to the Maestro flow file
            
        Returns:
            dict: Execution result including success status, logs, and screenshots
        """
        print(f"Executing Maestro flow: {flow_path}")
        
        # Create unique result directory for this execution
        timestamp = int(time.time())
        flow_name = os.path.basename(flow_path).replace(".yaml", "")
        result_dir = f"{self.results_dir}/{flow_name}_{timestamp}"
        os.makedirs(result_dir, exist_ok=True)
        
        try:
            # Execute the Maestro flow
            log_path = f"{result_dir}/execution.log"
            command = ["maestro", "test", "-v", flow_path]
            
            with open(log_path, "w") as log_file:
                process = subprocess.Popen(
                    command,
                    stdout=log_file,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stderr = process.communicate()[1]
                return_code = process.returncode
            
            # Read the log file
            with open(log_path, "r") as log_file:
                logs = log_file.read()
            
            # Parse execution results
            execution_time = self._extract_execution_time(logs)
            screenshots = self._collect_screenshots(logs, result_dir)
            errors = self._extract_errors(logs, stderr)
            
            success = return_code == 0 and not errors
            
            # Create result summary
            result = {
                "success": success,
                "flow_path": flow_path,
                "result_dir": result_dir,
                "log_path": log_path,
                "return_code": return_code,
                "execution_time": execution_time,
                "screenshots": screenshots,
                "errors": errors
            }
            
            # Save result summary as JSON
            with open(f"{result_dir}/result_summary.json", "w") as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            error_message = str(e)
            print(f"Error executing flow: {error_message}")
            
            # Log the error
            with open(f"{result_dir}/error.log", "w") as f:
                f.write(error_message)
            
            return {
                "success": False,
                "flow_path": flow_path,
                "result_dir": result_dir,
                "error": error_message
            }
    
    def _extract_execution_time(self, logs):
        """Extract execution time from Maestro logs"""
        time_match = re.search(r"Test completed in (\d+\.\d+)s", logs)
        if time_match:
            return float(time_match.group(1))
        return None
    
    def _collect_screenshots(self, logs, result_dir):
        """
        Collect screenshots taken during test execution.
        
        This function attempts to find references to screenshots in the logs
        and collects them for the result summary.
        """
        screenshots = []
        # Regular expression to match screenshot mentions in logs
        screenshot_matches = re.finditer(r"Screenshot saved (?:at|to) [\"']?([^\"'\s]+)", logs)
        
        for match in screenshot_matches:
            screenshot_path = match.group(1)
            # Copy or move screenshot to result directory if needed
            screenshot_name = os.path.basename(screenshot_path)
            destination = f"{result_dir}/{screenshot_name}"
            
            try:
                if os.path.exists(screenshot_path) and screenshot_path != destination:
                    # Copy screenshot to result directory
                    with open(screenshot_path, "rb") as src, open(destination, "wb") as dst:
                        dst.write(src.read())
                
                screenshots.append({
                    "original_path": screenshot_path,
                    "result_path": destination
                })
            except Exception as e:
                print(f"Failed to process screenshot {screenshot_path}: {e}")
        
        return screenshots
    
    def _extract_errors(self, logs, stderr):
        """Extract error information from logs and stderr"""
        errors = []
        
        # Check stderr
        if stderr:
            errors.append({
                "source": "stderr",
                "message": stderr.strip()
            })
        
        # Look for error patterns in logs
        error_patterns = [
            r"Error: (.+?)(?:\n|$)",
            r"Exception: (.+?)(?:\n|$)",
            r"Failed: (.+?)(?:\n|$)",
            r"Assertion failed: (.+?)(?:\n|$)"
        ]
        
        for pattern in error_patterns:
            for match in re.finditer(pattern, logs, re.IGNORECASE):
                errors.append({
                    "source": "log",
                    "message": match.group(1).strip()
                })
        
        return errors
    
    def generate_report(self, result):
        """
        Generate a human-readable test execution report.
        
        Args:
            result (dict): Execution result from execute_flow
            
        Returns:
            str: Path to the generated HTML report
        """
        if not result:
            return None
            
        result_dir = result.get("result_dir")
        if not result_dir or not os.path.exists(result_dir):
            return None
            
        # Create a simple HTML report
        report_path = f"{result_dir}/report.html"
        
        try:
            with open(report_path, "w") as f:
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>Test Execution Report - {os.path.basename(result.get('flow_path', 'Unknown'))}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 10px; margin-bottom: 20px; }}
        .success {{ color: green; }}
        .failure {{ color: red; }}
        .section {{ margin-bottom: 20px; border: 1px solid #ddd; padding: 10px; }}
        .error {{ background-color: #ffeeee; padding: 10px; margin: 5px 0; border-left: 3px solid red; }}
        img {{ max-width: 300px; border: 1px solid #ddd; margin: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Test Execution Report</h1>
        <p>Flow: <strong>{os.path.basename(result.get('flow_path', 'Unknown'))}</strong></p>
        <p>Status: <span class="{'success' if result.get('success') else 'failure'}">
            {'SUCCESS' if result.get('success') else 'FAILURE'}
        </span></p>
        <p>Execution Time: {result.get('execution_time', 'Unknown')}s</p>
        <p>Timestamp: {time.ctime()}</p>
    </div>
""")

                # Error section
                if result.get('errors'):
                    f.write('<div class="section"><h2>Errors</h2>\n')
                    for error in result.get('errors', []):
                        f.write(f'<div class="error">\n')
                        f.write(f'<p><strong>Source:</strong> {error.get("source", "Unknown")}</p>\n')
                        f.write(f'<p>{error.get("message", "Unknown error")}</p>\n')
                        f.write('</div>\n')
                    f.write('</div>\n')
                
                # Screenshots section
                if result.get('screenshots'):
                    f.write('<div class="section"><h2>Screenshots</h2>\n')
                    for screenshot in result.get('screenshots', []):
                        result_path = screenshot.get('result_path')
                        if result_path and os.path.exists(result_path):
                            relative_path = os.path.basename(result_path)
                            f.write(f'<div>\n')
                            f.write(f'<img src="{relative_path}" alt="Screenshot" />\n')
                            f.write(f'<p>{relative_path}</p>\n')
                            f.write('</div>\n')
                    f.write('</div>\n')
                
                # Log excerpt section
                if os.path.exists(result.get('log_path', '')):
                    f.write('<div class="section"><h2>Log Excerpt</h2>\n')
                    f.write('<pre>\n')
                    with open(result.get('log_path'), 'r') as log_file:
                        # Get the last 50 lines of log
                        log_lines = log_file.readlines()[-50:]
                        for line in log_lines:
                            f.write(line.replace('<', '&lt;').replace('>', '&gt;'))
                    f.write('</pre>\n')
                    f.write('</div>\n')
                
                f.write('</body>\n</html>')
            
            return report_path
            
        except Exception as e:
            print(f"Error generating report: {e}")
            return None