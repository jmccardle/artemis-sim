#!/usr/bin/env bash
# Build, push to local registry, and deploy to K3s.
# Usage: ./scripts/deploy.sh [--migrate]
set -euo pipefail

REGISTRY="registry.local:30500"
IMAGE="${REGISTRY}/artemis-sim"
TAG="${TAG:-latest}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building image ${IMAGE}:${TAG}"
docker build -t "${IMAGE}:${TAG}" "${PROJECT_DIR}"

echo "==> Pushing to local registry ${REGISTRY}"
docker push "${IMAGE}:${TAG}"

echo "==> Applying K8s manifests"
kubectl apply -f "${PROJECT_DIR}/k8s/artemis/configmap.yaml"
kubectl apply -f "${PROJECT_DIR}/k8s/artemis/secret.yaml"
kubectl apply -f "${PROJECT_DIR}/k8s/artemis/app.yaml"
kubectl apply -f "${PROJECT_DIR}/k8s/artemis/worker.yaml"

if [[ "${1:-}" == "--migrate" ]]; then
    echo "==> Running migration job"
    # Delete previous completed job if exists
    kubectl -n artemis delete job artemis-migrate --ignore-not-found
    kubectl apply -f "${PROJECT_DIR}/k8s/artemis/app.yaml"
    kubectl -n artemis wait --for=condition=complete job/artemis-migrate --timeout=60s
    echo "==> Migration complete"
fi

echo "==> Rolling restart of deployments"
kubectl -n artemis rollout restart deployment/artemis-app
kubectl -n artemis rollout restart deployment/artemis-worker
kubectl -n artemis rollout restart deployment/artemis-llm-worker

echo "==> Waiting for rollout"
kubectl -n artemis rollout status deployment/artemis-app --timeout=90s
kubectl -n artemis rollout status deployment/artemis-worker --timeout=90s
kubectl -n artemis rollout status deployment/artemis-llm-worker --timeout=90s

echo "==> Deploy complete"
kubectl -n artemis get pods
