from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import ItemStatus, OperationalEvent, SessionOperationalHistory, TurnStatus
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.runtime.tool_orchestration import ToolReceipt, ToolReceiptStatus

def test_ordered_events_reopen_and_preserve_identity(tmp_path):
    store=WorkspaceMemoryStore(tmp_path/'state.sqlite3')
    store.save_session_state(SessionState(session_id='s1',project_workspace_id='w1',canonical_workspace_root=tmp_path,mode='coding'))
    history=SessionOperationalHistory(store=store); turn=history.start_turn(session_id='s1'); item=history.start_item(turn_id=turn.turn_id,kind='model.exchange')
    first=history.append_event(OperationalEvent(session_id='s1',turn_id=turn.turn_id,item_id=item.item_id,event_type='model.turn.started',payload={},provider_request_id='request-1'))
    second=history.append_event(OperationalEvent(session_id='s1',turn_id=turn.turn_id,item_id=item.item_id,event_type='model.turn.completed',payload={},provider_request_id='request-1'))
    assert (first.session_sequence,second.session_sequence)==(1,2)
    assert [e.provider_request_id for e in SessionOperationalHistory(store=WorkspaceMemoryStore(tmp_path/'state.sqlite3')).events_for_turn(turn_id=turn.turn_id)]==['request-1','request-1']
    assert history.finalize_turn(turn_id=turn.turn_id,status=TurnStatus.COMPLETED).status is TurnStatus.COMPLETED
    assert history.finalize_item(item_id=item.item_id,status=ItemStatus.COMPLETED).status is ItemStatus.COMPLETED
    assert history.replay_turn_status(turn_id=turn.turn_id) is TurnStatus.COMPLETED

def test_receipt_projection_preserves_real_operation_without_executing_tool(tmp_path):
    store=WorkspaceMemoryStore(tmp_path/'state.sqlite3'); store.save_session_state(SessionState(session_id='s1',project_workspace_id='w1',canonical_workspace_root=tmp_path,mode='coding'))
    history=SessionOperationalHistory(store=store); turn=history.start_turn(session_id='s1')
    event=history.project_tool_receipt(session_id='s1',turn_id=turn.turn_id,item_id=None,receipt=ToolReceipt(operation_id='op1',tool_id='workspace.read',status=ToolReceiptStatus.ESCALATED,authorization=None,error_code='ESCALATED'),provider_tool_call_id='provider1',lbe_call_id='lbe1')
    assert event.event_type=='tool.escalated' and event.runtime_operation_id=='op1' and event.lbe_call_id=='lbe1' and event.tool_receipt_id==event.payload['receipt_id']
