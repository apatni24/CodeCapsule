import os
import sys
import subprocess
import threading
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/auto_capture.log')
    ]
)
logger = logging.getLogger('auto_capture')

# Add context manager to path - use the correct workspace path
workspace_path = '/home/user/workspace'
if workspace_path not in sys.path:
    sys.path.insert(0, workspace_path)
    logger.debug(f"Added {workspace_path} to sys.path")

try:
    from context_manager import (
        capture_shell_command, capture_code_execution, 
        capture_file_change, capture_user_prompt,
        get_context_summary
    )
    logger.info("Successfully imported context_manager functions")
except ImportError as e:
    logger.error(f"Could not import context_manager: {e}")
    logger.error(f"sys.path: {sys.path}")
    logger.error(f"Current directory: {os.getcwd()}")
    logger.error(f"Files in workspace: {list(Path(workspace_path).glob('*.py')) if Path(workspace_path).exists() else 'Workspace does not exist'}")
    
    # Define fallback functions
    def capture_shell_command(job_id, command, output="", exit_code=0):
        logger.warning(f"Fallback: Shell command captured: {command}")
    
    def capture_code_execution(job_id, code, output="", error=""):
        logger.warning(f"Fallback: Code execution captured: {code[:50]}...")
    
    def capture_file_change(job_id, file_path, action, content=""):
        logger.warning(f"Fallback: File change captured: {action} {file_path}")
    
    def capture_user_prompt(job_id, prompt, response=""):
        logger.warning(f"Fallback: User prompt captured: {prompt[:50]}...")
    
    def get_context_summary(job_id):
        return {"error": "Context manager not available"}

class AutoCapture:
    """Automatic context capture system"""
    
    def __init__(self, job_id: str):
        logger.info(f"Initializing AutoCapture for job: {job_id}")
        self.job_id = job_id
        self.file_watchers = {}
        self.shell_history_file = os.path.expanduser("~/.bash_history")
        self.last_shell_position = 0
        self.running = False
        self.notebook_capture = None  # Enhanced notebook capture
        
        logger.debug(f"Shell history file: {self.shell_history_file}")
        logger.debug(f"Shell history exists: {os.path.exists(self.shell_history_file)}")
        
    def start(self):
        """Start all capture systems"""
        logger.info(f"Starting auto-capture for job: {self.job_id}")
        self.running = True
        
        # Start shell command capture
        self.shell_thread = threading.Thread(target=self._capture_shell_commands, daemon=True)
        self.shell_thread.start()
        logger.debug("Shell capture thread started")
        
        # Start file change monitoring
        self.file_thread = threading.Thread(target=self._monitor_file_changes, daemon=True)
        self.file_thread.start()
        logger.debug("File monitoring thread started")
        
        # Setup Python execution hooks
        self._setup_python_hooks()
        
        # Start enhanced Jupyter notebook capture
        self._start_notebook_capture()
        
        logger.info(f"Auto-capture started for job: {self.job_id}")
    
    def stop(self):
        """Stop all capture systems"""
        logger.info(f"Stopping auto-capture for job: {self.job_id}")
        self.running = False
        
        # Stop notebook capture
        if self.notebook_capture:
            self.notebook_capture.stop()
    
    def _start_notebook_capture(self):
        """Start enhanced Jupyter notebook capture"""
        try:
            from jupyter_notebook_capture import start_notebook_capture
            self.notebook_capture = start_notebook_capture(self.job_id)
            logger.info("Enhanced Jupyter notebook capture started")
        except ImportError as e:
            logger.warning(f"Enhanced notebook capture not available: {e}")
        except Exception as e:
            logger.error(f"Failed to start notebook capture: {e}")
    
    def _capture_shell_commands(self):
        """Monitor shell history for new commands"""
        logger.debug("Shell capture thread started")
        while self.running:
            try:
                if os.path.exists(self.shell_history_file):
                    with open(self.shell_history_file, 'r') as f:
                        lines = f.readlines()
                    
                    logger.debug(f"Shell history lines: {len(lines)}, last position: {self.last_shell_position}")
                    
                    if len(lines) > self.last_shell_position:
                        new_commands = lines[self.last_shell_position:]
                        logger.debug(f"Found {len(new_commands)} new commands")
                        
                        for cmd in new_commands:
                            cmd = cmd.strip()
                            if cmd and not cmd.startswith('#'):
                                logger.debug(f"Processing command: {cmd}")
                                # Try to get command output (basic implementation)
                                try:
                                    result = subprocess.run(
                                        cmd, shell=True, capture_output=True, text=True, timeout=5
                                    )
                                    output = result.stdout + result.stderr
                                    logger.debug(f"Command output: {output[:100]}...")
                                    logger.debug(f"Command exit code: {result.returncode}")
                                    
                                    capture_shell_command(
                                        self.job_id, cmd, output, result.returncode
                                    )
                                    logger.debug(f"Successfully captured shell command: {cmd}")
                                except Exception as e:
                                    logger.error(f"Error executing command {cmd}: {e}")
                                    capture_shell_command(
                                        self.job_id, cmd, f"Error: {str(e)}", -1
                                    )
                        
                        self.last_shell_position = len(lines)
                        logger.debug(f"Updated last position to: {self.last_shell_position}")
                else:
                    logger.debug(f"Shell history file does not exist: {self.shell_history_file}")
                
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in shell capture: {e}")
                time.sleep(5)
        
        logger.debug("Shell capture thread stopped")
    
    def _monitor_file_changes(self):
        """Monitor workspace for file changes"""
        logger.debug("File monitoring thread started")
        workspace = Path('/home/user/workspace')
        file_states = {}
        
        logger.debug(f"Workspace path: {workspace}")
        logger.debug(f"Workspace exists: {workspace.exists()}")
        
        # Initial scan
        if workspace.exists():
            for file_path in workspace.rglob('*'):
                if file_path.is_file():
                    file_states[str(file_path)] = {
                        'mtime': file_path.stat().st_mtime,
                        'size': file_path.stat().st_size
                    }
            logger.debug(f"Initial scan found {len(file_states)} files")
        
        while self.running:
            try:
                if workspace.exists():
                    for file_path in workspace.rglob('*'):
                        if file_path.is_file() and not str(file_path).startswith('/home/user/workspace/context/'):
                            file_str = str(file_path)
                            current_state = {
                                'mtime': file_path.stat().st_mtime,
                                'size': file_path.stat().st_size
                            }
                            
                            if file_str not in file_states:
                                # New file
                                logger.debug(f"New file detected: {file_str}")
                                try:
                                    with open(file_path, 'r') as f:
                                        content = f.read()
                                    capture_file_change(
                                        self.job_id, file_str, 'create', content
                                    )
                                    logger.debug(f"Successfully captured file creation: {file_str}")
                                except Exception as e:
                                    logger.error(f"Error reading file {file_str}: {e}")
                                    capture_file_change(
                                        self.job_id, file_str, 'create', "[binary or unreadable]"
                                    )
                            elif (file_states[file_str]['mtime'] != current_state['mtime'] or 
                                  file_states[file_str]['size'] != current_state['size']):
                                # Modified file
                                logger.debug(f"File modified: {file_str}")
                                try:
                                    with open(file_path, 'r') as f:
                                        content = f.read()
                                    capture_file_change(
                                        self.job_id, file_str, 'edit', content
                                    )
                                    logger.debug(f"Successfully captured file modification: {file_str}")
                                except Exception as e:
                                    logger.error(f"Error reading modified file {file_str}: {e}")
                                    capture_file_change(
                                        self.job_id, file_str, 'edit', "[binary or unreadable]"
                                    )
                            
                            file_states[file_str] = current_state
                else:
                    logger.debug("Workspace does not exist")
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in file monitoring: {e}")
                time.sleep(10)
        
        logger.debug("File monitoring thread stopped")
    
    def _setup_python_hooks(self):
        """Setup hooks for Python code execution"""
        logger.debug("Setting up Python execution hooks")
        try:
            # Hook into IPython/Jupyter if available
            import IPython
            from IPython.core.interactiveshell import InteractiveShell
            
            original_run_cell = InteractiveShell.run_cell
            
            def run_cell_with_capture(self, raw_cell, *args, **kwargs):
                # Capture the code before execution
                logger.debug(f"Capturing code execution: {raw_cell[:100]}...")
                capture_code_execution(self.job_id, raw_cell)
                
                # Execute and capture output
                try:
                    result = original_run_cell(self, raw_cell, *args, **kwargs)
                    # Note: IPython handles output display, so we don't capture it here
                    return result
                except Exception as e:
                    logger.error(f"Error in code execution: {e}")
                    capture_code_execution(self.job_id, raw_cell, error=str(e))
                    raise
            
            InteractiveShell.run_cell = run_cell_with_capture
            logger.info("Python execution hooks installed")
            
        except ImportError as e:
            logger.warning(f"IPython not available, Python hooks not installed: {e}")
    
    def capture_manual(self, context_type: str, content: str, metadata: Dict = None):
        """Manually capture content"""
        logger.debug(f"Manual capture - type: {context_type}, content: {content[:100]}...")
        try:
            from context_manager import append_to_context
            append_to_context(self.job_id, content, context_type, metadata)
            logger.debug(f"Successfully captured manual entry: {context_type}")
        except ImportError as e:
            logger.error(f"Failed to import append_to_context: {e}")
            print(f"Manual capture: {context_type} - {content[:50]}...")
    
    def get_notebook_summary(self) -> Dict:
        """Get summary of all notebooks in workspace"""
        if self.notebook_capture:
            try:
                return {
                    'notebooks': self.notebook_capture.list_notebooks(),
                    'capture_active': True
                }
            except Exception as e:
                logger.error(f"Error getting notebook summary: {e}")
                return {'error': str(e), 'capture_active': False}
        else:
            return {'capture_active': False, 'message': 'Notebook capture not available'}

# Global capture instance
_auto_capture = None

def start_auto_capture(job_id: str):
    """Start automatic context capture"""
    global _auto_capture
    logger.info(f"Starting auto-capture for job: {job_id}")
    
    if _auto_capture is None:
        _auto_capture = AutoCapture(job_id)
        _auto_capture.start()
        logger.info(f"Auto-capture instance created and started")
    else:
        logger.warning(f"Auto-capture instance already exists: {_auto_capture.job_id}")
    
    return _auto_capture

def stop_auto_capture():
    """Stop automatic context capture"""
    global _auto_capture
    if _auto_capture:
        logger.info(f"Stopping auto-capture for job: {_auto_capture.job_id}")
        _auto_capture.stop()
        _auto_capture = None
        logger.info("Auto-capture stopped")

def get_capture_instance():
    """Get the current capture instance"""
    return _auto_capture

# Auto-start if JOB_ID is available
job_id = os.environ.get('JOB_ID')
if job_id:
    logger.info(f"Auto-starting capture for job: {job_id}")
    start_auto_capture(job_id)
else:
    logger.warning("No JOB_ID found in environment, auto-capture not started") 