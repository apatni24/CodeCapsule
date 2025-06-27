#!/usr/bin/env python3
"""
Jupyter Configuration for CodeCapsule
Configures Jupyter to work with the context capture system
"""

import os
import sys
from pathlib import Path

# Add workspace to Python path
workspace_path = '/workspace'
if workspace_path not in sys.path:
    sys.path.insert(0, workspace_path)

# Jupyter configuration
c = get_config()

# Disable login for easier access
c.NotebookApp.password = ''
c.NotebookApp.allow_origin = '*'
c.NotebookApp.allow_root = True
c.NotebookApp.ip = '0.0.0.0'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False

# Set working directory
c.NotebookApp.notebook_dir = '/workspace'

# Auto-load the context capture extension
c.InteractiveShellApp.extensions = ['jupyter_extension']

# Custom contents manager to hide context folder and output.zip
class ContextAwareContentsManager:
    """Custom contents manager that hides context folder and output.zip"""
    
    def __init__(self, original_manager):
        self.original_manager = original_manager
    
    def list_items(self, path=''):
        """List items, hiding context folder and output.zip"""
        items = self.original_manager.list_items(path)
        
        # Filter out context folder and output.zip
        filtered_items = []
        for item in items:
            if (not item['name'].startswith('context/') and 
                not item['name'] == 'output.zip' and
                not item['name'] == 'context'):
                filtered_items.append(item)
        
        return filtered_items
    
    def __getattr__(self, name):
        """Delegate all other methods to original manager"""
        return getattr(self.original_manager, name)

# Apply custom contents manager
try:
    from notebook.services.contents.manager import ContentsManager
    c.NotebookApp.contents_manager_class = ContextAwareContentsManager
except ImportError:
    pass

# Environment variables for context capture
os.environ['PYTHONPATH'] = f"{workspace_path}:{os.environ.get('PYTHONPATH', '')}"

print(f"Jupyter configured for CodeCapsule with workspace: {workspace_path}")
print(f"Context capture extension will be auto-loaded")
print(f"Context folder and output.zip will be hidden from file browser") 