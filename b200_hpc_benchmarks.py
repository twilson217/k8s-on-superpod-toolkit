#!/usr/bin/env python3
"""
Script to run NCCL tests using NVIDIA HPC Benchmarks 25.02 container in RunAI environment.

This script uses the same configuration that was validated on Slurm with B200 nodes.

Usage:
    python b200_hpc_benchmarks.py --project <PROJECT_NAME> --nodes <NUM_NODES>

Example:
    python b200_hpc_benchmarks.py --project test --nodes 2
"""

import argparse
import subprocess
import sys
import os
import time
import threading
import re
from datetime import datetime


def get_next_job_number(project_name):
    """
    Get the next job number by checking existing HPC benchmark workloads.
    
    Args:
        project_name: Name of the RunAI project
    
    Returns:
        Next job number to use
    """
    try:
        # Run runai training mpi list to get existing workloads
        cmd = ["runai", "training", "mpi", "list"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse the output to find hpc-bench* jobs
        lines = result.stdout.strip().split('\n')
        
        # Find all job numbers from hpc-bench* workloads
        job_numbers = []
        for line in lines:
            # Look for lines containing hpc-bench followed by a number
            match = re.search(r'hpc-bench(\d+)', line)
            if match:
                job_numbers.append(int(match.group(1)))
        
        # If we found any jobs, return max + 1, otherwise start at 1
        if job_numbers:
            next_number = max(job_numbers) + 1
            print(f"Found existing HPC benchmark jobs: {sorted(job_numbers)}")
            print(f"Using next available number: {next_number}")
        else:
            next_number = 1
            print("No existing HPC benchmark jobs found. Starting with: 1")
        
        return next_number
        
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not list existing jobs: {e.stderr}", file=sys.stderr)
        print("Defaulting to job number 1")
        return 1
    except Exception as e:
        print(f"Warning: Error parsing job list: {e}", file=sys.stderr)
        print("Defaulting to job number 1")
        return 1


def ensure_logs_directory():
    """Create .logs directory if it doesn't exist."""
    logs_dir = ".logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print(f"Created directory: {logs_dir}")
    return logs_dir


def wait_for_pods(namespace, job_name, expected_pods, timeout=300):
    """
    Wait for pods to be created and running.
    
    Args:
        namespace: Kubernetes namespace
        job_name: Name of the job
        expected_pods: Expected number of pods (launcher + workers)
        timeout: Maximum time to wait in seconds
    
    Returns:
        List of pod names if successful, empty list otherwise
    """
    print(f"\nWaiting for pods to be created in namespace {namespace}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Get pods with the job label
            cmd = [
                "kubectl", "get", "pods", "-n", namespace,
                "-l", f"app={job_name}",
                "-o", "jsonpath={.items[*].metadata.name}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            pod_names = result.stdout.strip().split()
            
            if len(pod_names) >= expected_pods:
                # Check if all pods are running or succeeded
                all_ready = True
                for pod in pod_names:
                    status_cmd = [
                        "kubectl", "get", "pod", pod, "-n", namespace,
                        "-o", "jsonpath={.status.phase}"
                    ]
                    status_result = subprocess.run(status_cmd, capture_output=True, text=True, check=True)
                    status = status_result.stdout.strip()
                    if status not in ["Running", "Succeeded"]:
                        all_ready = False
                        break
                
                if all_ready:
                    print(f"Found {len(pod_names)} pod(s): {', '.join(pod_names)}")
                    return pod_names
            
            time.sleep(5)
        except subprocess.CalledProcessError:
            time.sleep(5)
    
    print(f"Timeout waiting for pods after {timeout} seconds")
    return []


def stream_pod_logs(namespace, pod_name, log_file_path):
    """
    Stream logs from a pod to a file.
    
    Args:
        namespace: Kubernetes namespace
        pod_name: Name of the pod
        log_file_path: Path to the log file
    """
    print(f"Starting log capture for pod {pod_name} -> {log_file_path}")
    
    try:
        with open(log_file_path, 'w') as log_file:
            # Stream logs using kubectl logs -f
            cmd = ["kubectl", "logs", "-f", pod_name, "-n", namespace]
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True
            )
            process.wait()
    except Exception as e:
        print(f"Error capturing logs for {pod_name}: {e}")


def capture_logs_for_job(namespace, job_name, num_nodes):
    """
    Capture logs from all pods associated with the job.
    
    Args:
        namespace: Kubernetes namespace
        job_name: Name of the job
        num_nodes: Number of worker nodes
    """
    # Ensure logs directory exists
    logs_dir = ensure_logs_directory()
    
    # Generate timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Expected pods: 1 launcher + num_nodes workers
    expected_pods = num_nodes + 1
    
    # Wait for pods to be created
    pod_names = wait_for_pods(namespace, job_name, expected_pods)
    
    if not pod_names:
        print("Failed to find pods. Logs will not be captured.")
        return
    
    # Start log streaming in separate threads for each pod
    threads = []
    for pod_name in pod_names:
        log_file_name = f"{job_name}_{pod_name}_{timestamp}.log"
        log_file_path = os.path.join(logs_dir, log_file_name)
        
        thread = threading.Thread(
            target=stream_pod_logs,
            args=(namespace, pod_name, log_file_path)
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    print(f"\nLog capture started for {len(pod_names)} pod(s).")
    print(f"Logs are being saved to: {logs_dir}/")
    print("\nNote: Log streaming will continue in the background.")
    print("You can monitor the job with: kubectl get pods -n", namespace)
    
    # Optional: Wait a bit to ensure logs start being captured
    time.sleep(2)


def run_nccl_test(project_name, num_nodes):
    """
    Run NCCL test using NVIDIA HPC Benchmarks 25.02 container in RunAI environment.
    
    This uses the same configuration validated on Slurm with B200 nodes.
    
    Args:
        project_name: Name of the RunAI project
        num_nodes: Number of worker nodes to use
    """
    
    # First, configure the project
    print(f"Configuring RunAI project: {project_name}")
    config_cmd = ["runai", "config", "project", project_name]
    
    try:
        result = subprocess.run(config_cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error configuring project: {e.stderr}", file=sys.stderr)
        return 1
    
    # Get the next available job number
    job_number = get_next_job_number(project_name)
    job_name = f"hpc-bench{job_number}"
    
    print(f"\nJob name for this run: {job_name}")
    print(f"Using NVIDIA HPC Benchmarks 25.02 container (CUDA 12.8+, NCCL 2.23+)")
    
    # Calculate total number of processes (num_nodes * 8 GPUs per node)
    total_processes = num_nodes * 8
    
    # Build the MPI submit command - based on working Slurm configuration
    submit_cmd = [
        "runai", "mpi", "submit", job_name,
        "-i", "nvcr.io/nvidia/hpc-benchmarks:25.02",  # HPC Benchmarks 25.02 (CUDA 12.8+)
        "--workers", str(num_nodes),
        "--gpu-devices-request", "8",
        # Request SR-IOV VFs for all 8 IB adapters
        "--extended-resource", "nvidia.com/resibp24s0=1",
        "--extended-resource", "nvidia.com/resibp64s0=1",
        "--extended-resource", "nvidia.com/resibp79s0=1",
        "--extended-resource", "nvidia.com/resibp94s0=1",
        "--extended-resource", "nvidia.com/resibp154s0=1",
        "--extended-resource", "nvidia.com/resibp192s0=1",
        "--extended-resource", "nvidia.com/resibp206s0=1",
        "--extended-resource", "nvidia.com/resibp220s0=1",
        "--large-shm",
        "--stdin",
        "--tty",
        "--master-command", "mpirun",
        "--master-args", (
            f"--allow-run-as-root --bind-to none -map-by slot -np {total_processes} "
            "-x NCCL_NVLS_ENABLE -x NCCL_IB_ADAPTIVE_ROUTING -x NCCL_IB_SL "
            "-x NCCL_IB_QPS_PER_CONNECTION -x NCCL_IB_SPLIT_DATA_ON_QPS "
            "-x NCCL_IB_HCA -x NCCL_SOCKET_IFNAME -x NCCL_ALGO -x UCX_TLS "
            "all_reduce_perf_mpi -b 1G -f 2 -g 8 -e 32G"
        ),
        "--image-pull-policy", "IfNotPresent",
        # Attach InfiniBand VFs to pods via Multus
        "--annotation", (
            "k8s.v1.cni.cncf.io/networks=default/ibp192s0,default/ibp206s0,default/ibp154s0,"
            "default/ibp220s0,default/ibp24s0,default/ibp64s0,default/ibp79s0,default/ibp94s0"
        ),
        # NCCL Configuration - Exact match to working Slurm configuration
        "-e", "NCCL_NVLS_ENABLE=1",  # Enable NVLink Switch (critical for B200)
        "-e", "NCCL_IB_ADAPTIVE_ROUTING=1",  # Enable adaptive routing
        "-e", "NCCL_IB_SL=1",  # Service level
        "-e", "NCCL_IB_QPS_PER_CONNECTION=2",  # Queue pairs per connection
        "-e", "NCCL_IB_SPLIT_DATA_ON_QPS=0",  # Don't split data across QPs
        "-e", "NCCL_IB_HCA=mlx5_15,mlx5_10,mlx5_14,mlx5_13,mlx5_8,mlx5_7,mlx5_9,mlx5_4",  # All 8 IB adapters
        "-e", "NCCL_SOCKET_IFNAME=eth0",  # Use eth0 for bootstrap (container interface, not bond0)
        "-e", "NCCL_ALGO=RING",  # Use ring algorithm
        # UCX Configuration for MPI transport
        "-e", "UCX_TLS=rc"  # Use reliable connection transport
    ]
    
    print(f"\nSubmitting HPC Benchmark with {num_nodes} nodes ({total_processes} total processes)...")
    print(f"Command: {' '.join(submit_cmd)}\n")
    
    try:
        result = subprocess.run(submit_cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print("\nHPC Benchmark test submitted successfully!")
        
        # Start capturing logs from the job pods
        namespace = f"runai-{project_name}"
        capture_logs_for_job(namespace, job_name, num_nodes)
        
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error submitting HPC Benchmark test: {e.stderr}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Run NCCL tests using NVIDIA HPC Benchmarks 25.02 in RunAI environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python b200_hpc_benchmarks.py --project test --nodes 2
  python b200_hpc_benchmarks.py --project my-project --nodes 4

Container: nvcr.io/nvidia/hpc-benchmarks:25.02
  - CUDA 12.8+ (required for Blackwell B200)
  - NCCL 2.23+
  - Validated on Slurm with B200 nodes

Test: all_reduce_perf_mpi -b 1G -f 2 -g 8 -e 32G
  - 1GB starting message size
  - 2x factor increase per iteration
  - 8 GPUs per node
  - 32GB maximum message size
        """
    )
    
    parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="RunAI project name"
    )
    
    parser.add_argument(
        "--nodes",
        type=int,
        required=True,
        help="Number of worker nodes to use (each node has 8 GPUs)"
    )
    
    args = parser.parse_args()
    
    if args.nodes < 1:
        print("Error: Number of nodes must be at least 1", file=sys.stderr)
        return 1
    
    return run_nccl_test(args.project, args.nodes)


if __name__ == "__main__":
    sys.exit(main())

