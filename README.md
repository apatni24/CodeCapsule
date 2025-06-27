# CodeCapsule – A sandboxed, GUI-driven coding agent with dynamic orchestration and intelligent context tracking.

## 🚀 Overview

CodeCapsule spawns secure, sandboxed coding environments using Docker containers with full GUI access. It provides a comprehensive development environment with shell access, file system management, GUI desktop (via noVNC), and Jupyter notebook integration. The system uses a FastAPI-based orchestrator to manage containers on-demand and includes intelligent context management to persist and recall job progress beyond LLM token limits.

**Key Capabilities:**
- Spawns isolated Docker containers with full development environment
- Provides GUI access via noVNC web interface
- Includes Jupyter notebook with enhanced capture capabilities
- Tracks all user actions, shell commands, and code execution
- Persists context across sessions for continuous development
- Auto-assigns ports for GUI and Jupyter access

## 🔧 Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   Docker         │    │   Context       │
│   Orchestrator  │───▶│   Container      │───▶│   Management    │
│   (Port 8000)   │    │   (Isolated)     │    │   System        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
   ┌─────────────┐      ┌─────────────────┐      ┌─────────────┐
   │ Job         │      │ Xvfb + Fluxbox  │      │ File-based  │
   │ Scheduling  │      │ + x11vnc +      │      │ Context     │
   │ & Status    │      │ noVNC + Jupyter │      │ Storage     │
   └─────────────┘      └─────────────────┘      └─────────────┘
```

**Core Components:**
- **FastAPI Orchestrator**: Manages job lifecycle, container spawning, and context endpoints
- **Docker Container**: Ubuntu 22.04 with X11, Jupyter, and development tools
- **GUI Stack**: Xvfb (virtual framebuffer) + Fluxbox (window manager) + x11vnc + noVNC
- **Context System**: Automatic capture of shell commands, code execution, file changes, and user prompts
- **Enhanced Jupyter**: Notebook monitoring with cell execution tracking and content capture

## 💡 Key Features

### 🧩 **Sandboxing & Security**
- Isolated containers with 1 CPU, 512MB RAM, limited disk
- No host access, resource limits enforced via Docker
- Non-root user execution for enhanced security
- Network isolation with controlled port exposure

### ⚙️ **Dynamic Orchestration**
- `/schedule` endpoint spins up containers on-demand
- `/status/{job_id}` tracks job progress and provides access URLs
- Auto-port assignment (6100-6200 for GUI, 8900-9000 for Jupyter)
- Background task management for container lifecycle

### 📝 **Intelligent Context Management**
- **Automatic Capture**: Shell commands, code execution, file changes, user prompts
- **Enhanced Jupyter**: Notebook content monitoring, cell execution tracking
- **Persistent Storage**: Context survives container restarts
- **Search & Summary**: Query context across different types with intelligent summaries
- **Download Links**: Access context and job outputs via API

### 🖥️ **Full GUI Access**
- Complete desktop environment via noVNC web interface
- Fluxbox window manager with xterm terminal
- Falkon browser pre-configured for Jupyter access
- Real-time VNC streaming with no authentication required

### 📂 **File System Integration**
- Mounted workspace volume for persistent file access
- Automatic file change monitoring and capture
- Context-aware file browser (hides system files)
- Output archiving with downloadable job results

### 🔐 **Security Features**
- Resource limits: `--cpus=1.0 --memory=512m`
- Network isolation: `--network none` (removed for VNC access)
- Non-privileged containers with user `agentuser`
- File system isolation via Docker volumes

## 📦 Installation

### Prerequisites
- Docker
- Python 3.8+
- Git

### Quick Start
```bash
# Clone the repository
git clone https://github.com/your-repo/code-capsule
cd code-capsule

# Build the Docker image
docker build -t code-capsule .

# Start the orchestrator
uvicorn orchestrator:app --host 0.0.0.0 --port 8000 --reload
```

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
  "gui_url": "http://localhost:6100",
  "jupyter_url": "http://localhost:8900",
  "context_download_link": "/downloads/3dfb85f4-295f-4697-8e4a-099d8823357f/context.zip",
  "download_link": "/downloads/3dfb85f4-295f-4697-8e4a-099d8823357f/output.zip"
}
```

### Access the Environment
- **GUI Desktop**: Open `gui_url` in your browser for full desktop access
- **Jupyter Notebook**: Open `jupyter_url` for web-based notebook interface
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

### Capture Specific Actions
```bash
# Capture shell command
curl -X POST "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f/capture/shell" \
     -H "Content-Type: application/json" \
     -d '{"command": "npm install react", "output": "added 1234 packages", "exit_code": 0}'

# Capture code execution
curl -X POST "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f/capture/code" \
     -H "Content-Type: application/json" \
     -d '{"code": "import React from react", "output": "Module imported successfully"}'

# Capture file change
curl -X POST "http://localhost:8000/context/3dfb85f4-295f-4697-8e4a-099d8823357f/capture/file" \
     -H "Content-Type: application/json" \
     -d '{"file_path": "src/App.js", "action": "edit", "content": "function App() { return <div>Hello</div>; }"}'
```

## ⚠️ Security Notes

- **Resource Limits**: Containers limited to 1 CPU and 512MB RAM
- **Network Isolation**: Containers run with controlled network access
- **File System**: All code/data restricted to mounted workspace volume
- **User Isolation**: Containers run as non-root user `agentuser`
- **No Host Access**: Containers cannot access host system resources
- **Auto-Cleanup**: Containers are automatically removed after job completion

## 📈 Scalability Notes

- **Stateless Design**: Containers are job-specific and stateless
- **Horizontal Scaling**: Multiple orchestrator instances can run simultaneously
- **Port Management**: Dynamic port assignment prevents conflicts
- **Resource Efficiency**: Containers are created on-demand and cleaned up automatically
- **Future Enhancements**: 
  - Firecracker VMs for stronger isolation
  - Kubernetes CronJob integration for auto-scaling
  - Nomad job scheduling for distributed deployment

## 📌 Known Issues & TODOs

### Current Limitations
- No GPU support for ML workloads
- No authentication layer (development mode only)
- Limited to single-user per container
- No persistent user sessions across container restarts

### Planned Features
- [ ] Multi-user support with authentication
- [ ] GPU passthrough for ML workloads
- [ ] Persistent user sessions
- [ ] Real-time collaboration features
- [ ] Advanced resource monitoring
- [ ] Integration with external IDEs

### Performance Optimizations
- [ ] Container image optimization
- [ ] Faster startup times
- [ ] Better memory management
- [ ] Caching layer for dependencies

## 🔧 Development

### Project Structure
```
CodeCapsule/
├── orchestrator.py               # FastAPI job orchestrator
├── Dockerfile                    # Container definition
├── supervisord.conf              # Service orchestration
├── jupyter_config.py             # Jupyter configuration
├── requirements.txt              # Python dependencies
├── .debug/                       # System files (hidden from agent)
│   ├── auto_capture.py           # Automatic context capture
│   ├── context_manager.py        # Context management
│   ├── jupyter_extension.py      # Jupyter extension
│   └── jupyter_notebook_capture.py # Enhanced notebook capture
└── README.md                     # This file
```

### Building and Testing
```bash
# Build the Docker image
docker build -t code-capsule .

# Test the orchestrator
curl -X POST "http://localhost:8000/schedule?task=Test%20job"

# Check container logs
docker logs <container_name>

# Access container shell
docker exec -it <container_name> /bin/bash
```

## 📬 Submission

**Email**: founders@runable.xyz  
**CC**: team@runable.xyz  
**Repository**: [GitHub Repository Link] or attached ZIP

---

**CodeCapsule** - Empowering AI agents with secure, full-featured development environments. 