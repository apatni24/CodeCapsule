import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/context_manager.log')
    ]
)
logger = logging.getLogger('context_manager')

# Try different context root paths
CONTEXT_ROOT_CANDIDATES = [
    "/tmp/jobs",
    "/home/user/context",
    "/var/tmp/jobs",
    "/tmp/context"
]

def get_writable_context_root():
    """Find a writable context root directory"""
    for candidate in CONTEXT_ROOT_CANDIDATES:
        try:
            path = Path(candidate)
            # Try to create the directory
            path.mkdir(parents=True, exist_ok=True)
            # Try to write a test file
            test_file = path / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()  # Clean up
            logger.info(f"Using context root: {candidate}")
            return candidate
        except Exception as e:
            logger.debug(f"Context root {candidate} not writable: {e}")
            continue
    
    # Fallback to current directory
    fallback = Path.cwd() / "context"
    fallback.mkdir(exist_ok=True)
    logger.warning(f"Using fallback context root: {fallback}")
    return str(fallback)

CONTEXT_ROOT = get_writable_context_root()
MAX_SIZE_BYTES = 100_000
KEEP_LINES = 1000
SUMMARY_LINES = 50

# Context types
CONTEXT_TYPES = {
    'shell': 'shell_history.txt',
    'code': 'code_execution.txt', 
    'files': 'file_changes.txt',
    'prompts': 'user_prompts.txt',
    'summary': 'context_summary.txt'
}

def get_context_path(job_id: str, context_type: str = 'general') -> Path:
    """Get path for specific context type"""
    context_dir = Path(CONTEXT_ROOT) / job_id / "context"
    logger.debug(f"Creating context directory: {context_dir}")
    
    try:
        context_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Context directory created/exists: {context_dir}")
    except Exception as e:
        logger.error(f"Failed to create context directory {context_dir}: {e}")
        raise
    
    if context_type in CONTEXT_TYPES:
        filename = CONTEXT_TYPES[context_type]
    else:
        filename = f"{context_type}.txt"
    
    file_path = context_dir / filename
    logger.debug(f"Context file path: {file_path}")
    return file_path

def append_to_context(job_id: str, entry: str, context_type: str = 'general', metadata: Dict = None):
    """Append entry to specific context type with metadata"""
    logger.debug(f"Appending to context - job_id: {job_id}, type: {context_type}")
    logger.debug(f"Entry content: {entry[:100]}...")
    
    path = get_context_path(job_id, context_type)
    
    # Create entry with timestamp and metadata
    timestamp = datetime.now().isoformat()
    entry_data = {
        'timestamp': timestamp,
        'content': entry,
        'metadata': metadata or {}
    }
    
    logger.debug(f"Writing to file: {path}")
    logger.debug(f"Entry data: {json.dumps(entry_data, indent=2)}")
    
    try:
        # Append as JSON line
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_data) + "\n")
        
        logger.info(f"Successfully wrote context entry to {path}")
        
        # Verify the write
        if path.exists():
            logger.debug(f"File exists after write, size: {path.stat().st_size} bytes")
        else:
            logger.error(f"File does not exist after write: {path}")
            
    except Exception as e:
        logger.error(f"Failed to write context entry: {e}")
        logger.error(f"Path: {path}")
        logger.error(f"Job ID: {job_id}")
        logger.error(f"Context type: {context_type}")
        raise
    
    # Prune if needed
    prune_context(job_id, context_type)

def capture_shell_command(job_id: str, command: str, output: str = "", exit_code: int = 0):
    """Capture shell command execution"""
    logger.debug(f"Capturing shell command: {command}")
    logger.debug(f"Output: {output[:100]}...")
    logger.debug(f"Exit code: {exit_code}")
    
    metadata = {
        'type': 'shell_command',
        'exit_code': exit_code,
        'command_hash': hashlib.md5(command.encode()).hexdigest()[:8]
    }
    
    entry = f"COMMAND: {command}\nOUTPUT: {output}\nEXIT_CODE: {exit_code}"
    append_to_context(job_id, entry, 'shell', metadata)

def capture_code_execution(job_id: str, code: str, output: str = "", error: str = ""):
    """Capture code execution (Python, etc.)"""
    logger.debug(f"Capturing code execution: {code[:100]}...")
    logger.debug(f"Output: {output[:100]}...")
    if error:
        logger.debug(f"Error: {error}")
    
    metadata = {
        'type': 'code_execution',
        'language': 'python',  # Can be extended
        'code_hash': hashlib.md5(code.encode()).hexdigest()[:8]
    }
    
    entry = f"CODE:\n{code}\nOUTPUT:\n{output}"
    if error:
        entry += f"\nERROR:\n{error}"
    
    append_to_context(job_id, entry, 'code', metadata)

def capture_file_change(job_id: str, file_path: str, action: str, content: str = "", old_content: str = ""):
    """Capture file changes (create, edit, delete)"""
    logger.debug(f"Capturing file change: {action} {file_path}")
    logger.debug(f"Content length: {len(content)}")
    
    metadata = {
        'type': 'file_change',
        'action': action,  # 'create', 'edit', 'delete'
        'file_path': file_path,
        'file_hash': hashlib.md5(content.encode()).hexdigest()[:8] if content else None
    }
    
    entry = f"FILE: {file_path}\nACTION: {action}\nCONTENT:\n{content}"
    if old_content and action == 'edit':
        entry += f"\nOLD_CONTENT:\n{old_content}"
    
    append_to_context(job_id, entry, 'files', metadata)

def capture_user_prompt(job_id: str, prompt: str, response: str = ""):
    """Capture user prompts and responses"""
    logger.debug(f"Capturing user prompt: {prompt[:100]}...")
    if response:
        logger.debug(f"Response: {response[:100]}...")
    
    metadata = {
        'type': 'user_prompt',
        'prompt_hash': hashlib.md5(prompt.encode()).hexdigest()[:8]
    }
    
    entry = f"PROMPT: {prompt}"
    if response:
        entry += f"\nRESPONSE: {response}"
    
    append_to_context(job_id, entry, 'prompts', metadata)

def prune_context(job_id: str, context_type: str = 'general', max_size_bytes: int = MAX_SIZE_BYTES):
    """Intelligently prune context, keeping latest entries and generating summary"""
    logger.debug(f"Checking if pruning needed for {context_type}")
    path = get_context_path(job_id, context_type)
    if not path.exists():
        logger.debug(f"Context file does not exist: {path}")
        return
    
    file_size = path.stat().st_size
    logger.debug(f"Context file size: {file_size} bytes (max: {max_size_bytes})")
    
    if file_size <= max_size_bytes:
        logger.debug("No pruning needed")
        return
    
    logger.info(f"Pruning context file: {path}")
    
    # Read all entries
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    
    logger.debug(f"Total entries: {len(entries)}")
    
    if len(entries) <= KEEP_LINES:
        logger.debug("Not enough entries to prune")
        return
    
    # Keep latest entries
    kept_entries = entries[-KEEP_LINES:]
    logger.debug(f"Keeping {len(kept_entries)} entries")
    
    # Generate summary from pruned entries
    pruned_entries = entries[:-KEEP_LINES]
    summary = generate_context_summary(pruned_entries, context_type)
    
    # Write back kept entries
    with open(path, "w", encoding="utf-8") as f:
        for entry in kept_entries:
            f.write(json.dumps(entry) + "\n")
    
    logger.info(f"Pruned {len(pruned_entries)} entries from {context_type}")
    
    # Append summary to summary file
    if summary:
        append_to_context(job_id, summary, 'summary', {
            'type': 'context_summary',
            'context_type': context_type,
            'pruned_count': len(pruned_entries)
        })

def generate_context_summary(entries: List[Dict], context_type: str) -> str:
    """Generate intelligent summary of pruned entries"""
    if not entries:
        return ""
    
    timestamp = datetime.now().isoformat()
    
    if context_type == 'shell':
        commands = [e['content'].split('\n')[0].replace('COMMAND: ', '') for e in entries]
        unique_commands = list(set(commands))
        return f"[{timestamp}] SHELL SUMMARY: {len(entries)} commands executed, {len(unique_commands)} unique commands"
    
    elif context_type == 'code':
        return f"[{timestamp}] CODE SUMMARY: {len(entries)} code executions, {sum(1 for e in entries if 'ERROR' in e['content'])} errors"
    
    elif context_type == 'files':
        actions = [e['metadata'].get('action', 'unknown') for e in entries]
        action_counts = {action: actions.count(action) for action in set(actions)}
        return f"[{timestamp}] FILE SUMMARY: {len(entries)} file changes - {action_counts}"
    
    elif context_type == 'prompts':
        return f"[{timestamp}] PROMPT SUMMARY: {len(entries)} user interactions"
    
    else:
        return f"[{timestamp}] GENERAL SUMMARY: {len(entries)} entries pruned"

def read_context(job_id: str, context_type: str = 'general', limit: int = None) -> str:
    """Read context with optional limit"""
    logger.debug(f"Reading context - job_id: {job_id}, type: {context_type}, limit: {limit}")
    path = get_context_path(job_id, context_type)
    if not path.exists():
        logger.debug(f"Context file does not exist: {path}")
        return ""
    
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    
    logger.debug(f"Read {len(entries)} entries from {path}")
    
    if limit:
        entries = entries[-limit:]
        logger.debug(f"Limited to {len(entries)} entries")
    
    # Format entries for reading
    formatted = []
    for entry in entries:
        timestamp = entry['timestamp']
        content = entry['content']
        formatted.append(f"[{timestamp}]\n{content}\n")
    
    return "\n".join(formatted)

def get_context_summary(job_id: str) -> Dict:
    """Get comprehensive context summary for a job"""
    logger.debug(f"Getting context summary for job: {job_id}")
    summary = {
        'job_id': job_id,
        'context_types': {},
        'total_entries': 0,
        'last_activity': None
    }
    
    for context_type in CONTEXT_TYPES.keys():
        path = get_context_path(job_id, context_type)
        if path.exists():
            entries = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            if entries:
                summary['context_types'][context_type] = {
                    'entry_count': len(entries),
                    'last_entry': entries[-1]['timestamp'],
                    'size_bytes': path.stat().st_size
                }
                summary['total_entries'] += len(entries)
                
                if not summary['last_activity'] or entries[-1]['timestamp'] > summary['last_activity']:
                    summary['last_activity'] = entries[-1]['timestamp']
    
    logger.debug(f"Context summary: {summary}")
    return summary

def search_context(job_id: str, query: str, context_types: List[str] = None) -> List[Dict]:
    """Search across context types for specific content"""
    logger.debug(f"Searching context - job_id: {job_id}, query: {query}")
    if context_types is None:
        context_types = list(CONTEXT_TYPES.keys())
    
    results = []
    query_lower = query.lower()
    
    for context_type in context_types:
        path = get_context_path(job_id, context_type)
        if not path.exists():
            continue
        
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if query_lower in entry['content'].lower():
                        results.append({
                            'context_type': context_type,
                            'timestamp': entry['timestamp'],
                            'content': entry['content'],
                            'metadata': entry['metadata']
                        })
                except json.JSONDecodeError:
                    continue
    
    logger.debug(f"Search found {len(results)} results")
    return results 