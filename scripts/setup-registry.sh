#!/usr/bin/env bash
# One-time setup: configure K3s and Docker to use the local registry.
# Run with: sudo ./scripts/setup-registry.sh
set -euo pipefail

REGISTRY_HOST="registry.local"
REGISTRY_PORT="30500"
NODE_IP="192.168.1.100"

echo "==> Adding ${REGISTRY_HOST} to /etc/hosts"
if ! grep -q "${REGISTRY_HOST}" /etc/hosts; then
    echo "${NODE_IP}  ${REGISTRY_HOST}" >> /etc/hosts
    echo "    Added"
else
    echo "    Already present"
fi

echo "==> Configuring K3s containerd mirror"
mkdir -p /etc/rancher/k3s
cat > /etc/rancher/k3s/registries.yaml <<YAML
mirrors:
  "${REGISTRY_HOST}:${REGISTRY_PORT}":
    endpoint:
      - "http://${NODE_IP}:${REGISTRY_PORT}"
YAML
echo "    Wrote /etc/rancher/k3s/registries.yaml"

echo "==> Configuring Docker insecure registry"
DAEMON_JSON="/etc/docker/daemon.json"
if [ -f "${DAEMON_JSON}" ]; then
    # Merge with existing config using python
    python3 -c "
import json, sys
with open('${DAEMON_JSON}') as f:
    cfg = json.load(f)
registries = cfg.get('insecure-registries', [])
entry = '${REGISTRY_HOST}:${REGISTRY_PORT}'
if entry not in registries:
    registries.append(entry)
    cfg['insecure-registries'] = registries
    with open('${DAEMON_JSON}', 'w') as f:
        json.dump(cfg, f, indent=2)
    print('    Updated existing daemon.json')
else:
    print('    Already configured')
"
else
    cat > "${DAEMON_JSON}" <<JSON
{
  "insecure-registries": ["${REGISTRY_HOST}:${REGISTRY_PORT}"]
}
JSON
    echo "    Created ${DAEMON_JSON}"
fi

echo "==> Restarting Docker"
systemctl restart docker
echo "    Docker restarted"

echo "==> Restarting K3s"
systemctl restart k3s
echo "    K3s restarted"

echo ""
echo "==> Setup complete. Verify with:"
echo "    curl http://${REGISTRY_HOST}:${REGISTRY_PORT}/v2/"
echo "    docker push ${REGISTRY_HOST}:${REGISTRY_PORT}/test:latest"
