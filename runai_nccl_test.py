#!/usr/bin/env python3
"""
Script to run multi-node NCCL tests in a RunAI environment.

Usage:
    python run_nccl_test.py --project <PROJECT_NAME> --nodes <NUM_NODES>

Example:
    python run_nccl_test.py --project test --nodes 2
"""

import argparse
import subprocess
import sys


def run_nccl_test(project_name, num_nodes):
    """
    Run NCCL test using RunAI MPI submit command.
    
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
    
    # Calculate total number of processes (num_nodes * 8 GPUs per node)
    total_processes = num_nodes * 8
    
    # Build the MPI submit command
    submit_cmd = [
        "runai", "mpi", "submit", "nccl-test1",
        "-i", "docker.io/deepops/nccl-tests:2312",
        "--workers", str(num_nodes),
        "--gpu-devices-request", "8",
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
            "-mca pml ob1 -mca btl self,tcp all_reduce_perf_mpi -b 1G -e 16G -f 2 -n 100 -g 1"
        ),
        "--image-pull-policy", "IfNotPresent",
        "--annotation", (
            "k8s.v1.cni.cncf.io/networks=default/ibp192s0,default/ibp206s0,default/ibp154s0,"
            "default/ibp220s0,default/ibp24s0,default/ibp64s0,default/ibp79s0,default/ibp94s0"
        ),
        "-e", "CUDA_DEVICE_MAX_CONNECTIONS=1",
        "-e", "NCCL_SOCKET_IFNAME=eth0",
        "-e", "NCCL_ASYNC_ERROR_HANDLING=1",
        "-e", "NCCL_IB_QPS_PER_CONNECTION=2",
        "-e", "NCCL_IB_SPLIT_DATA_ON_QPS=0"
    ]
    
    print(f"\nSubmitting NCCL test with {num_nodes} nodes ({total_processes} total processes)...")
    print(f"Command: {' '.join(submit_cmd)}\n")
    
    try:
        result = subprocess.run(submit_cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print("\nNCCL test submitted successfully!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error submitting NCCL test: {e.stderr}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Run multi-node NCCL tests in RunAI environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_nccl_test.py --project test --nodes 2
  python run_nccl_test.py --project my-project --nodes 4
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
