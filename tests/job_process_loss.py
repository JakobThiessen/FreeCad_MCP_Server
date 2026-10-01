"""Controlled Stage 8 job timeout and process-loss checks against an isolated bridge."""

import argparse
import json
import sys
import time

from freecad_mcp.connection import FreeCADConnection


def connect(port, timeout=30.0):
    connection = FreeCADConnection(port=port, timeout=timeout)
    if not connection.connect():
        raise RuntimeError(f"Bridge on port {port} is not available")
    return connection


def start_job(port):
    connection = connect(port)
    document = connection.call_function(
        "freecad_ai_bridge.operations", "create_document", name="MCP_Process_Loss"
    )["name"]
    job = connection.start_job(
        "freecad_ai_bridge.operations",
        "execute_batch",
        steps=[{
            "id": "box",
            "operation": "part_box",
            "doc_name": document,
            "arguments": {"length": 10, "width": 10, "height": 10, "name": "JobBox"},
        }],
        atomic=True,
        preview=False,
    )
    job_id = job["job_id"]
    timed_out = False
    try:
        FreeCADConnection(port=port, timeout=0.000001).get_job(job_id)
    except (ConnectionError, OSError, TimeoutError):
        timed_out = True
    if not timed_out:
        raise AssertionError("Expected the deliberately tiny transport timeout")
    for _ in range(200):
        job = connection.get_job(job_id)
        if job["status"] not in {"queued", "running"}:
            break
        time.sleep(0.01)
    if job["status"] != "succeeded":
        raise AssertionError(job)
    print(json.dumps({"job_id": job_id, "timeout_observed": True, "status": job["status"]}))


def query_lost_job(port, job_id):
    result = connect(port).get_job(job_id)
    if result["status"] != "unknown" or not result["warnings"]:
        raise AssertionError(result)
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["start", "query"])
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--job-id")
    arguments = parser.parse_args()
    if arguments.mode == "start":
        start_job(arguments.port)
    else:
        if not arguments.job_id:
            parser.error("--job-id is required for query")
        query_lost_job(arguments.port, arguments.job_id)


if __name__ == "__main__":
    sys.exit(main())