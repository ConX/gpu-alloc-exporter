import os
import subprocess
from collections import defaultdict
from prometheus_client import start_http_server, Gauge
import docker

# Prometheus metric: 1 if container is using GPU, 0 otherwise
gpu_container_allocation = Gauge(
    'gpu_container_allocation',
    'Indicates if a container is using a specific GPU',
    ['gpu', 'container', 'compose_project']
)

def get_available_gpus():
    try:
        output = subprocess.check_output([
            'nvidia-smi', '--query-gpu=index', '--format=csv,noheader'
        ], encoding='utf-8')
        return sorted([gpu.strip() for gpu in output.strip().split('\n') if gpu.strip()])
    except Exception:
        return []

def get_container_gpu_devices(container):
    # Returns a list of GPU IDs assigned to the container
    try:
        devreqs = container.attrs['HostConfig'].get('DeviceRequests', [])
        gpus = []
        for req in devreqs:
            if req is None:
                continue
            driver = req.get('Driver', '')
            caps = req.get('Capabilities', [])
            if driver == 'nvidia' or any('gpu' in cap for cap in sum(caps, [])):
                for device_id in req.get('DeviceIDs', []):
                    # Split comma-separated GPU IDs if present
                    if isinstance(device_id, str) and ',' in device_id:
                        gpus.extend([gpu.strip() for gpu in device_id.split(',') if gpu.strip()])
                    else:
                        gpus.append(str(device_id))
        return gpus
    except Exception:
        return []

def get_compose_project(container):
    try:
        return container.labels.get('com.docker.compose.project', '')
    except Exception:
        return ''

def collect_gpu_allocations():
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    containers = client.containers.list()
    gpu_to_containers = defaultdict(list)
    all_gpus = set(get_available_gpus())
    container_projects = {}
    for container in containers:
        gpus = get_container_gpu_devices(container)
        project = get_compose_project(container)
        container_projects[container.name] = project
        for gpu in gpus:
            gpu_to_containers[gpu].append(container.name)
            all_gpus.add(gpu)
    return all_gpus, gpu_to_containers, container_projects

def update_metrics():
    all_gpus, gpu_to_containers, container_projects = collect_gpu_allocations()
    # Clear all previous metrics to ensure a full refresh
    gpu_container_allocation._metrics.clear()
    for gpu in all_gpus:
        containers = gpu_to_containers.get(gpu, [])
        if containers:
            for container in containers:
                project = container_projects.get(container, '')
                gpu_container_allocation.labels(gpu=gpu, container=container, compose_project=project).set(1)
        else:
            gpu_container_allocation.labels(gpu=gpu, container='None', compose_project='').set(1)

def main():
    port = int(os.environ.get('EXPORTER_PORT', 8000))
    start_http_server(port)
    print(f"Exporter running on :{port}/metrics")
    import time
    while True:
        update_metrics()
        time.sleep(15)

if __name__ == '__main__':
    main()
