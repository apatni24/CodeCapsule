#!/bin/bash

# CodeCapsule Kubernetes Deployment Script

set -e

# Helper function for error handling
function check_success {
    if [ $? -ne 0 ]; then
        echo "❌ $1 failed. Exiting."
        exit 1
    else
        echo "✅ $2"
    fi
}

echo "🚀 Starting Minikube..."
minikube start
check_success "Minikube start" "Minikube started successfully."

echo "🔨 Setting Docker env to Minikube..."
eval $(minikube docker-env)
check_success "Setting Docker env" "Docker environment set to Minikube."

echo "🔨 Building Docker image..."
docker build -t code-capsule-agent:latest .
check_success "Docker build" "Docker image built successfully."

echo "📦 Creating namespace..."
kubectl create namespace code-capsule --dry-run=client -o yaml | kubectl apply -f -
check_success "Namespace creation" "Namespace 'code-capsule' ensured."

echo "🔑 Applying RBAC..."
kubectl apply -f k8s/orchestrator-rbac.yaml
check_success "RBAC apply" "RBAC applied successfully."

echo "📦 Deploying orchestrator..."
kubectl apply -f k8s/orchestrator-deployment.yaml
check_success "Orchestrator deployment" "Orchestrator deployment applied."

echo "🔄 Restarting orchestrator deployment..."
kubectl rollout restart deployment/code-capsule-orchestrator -n code-capsule
check_success "Orchestrator restart" "Orchestrator deployment restarted."

echo "⏳ Waiting for orchestrator to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/code-capsule-orchestrator -n code-capsule
if [ $? -ne 0 ]; then
    echo "❌ Orchestrator did not become ready in time. Check pod status with: kubectl get pods -n code-capsule"
    exit 1
else
    echo "✅ Orchestrator is ready."
fi

echo "🌐 Getting orchestrator service URL..."
minikube service code-capsule-orchestrator -n code-capsule --url
ORCH_URL=$(0)
if [ $? -ne 0 ] || [ -z "$ORCH_URL" ]; then
    echo "⚠️ Could not get orchestrator service URL. You may need to use port-forward:"
    echo "kubectl port-forward service/code-capsule-orchestrator 8000:8000 -n code-capsule"
    ORCH_URL="http://localhost:8000"
else
    echo "✅ Orchestrator service URL: $ORCH_URL"
fi

echo "🎉 Deployment complete! Use the above URL for API calls."

# Get the service URL
ORCHESTRATOR_URL=$(kubectl get service code-capsule-orchestrator -n code-capsule -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
if [ -z "$ORCHESTRATOR_URL" ]; then
    ORCHESTRATOR_URL=$(kubectl get service code-capsule-orchestrator -n code-capsule -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
fi

if [ -z "$ORCHESTRATOR_URL" ]; then
    echo "⚠️ Could not get external IP. You may need to use port-forward:"
    echo "kubectl port-forward service/code-capsule-orchestrator 8000:8000 -n code-capsule"
    ORCHESTRATOR_URL="localhost:8000"
else
    ORCHESTRATOR_URL="$ORCHESTRATOR_URL:8000"
fi

echo "🎉 CodeCapsule deployed successfully!"
echo "📡 Orchestrator URL: http://$ORCHESTRATOR_URL"
echo ""
echo "🧪 Test the deployment:"
echo "curl -X POST \"http://$ORCHESTRATOR_URL/schedule?task=Test%20Kubernetes%20deployment\""
echo ""
echo "📊 Check status:"
echo "kubectl get pods -n code-capsule"
echo "kubectl get services -n code-capsule" 