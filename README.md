# CodeCapsule – A sandboxed, GUI-driven coding agent with dynamic orchestration and intelligent context tracking.

## 🚀 Overview

CodeCapsule spawns secure, sandboxed coding environments using Kubernetes jobs and pods, each with full GUI access. Each agent pod is created on-demand per user task, ensuring strong isolation and scalability. The system provides a comprehensive development environment with shell access, file system management, GUI desktop (via noVNC), and Jupyter notebook integration. The FastAPI-based orchestrator (itself a Kubernetes pod) manages agent pods and includes intelligent context management to persist and recall job progress beyond LLM token limits.

**Key Capabilities:**
- Spawns isolated Kubernetes pods with full development environment
- Provides GUI access via noVNC web interface
- Includes Jupyter notebook with enhanced capture capabilities
- Tracks all user actions, shell commands, and code execution
- Persists context across sessions for continuous development
- Auto-assigns ports for GUI and Jupyter access

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                       │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   Orchestrator  │    │        Agent Jobs               │ │
│  │   Deployment    │    │                                 │ │
│  │   (FastAPI)     │───▶│  ┌─────────┐  ┌─────────┐       │ │
│  │   Port: 8000    │    │  │ Job 1   │  │ Job 2   │       │ │
│  └─────────────────┘    │  │ Pod     │  │ Pod     │       │ │
│                         │  └─────────┘  └─────────┘       │ │
│  ┌─────────────────┐    │                                 │ │
│  │   LoadBalancer  │    │  ┌─────────┐  ┌─────────┐       │ │
│  │   Service       │    │  │ Svc 1   │  │ Svc 2   │       │ │
│  └─────────────────┘    │  │ NodePort│  │ NodePort│       │ │
│                         │  └─────────┘  └─────────┘       │ │
│                         └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Core Components:**
- **Orchestrator Pod (FastAPI)**: Runs as a Kubernetes pod, manages job lifecycle, schedules agent pods on-demand per job/task, and exposes API endpoints
- **Agent Pods**: Ubuntu 22.04 with X11, Jupyter, and development tools, each running as a separate Kubernetes pod created per user job/task
- **GUI Stack**: Xvfb (virtual framebuffer) + Fluxbox (window manager) + x11vnc + noVNC
- **Context System**: Automatic capture of shell commands, code execution, file changes, and user prompts
- **Enhanced Jupyter**: Notebook monitoring with cell execution tracking and content capture

## 💡 Key Features

### 🧩 **Sandboxing & Security**
- Isolated agent pods with 1 CPU, 1Gi RAM, limited disk
- No host access, resource limits enforced via Kubernetes
- Non-root user execution for enhanced security
- Network isolation with controlled port exposure

### ⚙️ **Dynamic Orchestration**
- `/schedule` endpoint spins up agent pods on-demand
- `/status/{job_id}` tracks job progress and provides access URLs
- Auto-port assignment (NodePort ranges for GUI/Jupyter)
- Background task management for pod lifecycle

### 📝 **Intelligent Context Management**
- **Automatic Capture**: Shell commands, code execution, file changes, user prompts
- **Enhanced Jupyter**: Notebook content monitoring, cell execution tracking
- **Persistent Storage**: Context survives pod restarts (if using PVCs)
- **Search & Summary**: Query context across different types with intelligent summaries
- **Download Links**: Access context and job outputs via API

### 🖥️ **Full GUI Access**
- Complete desktop environment via noVNC web interface
- Fluxbox window manager with xterm terminal
- Falkon browser pre-configured for Jupyter access
- Real-time VNC streaming with no authentication required

### 📂 **File System Integration**
- Mounted workspace volume for persistent file access (via Kubernetes volumes)
- Automatic file change monitoring and capture
- Context-aware file browser (hides system files)
- Output archiving with downloadable job results

### 🔐 **Security Features**
- Resource limits: 1 CPU, 1Gi RAM per agent pod
- Network isolation: Kubernetes network policies (recommended)
- Non-privileged containers with user `agentuser`
- File system isolation via Kubernetes volumes

## 📦 Kubernetes Deployment & Operations

### Prerequisites
- **Kubernetes Cluster**: Minikube, Docker Desktop, or cloud cluster
- **kubectl**: Configured to access your cluster
- **Docker**: For building the agent image
- **Python 3.8+**
- **Git**

### Quick Start (Automated)
```bash
# Clone the repository
git clone https://github.com/your-repo/code-capsule
cd code-capsule

# Build the agent image
docker build -t code-capsule-agent .

# Deploy to Kubernetes
chmod +x k8s/deploy.sh
./k8s/deploy.sh
```

### Quick Start (Manual)
```bash
# Create namespace
kubectl create namespace code-capsule

# Deploy orchestrator
kubectl apply -f k8s/orchestrator-deployment.yaml

# Check status
kubectl get pods -n code-capsule
kubectl get services -n code-capsule
```

### Access Patterns
#### Local Development (Minikube/Docker Desktop)
```bash
# Port forward to access orchestrator
kubectl port-forward service/code-capsule-orchestrator 8000:8000 -n code-capsule

# Access orchestrator
curl http://localhost:8000/status/<job-id>
```
#### Cloud Deployment
```bash
# Get external IP
kubectl get service code-capsule-orchestrator -n code-capsule

# Access via external IP
curl http://<external-ip>:8000/schedule?task=Test
```
#### Agent Pod Access
```bash
# Port forward to access a specific agent pod's GUI/Jupyter
kubectl port-forward service/code-agent-svc-<job-id> 6080:6080 8888:8888 -n code-capsule
```

### Monitoring
```bash
# List all jobs
kubectl get jobs -n code-capsule

# Get job details
kubectl describe job code-agent-job-<job-id> -n code-capsule

# Get pod logs
kubectl logs job/code-agent-job-<job-id> -n code-capsule

# List services
kubectl get services -n code-capsule

# Get service details
kubectl describe service code-agent-svc-<job-id> -n code-capsule
```

### Cleanup
```bash
# Clean up specific job
kubectl delete job code-agent-job-<job-id> -n code-capsule
kubectl delete service code-agent-svc-<job-id> -n code-capsule

# Clean up everything
kubectl delete namespace code-capsule
```

### Security Considerations
1. **Image Security**: Use private registries for production
2. **Network Policies**: Implement network policies for pod isolation
3. **RBAC**: Configure appropriate service accounts and permissions
4. **Resource Limits**: Jobs have CPU/memory limits enforced
5. **TTL**: Jobs auto-cleanup after 10 minutes

### Scaling
#### Horizontal Pod Autoscaler (HPA)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: code-capsule-orchestrator-hpa
  namespace: code-capsule
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: code-capsule-orchestrator
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```
#### KEDA (Event-Driven Autoscaling)
For advanced scaling based on queue depth or custom metrics.

### Troubleshooting
#### Common Issues
1. **Image Pull Errors**:
   ```bash
   # Check if image exists locally
   docker images | grep code-capsule-agent
   # Use imagePullPolicy: Never for local images
   ```
2. **Port Conflicts**:
   ```bash
   # Check used NodePorts
   kubectl get services -n code-capsule -o jsonpath='{range .items[*]}{.spec.ports[*].nodePort}{"\n"}{end}'
   ```
3. **Resource Limits**:
   ```bash
   # Check pod events
   kubectl describe pod <pod-name> -n code-capsule
   ```
4. **Context Storage Issues**:
   ```bash
   # Check volume mounts
   kubectl exec -it <pod-name> -n code-capsule -- ls -la /tmp/jobs
   ```

### Migration from Docker
1. **Update orchestrator**: Use `orchestrator_k8s.py` instead of `orchestrator.py`
2. **Install dependencies**: Add `kubernetes` to requirements.txt
3. **Update image**: Ensure image is available in cluster
4. **Deploy**: Use Kubernetes manifests instead of Docker commands

### Configuration
#### Environment Variables
- `JOB_ID`: Set by orchestrator for each job
- `WORKSPACE`: Set to `/workspace` in containers
- `PYTHONPATH`: Set to `/workspace/.debug` for orchestrator

#### Resource Limits
- **Orchestrator**: 500m CPU, 512Mi memory
- **Agent Jobs**: 1 CPU, 1Gi memory
- **Storage**: 10Gi per PVC (if using persistent storage)

#### Port Ranges
- **noVNC**: 30080-30100 (NodePort)
- **Jupyter**: 30100-30120 (NodePort)
- **Orchestrator**: 8000 (LoadBalancer)

## 📦 Installation

### Environment Setup
```bash
# Create virtual environment (optional)
python -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🧪 Usage

### Schedule a Job
```bash
curl -X POST "http://localhost:8000/schedule?task=Build%20a%20React%20todo%20app"
```

**Response:**
```json
{
  "job_id": "3dfb85f4-295f-4697-8e4a-099d8823357f"
}
```

### Check Job Status
```bash
curl "http://localhost:8000/status/3dfb85f4-295f-4697-8e4a-099d8823357f"
```

**Response:**
```json
{
  "status": "running",
  "task": "Build a React todo app",
  "gui_url": "http://localhost:6100",  # (If port-forwarded)
  "jupyter_url": "http://localhost:8900",  # (If port-forwarded)
  "context_download_link": "/downloads/3dfb85f4-295f-4697-8e4a-099d8823357f/context.zip",
  "download_link": "/downloads/3dfb85f4-295f-4697-8e4a-099d8823357f/output.zip"
}
```

### Access the Environment
- **Orchestrator API**: Accessible at `http://localhost:8000` (after port-forwarding)
- **GUI Desktop**: Open `gui_url` in your browser for full desktop access (after port-forwarding the agent service)
- **Jupyter Notebook**: Open `jupyter_url` for web-based notebook interface (after port-forwarding the agent service)
- **Download Results**: Use `download_link` to get job output archive
- **Download Context**: Use `context_download_link` to get captured context

## 📁 Context API

### Get Context for a Job
```bash
# Get shell command history
curl "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f?context_type=shell&limit=10"

# Get code execution history
curl "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f?context_type=code&limit=5"

# Get file changes
curl "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f?context_type=files&limit=10"
```

### Append to Context
```bash
curl -X POST "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f/append" \
     -H "Content-Type: application/json" \
     -d '{"entry": "Manual note about the implementation", "context_type": "general"}'
```

### Get Context Summary
```bash
curl "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f/summary"
```

### Search Context
```bash
curl "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f/search?query=react&context_types=shell,code,notebook"
```