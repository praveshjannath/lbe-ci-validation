"""Bounded real-process observations for already policy-selected commands."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterator

from .validation_command_policy import ValidationCommandPolicy


class ProcessEventType(StrEnum):
    STARTED="command.started"; STDOUT="command.stdout.delta"; STDERR="command.stderr.delta"; COMPLETED="command.completed"; FAILED="command.failed"; CANCELLED="command.cancelled"

@dataclass(frozen=True)
class ProcessEvent:
    event_type: ProcessEventType; operation_id: str; sequence: int; elapsed_seconds: float; text: str | None=None; exit_code: int | None=None

def observe_policy_command(*, operation_id: str, policy: ValidationCommandPolicy, workspace_root: str|Path, cancel_after_seconds: float|None=None) -> Iterator[ProcessEvent]:
    """Run only a preselected argv with shell disabled and yield actual output."""
    if not operation_id.strip(): raise ValueError("operation_id must be non-empty")
    root=Path(workspace_root).resolve()
    if not root.is_dir(): raise FileNotFoundError("workspace root does not exist")
    started=time.monotonic(); sequence=0
    def event(kind:ProcessEventType, text:str|None=None, exit_code:int|None=None):
        nonlocal sequence; sequence+=1
        return ProcessEvent(kind,operation_id,sequence,time.monotonic()-started,text,exit_code)
    process=subprocess.Popen(policy.command,cwd=root,shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    yield event(ProcessEventType.STARTED)
    try:
        stdout,stderr=process.communicate(timeout=cancel_after_seconds or policy.timeout_seconds)
    except subprocess.TimeoutExpired:
        process.terminate(); stdout,stderr=process.communicate()
        if stdout: yield event(ProcessEventType.STDOUT,stdout)
        if stderr: yield event(ProcessEventType.STDERR,stderr)
        yield event(ProcessEventType.CANCELLED,exit_code=process.returncode)
        return
    if stdout: yield event(ProcessEventType.STDOUT,stdout)
    if stderr: yield event(ProcessEventType.STDERR,stderr)
    yield event(ProcessEventType.COMPLETED if process.returncode==0 else ProcessEventType.FAILED,exit_code=process.returncode)
