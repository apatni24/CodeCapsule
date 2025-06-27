FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Kolkata

# Basic setup
RUN apt-get update && apt-get install -y \
    tzdata gnupg lsb-release\
    python3 python3-pip nodejs npm \
    xdotool xvfb fluxbox wget curl \
    git net-tools x11vnc supervisor \
    xterm falkon nano\
    && ln -fs /usr/share/zoneinfo/Asia/Kolkata /etc/localtime \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    && apt-get clean

RUN ln -s /usr/bin/python3 /usr/bin/python

# Install Jupyter and dependencies
RUN pip3 install notebook nbformat psutil

# Copy Jupyter configuration
COPY jupyter_config.py /usr/local/lib/python3.10/dist-packages/jupyter_config.py

# Setup noVNC
RUN git clone https://github.com/novnc/noVNC.git /opt/noVNC && \
    ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html && \
    git clone https://github.com/novnc/websockify /opt/noVNC/utils/websockify

# Copy context management files to /opt/context/ (won't be overwritten by volume mount)
RUN mkdir -p /opt/context/
COPY .debug/auto_capture.py /opt/context/
COPY .debug/context_manager.py /opt/context/
COPY .debug/jupyter_notebook_capture.py /opt/context/
COPY .debug/jupyter_extension.py /opt/context/

# Add non-root user for job execution
RUN useradd -m agentuser

# Set up workspace and permissions
RUN mkdir -p /workspace && chown agentuser:agentuser /workspace
RUN mkdir -p /workspace/logs && chown agentuser:agentuser /workspace/logs

# Set working directory
WORKDIR /workspace

# Create startup script to enable context capture
RUN echo '#!/bin/bash\n\
# Extract job_id from environment\n\
if [ -n "$JOB_ID" ]; then\n\
    echo "Setting up context capture for job: $JOB_ID"\n\
    # Create workspace directory if it doesn\'t exist\n\
    mkdir -p /workspace\n\
    # Create logs directory for supervisord\n\
    mkdir -p /workspace/logs\n\
    # Create hidden directory for debug/test files as root\n\
    mkdir -p /workspace/.debug\n\
    chmod 700 /workspace/.debug\n\
    # Copy context files directly to hidden directory\n\
    cp /opt/context/*.py /workspace/.debug/\n\
    # Set permissions for workspace\n\
    chown -R agentuser:agentuser /workspace\n\
    chmod 700 /workspace/.debug\n\
    # Start auto-capture in background (from hidden directory)\n\
    cd /workspace\n\
    PYTHONPATH=/workspace/.debug python3 -c "import auto_capture; auto_capture.start_auto_capture(\"$JOB_ID\")" &\n\
    echo "Context capture started"\n\
    # Start context file sync in background\n\
    (while true; do\n\
        if [ -d "/tmp/jobs/$JOB_ID/context" ]; then\n\
            cp -r /tmp/jobs/$JOB_ID/context/* /workspace/context/ 2>/dev/null || true\n\
        fi\n\
        sleep 10\n\
    done) &\n\
fi\n\
exec "$@"' > /usr/local/bin/context_capture_wrapper.sh && \
chmod +x /usr/local/bin/context_capture_wrapper.sh

# Remove all default supervisor configs except your own
RUN rm -f /etc/supervisord.conf /etc/supervisor/supervisord.conf /etc/supervisor/conf.d/*

# Copy supervisor config to the default location
COPY supervisord.conf /etc/supervisord.conf

# Switch to non-root user for job execution
USER agentuser

# Expose display server and jupyter
EXPOSE 6080 8888

# Entrypoint - use the wrapper to start context capture
ENTRYPOINT ["/usr/local/bin/context_capture_wrapper.sh"]
CMD ["/usr/bin/supervisord"] 