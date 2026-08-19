import sys
from lbe_guard_inspector.runtime.process_events import ProcessEventType, observe_policy_command
from lbe_guard_inspector.runtime.validation_command_policy import ValidationCommandPolicy

def _policy(command): return ValidationCommandPolicy('p','op','coding','test',tuple(command),5)

def test_policy_command_emits_actual_stdout_stderr_and_completion(tmp_path):
    events=tuple(observe_policy_command(operation_id='op1',policy=_policy((sys.executable,'-c','import sys;print("out");print("err",file=sys.stderr)')),workspace_root=tmp_path))
    assert [event.event_type for event in events]==[ProcessEventType.STARTED,ProcessEventType.STDOUT,ProcessEventType.STDERR,ProcessEventType.COMPLETED]
    assert events[1].text=='out\n' and events[2].text=='err\n' and events[-1].exit_code==0

def test_policy_command_cancellation_terminates_real_process(tmp_path):
    events=tuple(observe_policy_command(operation_id='op2',policy=_policy((sys.executable,'-c','import time;time.sleep(5)')),workspace_root=tmp_path,cancel_after_seconds=.05))
    assert events[-1].event_type is ProcessEventType.CANCELLED
