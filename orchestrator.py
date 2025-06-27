from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
import uuid
import subprocess
import os
import shutil
from context_manager import (
    append_to_context, read_context, get_context_summary, search_context,
    capture_shell_command, capture_code_execution, capture_file_change, capture_user_prompt
)

app = FastAPI()
JOBS = {}
AGENT_IMAGE = "code-capsule"
JOBS_ROOT = "/tmp/jobs"

# Port ranges for dynamic assignment
NOVNC_PORT_RANGE = range(6100, 6200)
JUPYTER_PORT_RANGE = range(8900, 9000)

# Mount /tmp/jobs as /downloads for static file serving
app.mount("/downloads", StaticFiles(directory=JOBS_ROOT), name="downloads")

def find_available_port(port_range):
    used_ports = set()
    for job in JOBS.values():
        if "novnc_port" in job:
            used_ports.add(job["novnc_port"])
        if "jupyter_port" in job:
            used_ports.add(job["jupyter_port"])
    for port in port_range:
        if port not in used_ports:
            return port
    raise RuntimeError("No available ports in range")

@app.post("/schedule")
def schedule_job(task: str, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    novnc_port = find_available_port(NOVNC_PORT_RANGE)
    jupyter_port = find_available_port(JUPYTER_PORT_RANGE)
    JOBS[job_id] = {
        "status": "scheduled",
        "task": task,
        "novnc_port": novnc_port,
        "jupyter_port": jupyter_port,
        "gui_url": f"http://localhost:{novnc_port}",
        "jupyter_url": f"http://localhost:{jupyter_port}"
    }
    # Initialize context with the task
    capture_user_prompt(job_id, f"Task started: {task}")
    background_tasks.add_task(run_container, job_id, task, novnc_port, jupyter_port)
    return {"job_id": job_id}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"error": "Job not found"}
    
    # Create context download link if context directory exists
    context_download_link = None
    context_dir = os.path.join(JOBS_ROOT, job_id, "context")
    if os.path.exists(context_dir):
        context_zip_path = os.path.join(JOBS_ROOT, job_id, "context.zip")
        try:
            # Create context zip if it doesn't exist
            if not os.path.exists(context_zip_path):
                shutil.make_archive(os.path.splitext(context_zip_path)[0], 'zip', context_dir)
            context_download_link = f"/downloads/{job_id}/context.zip"
        except Exception as e:
            print(f"Warning: Could not create context zip for job {job_id}: {e}")
    
    # Always include GUI/Jupyter URLs if available
    resp = {k: job[k] for k in job if k in ["status", "task", "gui_url", "jupyter_url", "download_link", "error"]}
    
    # Add context download link if available
    if context_download_link:
        resp["context_download_link"] = context_download_link
    
    return resp

# Context Management Endpoints
@app.post("/context/{job_id}/append")
def append_context(job_id: str, entry: str, context_type: str = "general"):
    """Add an entry to the job's context"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    append_to_context(job_id, entry, context_type)
    return {"status": "Context updated", "job_id": job_id, "context_type": context_type}

@app.get("/context/{job_id}")
def get_context(job_id: str, context_type: str = "general", limit: int = None):
    """Get the current context for a job"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    context = read_context(job_id, context_type, limit)
    return {"job_id": job_id, "context_type": context_type, "context": context}

@app.get("/context/{job_id}/summary")
def get_context_summary_endpoint(job_id: str):
    """Get comprehensive context summary for a job"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    summary = get_context_summary(job_id)
    return summary

@app.post("/context/{job_id}/capture/shell")
def capture_shell(job_id: str, command: str, output: str = "", exit_code: int = 0):
    """Capture shell command execution"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    capture_shell_command(job_id, command, output, exit_code)
    return {"status": "Shell command captured", "job_id": job_id}

@app.post("/context/{job_id}/capture/code")
def capture_code(job_id: str, code: str, output: str = "", error: str = ""):
    """Capture code execution"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    capture_code_execution(job_id, code, output, error)
    return {"status": "Code execution captured", "job_id": job_id}

@app.post("/context/{job_id}/capture/file")
def capture_file(job_id: str, file_path: str, action: str, content: str = "", old_content: str = ""):
    """Capture file changes"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    capture_file_change(job_id, file_path, action, content, old_content)
    return {"status": "File change captured", "job_id": job_id}

@app.post("/context/{job_id}/capture/prompt")
def capture_prompt(job_id: str, prompt: str, response: str = ""):
    """Capture user prompts"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    capture_user_prompt(job_id, prompt, response)
    return {"status": "Prompt captured", "job_id": job_id}

@app.get("/context/{job_id}/search")
def search_context_endpoint(job_id: str, query: str, context_types: str = None):
    """Search across context types"""
    if job_id not in JOBS:
        return {"error": "Job not found"}
    
    types_list = None
    if context_types:
        types_list = [t.strip() for t in context_types.split(",")]
    
    results = search_context(job_id, query, types_list)
    return {"job_id": job_id, "query": query, "results": results}

def run_container(job_id, task, novnc_port, jupyter_port):
    JOBS[job_id]["status"] = "running"
    job_dir = os.path.join(JOBS_ROOT, job_id)
    os.makedirs(job_dir, exist_ok=True)
    container_name = f"agent-{job_id}"
    try:
        result = subprocess.run([
            "docker", "run", "-d",
            "--name", container_name,
            "-v", f"{job_dir}:/workspace",
            "--user", "agentuser",
            "--cpus=1.0",
            "--memory=512m",
            "-p", f"{novnc_port}:6080",
            "-p", f"{jupyter_port}:8888",
            "-e", f"JOB_ID={job_id}",
            "-e", f"WORKSPACE=/workspace",
            AGENT_IMAGE
        ], capture_output=True)
        JOBS[job_id]["container_id"] = result.stdout.decode().strip()
        
        # Wait for container to finish
        subprocess.run(["docker", "wait", container_name], capture_output=True)
        
        # Copy context files from container to workspace before container is removed
        try:
            subprocess.run([
                "docker", "cp", 
                f"{container_name}:/tmp/jobs/{job_id}/context/.", 
                f"{job_dir}/context/"
            ], capture_output=True)
            print(f"Context files copied for job {job_id}")
        except Exception as e:
            print(f"Warning: Could not copy context files for job {job_id}: {e}")
        
        # After container finishes, zip the job output
        output_zip = os.path.join(job_dir, "output.zip")
        shutil.make_archive(os.path.splitext(output_zip)[0], 'zip', job_dir)
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["download_link"] = f"/downloads/{job_id}/output.zip"
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e) 