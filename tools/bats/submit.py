"""
HogShade: submit a job to the running Job_Orchestrator (BATS) and wait for it. The developer path for every
Maya check: the orchestrator holds a resident Maya, the job runs inside it, and this prints the result.
Package: tools/bats/submit

Runs with the orchestrator's own interpreter (its venv has grpc and the protos); JOB_ORCHESTRATOR_ROOT
names the checkout (default D:/Depot/Job_Orchestrator):

    "%JOB_ORCHESTRATOR_ROOT%\\.venv\\Scripts\\python.exe" tools/bats/submit.py --gui --module hogshade.jobs.maya_ibl_check
    ... submit.py --gui --script probe.py                # an inline script file, STRING mode
    ... submit.py --pool                                 # what is running

A MODULE-mode job needs the HogShade root importable inside the worker; until the HogShade worker
overlay adds it to PYTHONPATH, --module wraps the import in a STRING-mode stub that inserts
--root into sys.path first. Parameters are passed as --param key=value.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JO_ROOT = Path(os.environ.get("JOB_ORCHESTRATOR_ROOT", "D:/Depot/Job_Orchestrator"))
sys.path.insert(0, str(JO_ROOT))

import grpc
from google.protobuf.json_format import MessageToDict
from job_orchestrator.protos import job_pb2, orchestrator_pb2, orchestrator_pb2_grpc

MODULE_STUB = """
import sys, json
root = r"{root}"
if root not in sys.path:
    sys.path.insert(0, root)
import importlib
mod = importlib.import_module("{module}")
params = json.loads(r'''{params_json}''')
result = getattr(mod, "{entry}")(params)
print("HOGSHADE_RESULT " + json.dumps(result, default=str))
"""


async def submit(args: argparse.Namespace) -> int:
    async with grpc.aio.insecure_channel(f"{args.host}:{args.port}") as channel:
        stub = orchestrator_pb2_grpc.ExternalJobAPIStub(channel)
        if args.pool:
            status = await stub.GetPoolStatus(orchestrator_pb2.PoolStatusRequest())
            print(json.dumps(MessageToDict(status), indent=2))
            return 0
        params = dict(kv.split("=", 1) for kv in args.param)
        if args.module:
            script = MODULE_STUB.format(
                root=str(args.root).replace("\\", "/"),
                module=args.module,
                params_json=json.dumps(params),
                entry=args.entry,
            )
        else:
            script = Path(args.script).read_text(encoding="utf-8")
        request = job_pb2.JobRequest(
            dcc_type=args.worker,
            execution_mode=job_pb2.GUI if args.gui else job_pb2.HEADLESS,
            priority=args.priority,
            submitter="hogshade",
            script=script,
            parameters={k: str(v) for k, v in params.items()},
            metadata={"project": "hogshade", "module": args.module or Path(args.script).name},
            execute_on_main_thread=args.main_thread,
            job_name=args.module or Path(args.script).name,
            tags=["hogshade"],
        )
        response = await stub.SubmitJob(request)
        print(f"submitted {response.job_id} (queue position {response.queue_position})")
        async for update in stub.StreamJobStatus(job_pb2.JobQuery(job_id=response.job_id)):
            name = job_pb2.JobStatus.Name(update.status) if isinstance(update.status, int) else str(update.status)
            print(f"[{name}] {getattr(update, 'progress_percent', 0)}% {getattr(update, 'message', '')}")
            if name in ("COMPLETED", "FAILED", "CANCELLED"):
                break
        result = await stub.GetJobResult(job_pb2.JobQuery(job_id=response.job_id))
        as_dict = MessageToDict(result)
        print(json.dumps(as_dict, indent=2)[: args.max_print])
        final = job_pb2.JobStatus.Name(result.status) if isinstance(result.status, int) else str(result.status)
        return 0 if final == "COMPLETED" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=50051)
    ap.add_argument("--worker", default="", help="worker type; default hogshade_maya, or hogshade_maya_gui with --gui")
    ap.add_argument("--gui", action="store_true", help="GUI execution mode (maya.exe, viewport)")
    ap.add_argument("--priority", type=int, default=5)
    ap.add_argument("--main-thread", action="store_true", help="run on the DCC main thread (viewport and UI work)")
    ap.add_argument("--module", default="", help="MODULE mode: importable module path (wrapped in a sys.path stub)")
    ap.add_argument("--entry", default="main")
    ap.add_argument("--script", default="", help="STRING mode: a Python file to send inline")
    ap.add_argument("--root", type=Path, default=ROOT, help="HogShade root the stub inserts into sys.path")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--pool", action="store_true", help="print the pool status and exit")
    ap.add_argument("--max-print", type=int, default=6000)
    args = ap.parse_args(argv)
    if not args.pool and not (args.module or args.script):
        ap.error("--module or --script is required")
    if not args.worker:
        args.worker = "hogshade_maya_gui" if args.gui else "hogshade_maya"
    return asyncio.run(submit(args))


if __name__ == "__main__":
    raise SystemExit(main())
