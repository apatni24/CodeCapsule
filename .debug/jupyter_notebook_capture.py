#!/usr/bin/env python3
"""
Enhanced Jupyter Notebook Capture System
Captures notebook content, cell execution, and changes to .ipynb files
"""

import os
import sys
import json
import logging
import threading
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import nbformat
from nbformat import read as read_notebook, write as write_notebook

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/jupyter_capture.log')
    ]
)
logger = logging.getLogger('jupyter_capture')

class JupyterNotebookCapture:
    """Enhanced Jupyter notebook capture system"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.workspace = Path('/home/user/workspace')
        self.notebook_states = {}  # Track notebook file states
        self.cell_execution_history = {}  # Track cell execution history
        self.running = False
        self.hooks_installed = False
        self.last_notebook_check = 0
        self.check_interval = 1  # Check every 1 second for more responsiveness
        
        logger.info(f"Initialized Jupyter notebook capture for job: {job_id}")
    
    def start(self):
        """Start notebook monitoring"""
        self.running = True
        
        # Start notebook file monitoring
        self.notebook_thread = threading.Thread(target=self._monitor_notebook_files, daemon=True)
        self.notebook_thread.start()
        logger.info("Notebook file monitoring started")
        
        # Start cell execution monitoring
        self.cell_thread = threading.Thread(target=self._monitor_cell_execution, daemon=True)
        self.cell_thread.start()
        logger.info("Cell execution monitoring started")
        
        # Setup enhanced Jupyter hooks
        self._setup_enhanced_jupyter_hooks()
        
        # Start periodic hook installation check
        self.hook_thread = threading.Thread(target=self._ensure_hooks_installed, daemon=True)
        self.hook_thread.start()
        logger.info("Hook monitoring started")
    
    def stop(self):
        """Stop notebook monitoring"""
        self.running = False
        logger.info("Jupyter notebook capture stopped")
    
    def _ensure_hooks_installed(self):
        """Periodically ensure Jupyter hooks are installed"""
        logger.debug("Hook monitoring thread started")
        
        while self.running:
            try:
                if not self.hooks_installed:
                    self._setup_enhanced_jupyter_hooks()
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in hook monitoring: {e}")
                time.sleep(30)
        
        logger.debug("Hook monitoring thread stopped")
    
    def _monitor_notebook_files(self):
        """Monitor .ipynb files for changes"""
        logger.debug("Notebook file monitoring thread started")
        
        # Initial scan for existing notebooks
        self._scan_notebook_files()
        
        while self.running:
            try:
                # Scan for new or modified notebooks
                self._scan_notebook_files()
                time.sleep(self.check_interval)  # Check every 1 second for responsiveness
                
            except Exception as e:
                logger.error(f"Error in notebook file monitoring: {e}")
                time.sleep(5)
        
        logger.debug("Notebook file monitoring thread stopped")
    
    def _scan_notebook_files(self):
        """Scan workspace for .ipynb files"""
        if not self.workspace.exists():
            return
        
        current_time = time.time()
        
        for notebook_path in self.workspace.rglob('*.ipynb'):
            notebook_str = str(notebook_path)
            try:
                current_state = {
                    'mtime': notebook_path.stat().st_mtime,
                    'size': notebook_path.stat().st_size
                }
                
                if notebook_str not in self.notebook_states:
                    # New notebook
                    logger.info(f"New notebook detected: {notebook_str}")
                    self._capture_notebook_content(notebook_str, 'create')
                    self.notebook_states[notebook_str] = current_state
                    
                elif (self.notebook_states[notebook_str]['mtime'] != current_state['mtime'] or 
                      self.notebook_states[notebook_str]['size'] != current_state['size']):
                    # Modified notebook
                    logger.info(f"Notebook modified: {notebook_str}")
                    self._capture_notebook_content(notebook_str, 'edit')
                    self.notebook_states[notebook_str] = current_state
                    
            except Exception as e:
                logger.error(f"Error scanning notebook {notebook_str}: {e}")
    
    def _capture_notebook_content(self, notebook_path: str, action: str):
        """Capture notebook content and structure"""
        try:
            notebook = read_notebook(notebook_path, as_version=4)
            
            # Extract notebook metadata
            metadata = {
                'nbformat': notebook.nbformat,
                'nbformat_minor': notebook.nbformat_minor,
                'metadata': dict(notebook.metadata) if notebook.metadata else {},
                'cell_count': len(notebook.cells),
                'cell_types': self._get_cell_type_counts(notebook.cells)
            }
            
            # Extract cell content
            cells_data = []
            for i, cell in enumerate(notebook.cells):
                cell_data = {
                    'index': i,
                    'cell_type': cell.cell_type,
                    'source': cell.source,
                    'metadata': dict(cell.metadata) if cell.metadata else {}
                }
                
                # Add execution count and outputs for code cells
                if cell.cell_type == 'code':
                    cell_data['execution_count'] = cell.execution_count
                    cell_data['outputs'] = self._extract_outputs(cell.outputs)
                
                cells_data.append(cell_data)
            
            # Create comprehensive notebook capture
            notebook_capture = {
                'notebook_path': notebook_path,
                'action': action,
                'timestamp': datetime.now().isoformat(),
                'metadata': metadata,
                'cells': cells_data,
                'total_cells': len(cells_data),
                'code_cells': len([c for c in cells_data if c['cell_type'] == 'code']),
                'markdown_cells': len([c for c in cells_data if c['cell_type'] == 'markdown']),
                'raw_cells': len([c for c in cells_data if c['cell_type'] == 'raw'])
            }
            
            # Capture to context
            self._capture_notebook_to_context(notebook_capture)
            
            logger.info(f"Successfully captured notebook: {notebook_path}")
            
        except Exception as e:
            logger.error(f"Error capturing notebook {notebook_path}: {e}")
            # Capture error as context
            error_capture = {
                'notebook_path': notebook_path,
                'action': action,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            self._capture_notebook_to_context(error_capture, is_error=True)
    
    def _get_cell_type_counts(self, cells) -> Dict[str, int]:
        """Get counts of different cell types"""
        counts = {'code': 0, 'markdown': 0, 'raw': 0}
        for cell in cells:
            counts[cell.cell_type] = counts.get(cell.cell_type, 0) + 1
        return counts
    
    def _extract_outputs(self, outputs) -> List[Dict]:
        """Extract and format cell outputs"""
        formatted_outputs = []
        for output in outputs:
            output_data = {
                'output_type': output.output_type,
                'metadata': dict(output.metadata) if output.metadata else {}
            }
            
            if output.output_type == 'stream':
                output_data['name'] = output.name
                output_data['text'] = output.text
            elif output.output_type == 'display_data':
                output_data['data'] = dict(output.data) if output.data else {}
            elif output.output_type == 'execute_result':
                output_data['execution_count'] = output.execution_count
                output_data['data'] = dict(output.data) if output.data else {}
            elif output.output_type == 'error':
                output_data['ename'] = output.ename
                output_data['evalue'] = output.evalue
                output_data['traceback'] = output.traceback
            
            formatted_outputs.append(output_data)
        
        return formatted_outputs
    
    def _capture_notebook_to_context(self, notebook_data: Dict, is_error: bool = False):
        """Capture notebook data to context manager"""
        try:
            from context_manager import append_to_context
            
            if is_error:
                content = f"NOTEBOOK ERROR: {notebook_data['notebook_path']}\nError: {notebook_data['error']}"
                context_type = 'notebook_error'
            else:
                # Create a readable summary
                summary = f"NOTEBOOK: {notebook_data['notebook_path']}\n"
                summary += f"Action: {notebook_data['action']}\n"
                summary += f"Cells: {notebook_data['total_cells']} total "
                summary += f"({notebook_data['code_cells']} code, "
                summary += f"{notebook_data['markdown_cells']} markdown, "
                summary += f"{notebook_data['raw_cells']} raw)\n"
                
                # Add cell summaries
                for cell in notebook_data['cells'][:5]:  # First 5 cells
                    cell_type = cell['cell_type']
                    source_preview = cell['source'][:100].replace('\n', ' ')
                    summary += f"  [{cell['index']}] {cell_type}: {source_preview}...\n"
                
                if len(notebook_data['cells']) > 5:
                    summary += f"  ... and {len(notebook_data['cells']) - 5} more cells\n"
                
                content = summary
                context_type = 'notebook'
            
            metadata = {
                'type': 'jupyter_notebook',
                'notebook_path': notebook_data.get('notebook_path', ''),
                'action': notebook_data.get('action', ''),
                'is_error': is_error
            }
            
            append_to_context(self.job_id, content, context_type, metadata)
            logger.debug(f"Captured notebook to context: {context_type}")
            
        except ImportError as e:
            logger.error(f"Failed to import context_manager: {e}")
        except Exception as e:
            logger.error(f"Error capturing notebook to context: {e}")
    
    def _monitor_cell_execution(self):
        """Monitor individual cell execution"""
        logger.debug("Cell execution monitoring thread started")
        
        while self.running:
            try:
                # Monitor for active Jupyter processes and ensure hooks are installed
                self._check_jupyter_processes()
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in cell execution monitoring: {e}")
                time.sleep(10)
        
        logger.debug("Cell execution monitoring thread stopped")
    
    def _check_jupyter_processes(self):
        """Check for active Jupyter processes and ensure hooks are installed"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'jupyter' in proc.info['name'].lower():
                        logger.debug(f"Found Jupyter process: {proc.info['name']} (PID: {proc.info['pid']})")
                        # Ensure hooks are installed when Jupyter is running
                        if not self.hooks_installed:
                            self._setup_enhanced_jupyter_hooks()
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            # psutil not available, try alternative method
            try:
                result = os.popen('pgrep -f jupyter').read().strip()
                if result:
                    logger.debug(f"Found Jupyter processes: {result}")
                    if not self.hooks_installed:
                        self._setup_enhanced_jupyter_hooks()
            except:
                pass
    
    def _setup_enhanced_jupyter_hooks(self):
        """Setup enhanced Jupyter execution hooks"""
        if self.hooks_installed:
            return
            
        logger.debug("Setting up enhanced Jupyter hooks")
        try:
            import IPython
            from IPython.core.interactiveshell import InteractiveShell
            
            # Store original method
            if not hasattr(InteractiveShell, '_original_run_cell'):
                InteractiveShell._original_run_cell = InteractiveShell.run_cell
            
            def run_cell_with_enhanced_capture(self, raw_cell, *args, **kwargs):
                # Capture cell execution start
                cell_id = f"cell_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                logger.info(f"Cell execution started: {cell_id}")
                
                # Capture the code before execution
                cell_capture = {
                    'cell_id': cell_id,
                    'code': raw_cell,
                    'execution_start': datetime.now().isoformat(),
                    'cell_type': 'code'
                }
                
                try:
                    # Execute the cell using original method
                    result = InteractiveShell._original_run_cell(self, raw_cell, *args, **kwargs)
                    
                    # Capture execution result
                    cell_capture['execution_end'] = datetime.now().isoformat()
                    cell_capture['success'] = True
                    
                    # Try to capture output
                    try:
                        # Get the last execution result
                        if hasattr(self, 'last_execution_result'):
                            cell_capture['output'] = str(self.last_execution_result)
                        elif hasattr(self, 'user_ns'):
                            # Try to get the last result from user namespace
                            if '_' in self.user_ns:
                                cell_capture['output'] = str(self.user_ns['_'])
                    except:
                        pass
                    
                    self._capture_cell_execution(cell_capture)
                    logger.info(f"Cell execution completed: {cell_id}")
                    
                    return result
                    
                except Exception as e:
                    # Capture execution error
                    cell_capture['execution_end'] = datetime.now().isoformat()
                    cell_capture['success'] = False
                    cell_capture['error'] = str(e)
                    cell_capture['error_type'] = type(e).__name__
                    
                    self._capture_cell_execution(cell_capture)
                    logger.error(f"Cell execution failed: {cell_id} - {e}")
                    raise
            
            # Install the hook
            InteractiveShell.run_cell = run_cell_with_enhanced_capture
            self.hooks_installed = True
            logger.info("Enhanced Jupyter hooks installed successfully")
            
        except ImportError as e:
            logger.warning(f"IPython not available, enhanced hooks not installed: {e}")
        except Exception as e:
            logger.error(f"Error setting up Jupyter hooks: {e}")
    
    def _capture_cell_execution(self, cell_data: Dict):
        """Capture individual cell execution"""
        try:
            from context_manager import append_to_context
            
            # Create readable cell execution summary
            summary = f"CELL EXECUTION: {cell_data['cell_id']}\n"
            summary += f"Success: {cell_data['success']}\n"
            summary += f"Code:\n{cell_data['code']}\n"
            
            if cell_data['success'] and 'output' in cell_data:
                summary += f"Output:\n{cell_data['output']}\n"
            elif not cell_data['success']:
                summary += f"Error: {cell_data['error']}\n"
            
            metadata = {
                'type': 'jupyter_cell_execution',
                'cell_id': cell_data['cell_id'],
                'success': cell_data['success'],
                'execution_time': cell_data.get('execution_end', '')
            }
            
            append_to_context(self.job_id, summary, 'jupyter_cells', metadata)
            logger.debug(f"Captured cell execution: {cell_data['cell_id']}")
            
        except ImportError as e:
            logger.error(f"Failed to import context_manager: {e}")
        except Exception as e:
            logger.error(f"Error capturing cell execution: {e}")
    
    def get_notebook_summary(self, notebook_path: str) -> Optional[Dict]:
        """Get a summary of a specific notebook"""
        try:
            notebook = read_notebook(notebook_path, as_version=4)
            
            summary = {
                'path': notebook_path,
                'cell_count': len(notebook.cells),
                'cell_types': self._get_cell_type_counts(notebook.cells),
                'last_modified': datetime.fromtimestamp(
                    Path(notebook_path).stat().st_mtime
                ).isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting notebook summary for {notebook_path}: {e}")
            return None
    
    def list_notebooks(self) -> List[Dict]:
        """List all notebooks in the workspace"""
        notebooks = []
        
        if not self.workspace.exists():
            return notebooks
        
        for notebook_path in self.workspace.rglob('*.ipynb'):
            summary = self.get_notebook_summary(str(notebook_path))
            if summary:
                notebooks.append(summary)
        
        return notebooks

# Global notebook capture instance
_notebook_capture = None

def start_notebook_capture(job_id: str):
    """Start Jupyter notebook capture"""
    global _notebook_capture
    if _notebook_capture is None:
        _notebook_capture = JupyterNotebookCapture(job_id)
        _notebook_capture.start()
    return _notebook_capture

def stop_notebook_capture():
    """Stop Jupyter notebook capture"""
    global _notebook_capture
    if _notebook_capture:
        _notebook_capture.stop()
        _notebook_capture = None

def get_notebook_capture_instance():
    """Get the current notebook capture instance"""
    return _notebook_capture 