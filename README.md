# CodeCapsule – Secure, GUI-Driven Coding Agents on Kubernetes

## 🌐 Current Public Orchestrator URL
- **Orchestrator API:** http://codecapsule-orchestrator.centralindia.cloudapp.azure.com:8000/

## ⚠️ Current Limitations
- **Maximum concurrent agent pods/services:**
  - The system uses NodePort ranges 30080-30120 for exposing agent GUIs and Jupyter services.
  - This allows for up to 20 concurrent agent jobs (each job uses two NodePorts: one for noVNC, one for Jupyter).
  - If all NodePorts are in use, new jobs will not be scheduled until ports are freed by completed/cleaned-up jobs.
- **Manual NSG configuration required:**
  - On AKS, ensure your Azure Network Security Group (NSG) allows external access to NodePort range 30080-30120.

## 🚀 Overview

**CodeCapsule** is a platform for spawning secure, sandboxed coding environments with full desktop GUI and Jupyter access, orchestrated dynamically on Kubernetes. Each user task runs in its own isolated pod, with persistent context, file management, and intelligent capture of all user actions. CodeCapsule is ideal for:
- AI coding agents
- Secure browser-based coding sandboxes
- Education, workshops, and cloud IDEs
- Automated code evaluation and grading

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

**Components:**
- **Orchestrator Pod (FastAPI):** Receives API requests, schedules agent pods, tracks jobs, exposes `/schedule` and `/status` endpoints.
- **Agent Pods:** Each user/job gets a dedicated pod with Ubuntu, GUI (noVNC), Jupyter, and context capture.
- **Services:** LoadBalancer exposes orchestrator; NodePort services expose agent GUIs/Jupyter.

## ✨ Features
- **Isolated, on-demand agent pods** (GUI, Jupyter, shell)
- **FastAPI orchestrator** with REST API
- **Persistent, intelligent context capture** (shell, code, files, prompts)
- **Full desktop via noVNC**, Jupyter notebook integration
- **Secure:** resource limits, non-root, network isolation, RBAC
- **Scalable:** Kubernetes-native, supports autoscaling (HPA/KEDA)
- **Easy monitoring and cleanup** with kubectl
- **Automatic timeout & cleanup:** Jobs are automatically terminated and cleaned up after 10 minutes if not completed.
- **Status API returns external URLs:** `/status` endpoint returns URLs with the node's external IP for direct access.

---

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/apatni24/CodeCapsule.git
   cd CodeCapsule
   ```
2. **Make the deploy script executable**
   ```bash
   chmod +x k8s/deploy.sh
   ```
3. **Deploy to Kubernetes**
   ```bash
   ./k8s/deploy.sh
   ```
   This will print the orchestrator URL (e.g. `http://localhost:8000` or a cloud IP).

4. **Schedule a new agent pod**
   ```bash
   curl -X POST "http://<orchestrator-url>/schedule?task=Try%20Python%20GUI"
   ```
   **Note:** The `task` parameter must be provided as a query parameter, not in the JSON body.
   **Sample response:**
   ```json
   { "job_id": "3dfb85f4-295f-4697-8e4a-099d8823357f" }
   ```

5. **Check agent pod status**
   ```bash
   curl "http://<orchestrator-url>/status/3dfb85f4-295f-4697-8e4a-099d8823357f"
   ```
   **Sample response:**
   ```json
   {
     "status": "running",
     "task": "Try Python GUI",
     "gui_url": "http://<external-ip>:30080",
     "jupyter_url": "http://<external-ip>:30100",
     ...
   }
   ```
   When `status` is `running`, the agent pod is ready.

6. **Access the agent pod GUI/Jupyter**
   - **If using a cloud cluster (AKS, GKE, EKS):**
     - Open the `gui_url` and `jupyter_url` directly in your browser (these use the node's external IP and NodePort).
     - **AKS users:** Ensure your Azure Network Security Group (NSG) allows NodePort ranges 30080-30120 for both TCP and UDP.
   - **If using port-forwarding:**
     ```bash
     kubectl port-forward service/code-agent-svc-3dfb85f4-295f-4697-8e4a-099d8823357f 6080:6080 8888:8888 -n code-capsule
     ```
     Then open `http://localhost:6080` or `http://localhost:8888`.

---

## ⏰ Automatic Timeout & Cleanup
- **Job timeout:** Each agent job has a 10-minute maximum runtime. If the job does not complete in this time, it is marked as errored, the service is deleted, and the job is terminated in Kubernetes.
- **Automatic resource cleanup:** The orchestrator deletes the service and job for completed or timed-out jobs. Orphaned pods may remain briefly (due to Kubernetes finalizers) but are safe to delete or will be garbage collected automatically.
- **No manual cleanup required** for most use cases. You can still use kubectl to force-delete any lingering pods if needed.

## 🛠️ Monitoring & Cleanup
- **Monitor jobs/pods:**
  ```bash
  kubectl get jobs -n code-capsule
  kubectl get pods -n code-capsule
  kubectl logs job/code-agent-job-<job_id> -n code-capsule
  ```
- **Manual cleanup (if needed):**
  ```bash
  kubectl delete job code-agent-job-<job_id> -n code-capsule
  kubectl delete service code-agent-svc-<job_id> -n code-capsule
  kubectl delete pod <pod_name> -n code-capsule  # For orphaned pods
  kubectl delete namespace code-capsule
  ```

## 🔒 Security & Scaling
- **Resource limits:** 1 CPU, 1Gi RAM per agent pod (configurable)
- **RBAC:** Role-based access control for orchestrator and jobs
- **Network policies:** Recommended for pod isolation
- **Autoscaling:** Use Kubernetes HPA or KEDA for orchestrator and agent jobs

## ⚙️ Configuration
- **Environment variables:** `JOB_ID`, `WORKSPACE`, `PYTHONPATH`
- **Port ranges:** noVNC (30080-30100), Jupyter (30100-30120), Orchestrator (8000)
- **Persistent storage:** Use PVCs for agent pods if needed
- **NodePort/NSG:** If using AKS, ensure your NSG allows NodePort ranges 30080-30120 for external access to agent GUIs and Jupyter.

---

For more, see the [GitHub repository](https://github.com/apatni24/CodeCapsule.git).