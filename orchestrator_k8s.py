from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
import uuid
import os
import shutil
import yaml
import tempfile
import time
from kubernetes import client, config
from kubernetes.client import V1Job, V1Service, V1PersistentVolumeClaim
from context_manager import (
    append_to_context, read_context, get_context_summary, search_context,
    capture_shell_command, capture_code_execution, capture_file_change, capture_user_prompt
)

app = FastAPI()
JOBS = {}
AGENT_IMAGE = "codecapsuleacr.azurecr.io/code-capsule-agent:latest"
print(f"🔧 Using AGENT_IMAGE: {AGENT_IMAGE}")

JOBS_ROOT = "/tmp/jobs"

# Port ranges for dynamic assignment
NOVNC_PORT_RANGE = range(30080, 30100)  # NodePort range
JUPYTER_PORT_RANGE = range(30100, 30120)  # NodePort range

# Mount /tmp/jobs as /downloads for static file serving
app.mount("/downloads", StaticFiles(directory=JOBS_ROOT), name="downloads")

# Initialize Kubernetes client
try:
    config.load_kube_config()
    print("✅ Loaded Kubernetes config")
except Exception as e:
    print(f"⚠️ Could not load kubeconfig: {e}")
    # Try in-cluster config
    try:
        config.load_incluster_config()
        print("✅ Loaded in-cluster Kubernetes config")
    except Exception as e:
        print(f"❌ Could not load Kubernetes config: {e}")

NODE_EXTERNAL_IP = os.environ.get("NODE_EXTERNAL_IP", "20.244.44.105")  # Replace with your node's IP or set as env

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

def create_k8s_job(job_id: str, task: str) -> V1Job:
    """Create a Kubernetes Job object"""
    return V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=f"code-agent-job-{job_id}",
            labels={
                "app": "code-capsule",
                "job-type": "agent",
                "job-id": job_id
            }
        ),
        spec=client.V1JobSpec(
            backoff_limit=0,
            ttl_seconds_after_finished=60,  # Clean up after 1 minute
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": "code-capsule",
                        "job-type": "agent",
                        "job-id": job_id
                    }
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="code-agent",
                            image=AGENT_IMAGE,
                            image_pull_policy="Always",
                            ports=[
                                client.V1ContainerPort(container_port=6080, name="novnc"),
                                client.V1ContainerPort(container_port=8888, name="jupyter")
                            ],
                            env=[
                                client.V1EnvVar(name="JOB_ID", value=job_id),
                                client.V1EnvVar(name="WORKSPACE", value="/workspace")
                            ],
                            resources=client.V1ResourceRequirements(
                                limits={"cpu": "400m", "memory": "1.5Gi"},
                                requests={"cpu": "200m", "memory": "1Gi"}
                            ),
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="job-storage", 
                                    mount_path="/workspace"
                                ),
                                client.V1VolumeMount(
                                    name="context-storage", 
                                    mount_path="/tmp/jobs"
                                )
                            ],
                            security_context=client.V1SecurityContext(
                                run_as_user=1000,
                                run_as_group=1000
                            )
                        )
                    ],
                    restart_policy="Never",
                    security_context=client.V1PodSecurityContext(
                        fs_group=1000
                    ),
                    volumes=[
                        client.V1Volume(
                            name="job-storage",
                            empty_dir=client.V1EmptyDirVolumeSource()
                        ),
                        client.V1Volume(
                            name="context-storage",
                            empty_dir=client.V1EmptyDirVolumeSource()
                        )
                    ]
                )
            )
        )
    )

def create_k8s_service(job_id: str, novnc_port: int, jupyter_port: int) -> V1Service:
    """Create a Kubernetes Service object"""
    return V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=f"code-agent-svc-{job_id}",
            labels={
                "app": "code-capsule",
                "job-id": job_id
            }
        ),
        spec=client.V1ServiceSpec(
            selector={
                "job-name": f"code-agent-job-{job_id}"
            },
            ports=[
                client.V1ServicePort(
                    name="novnc",
                    port=6080,
                    target_port=6080,
                    node_port=novnc_port
                ),
                client.V1ServicePort(
                    name="jupyter",
                    port=8888,
                    target_port=8888,
                    node_port=jupyter_port
                )
            ],
            type="NodePort"
        )
    )

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
        "gui_url": f"http://{NODE_EXTERNAL_IP}:{novnc_port}",
        "jupyter_url": f"http://{NODE_EXTERNAL_IP}:{jupyter_port}"
    }
    
    # Initialize context with the task
    capture_user_prompt(job_id, f"Task started: {task}")
    background_tasks.add_task(run_k8s_job, job_id, task, novnc_port, jupyter_port)
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

# Context Management Endpoints (same as original)
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

def run_k8s_job(job_id: str, task: str, novnc_port: int, jupyter_port: int):
    """Run a Kubernetes job instead of Docker container"""
    JOBS[job_id]["status"] = "running"
    job_dir = os.path.join(JOBS_ROOT, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    try:
        # Create Kubernetes API clients
        batch_v1 = client.BatchV1Api()
        core_v1 = client.CoreV1Api()
        
        # Create the job
        job = create_k8s_job(job_id, task)
        batch_v1.create_namespaced_job(namespace="code-capsule", body=job)
        print(f"✅ Created Kubernetes job: code-agent-job-{job_id}")
        
        # Create the service
        service = create_k8s_service(job_id, novnc_port, jupyter_port)
        core_v1.create_namespaced_service(namespace="code-capsule", body=service)
        print(f"✅ Created Kubernetes service: code-agent-svc-{job_id}")
        
        # Wait for job to complete with timeout
        max_wait_time = 600  # 10 minutes timeout
        start_time = time.time()
        while True:
            job_status = batch_v1.read_namespaced_job_status(
                name=f"code-agent-job-{job_id}", 
                namespace="code-capsule"
            )
            
            if job_status.status.succeeded:
                print(f"✅ Job {job_id} completed successfully")
                break
            elif job_status.status.failed:
                print(f"❌ Job {job_id} failed")
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = "Job failed in Kubernetes"
                return
            
            current_time = time.time()
            if current_time - start_time > max_wait_time:
                print(f"❌ Job {job_id} timed out after {max_wait_time} seconds")
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = "Job timed out in Kubernetes"
                # Create output zip for timed out job
                output_zip = os.path.join(job_dir, "output.zip")
                shutil.make_archive(os.path.splitext(output_zip)[0], 'zip', job_dir)
                JOBS[job_id]["download_link"] = f"/downloads/{job_id}/output.zip"
                
                # Clean up service for timed out job
                try:
                    core_v1.delete_namespaced_service(
                        name=f"code-agent-svc-{job_id}", 
                        namespace="code-capsule"
                    )
                    print(f"✅ Cleaned up service: code-agent-svc-{job_id}")
                except Exception as e:
                    print(f"⚠️ Could not clean up service: {e}")
                
                # Terminate the job to trigger TTL cleanup
                try:
                    batch_v1.delete_namespaced_job(
                        name=f"code-agent-job-{job_id}", 
                        namespace="code-capsule"
                    )
                    print(f"✅ Terminated job: code-agent-job-{job_id}")
                except Exception as e:
                    print(f"⚠️ Could not terminate job: {e}")
                
                return
            
            time.sleep(5)
        
        # After job completes, zip the job output
        output_zip = os.path.join(job_dir, "output.zip")
        shutil.make_archive(os.path.splitext(output_zip)[0], 'zip', job_dir)
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["download_link"] = f"/downloads/{job_id}/output.zip"
        
        # Clean up Kubernetes resources
        try:
            core_v1.delete_namespaced_service(
                name=f"code-agent-svc-{job_id}", 
                namespace="code-capsule"
            )
            print(f"✅ Cleaned up service: code-agent-svc-{job_id}")
        except Exception as e:
            print(f"⚠️ Could not clean up service: {e}")
            
    except Exception as e:
        print(f"❌ Error running Kubernetes job {job_id}: {e}")
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)

if __name__ == "__main__":
    import uvicorn
    print(f"🔧 Using AGENT_IMAGE: {AGENT_IMAGE}")
    uvicorn.run(app, host="0.0.0.0", port=8000) 