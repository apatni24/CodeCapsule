#!/usr/bin/env python3
"""
Jupyter Extension for Automatic Context Capture
Automatically installs capture hooks when Jupyter starts
"""

import os
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/jupyter_extension.log')
    ]
)
logger = logging.getLogger('jupyter_extension')

def load_jupyter_extension(ipython):
    """Load the Jupyter extension"""
    logger.info("Loading Jupyter extension for context capture")
    
    try:
        # Get job_id from environment
        job_id = os.environ.get('JOB_ID')
        if not job_id:
            logger.warning("No JOB_ID found in environment")
            return
        
        # Add workspace to path
        workspace_path = '/home/user/workspace'
        if workspace_path not in sys.path:
            sys.path.insert(0, workspace_path)
        
        # Import and start notebook capture
        try:
            from jupyter_notebook_capture import start_notebook_capture
            notebook_capture = start_notebook_capture(job_id)
            logger.info(f"Started notebook capture for job: {job_id}")
            
            # Store reference in IPython namespace for debugging
            ipython.user_ns['_notebook_capture'] = notebook_capture
            logger.info("Notebook capture instance stored in IPython namespace as '_notebook_capture'")
            
        except ImportError as e:
            logger.error(f"Failed to import jupyter_notebook_capture: {e}")
        except Exception as e:
            logger.error(f"Failed to start notebook capture: {e}")
    
    except Exception as e:
        logger.error(f"Error loading Jupyter extension: {e}")

def unload_jupyter_extension(ipython):
    """Unload the Jupyter extension"""
    logger.info("Unloading Jupyter extension")
    
    try:
        from jupyter_notebook_capture import stop_notebook_capture
        stop_notebook_capture()
        logger.info("Stopped notebook capture")
    except Exception as e:
        logger.error(f"Error unloading Jupyter extension: {e}")

# Auto-load when imported
if __name__ == '__main__':
    logger.info("Jupyter extension module loaded") 