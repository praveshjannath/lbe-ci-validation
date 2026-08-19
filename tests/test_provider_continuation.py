import pytest
from lbe_guard_inspector.provider_continuation import continue_provider, continuation_from_receipt
from lbe_guard_inspector.runtime.tool_orchestration import ToolReceipt, ToolReceiptStatus

def _receipt(status=ToolReceiptStatus.EXECUTED): return ToolReceipt(operation_id='op1',tool_id='workspace.read',status=status,authorization=None,output={'text':'ok'} if status is ToolReceiptStatus.EXECUTED else None,error_code='DENIED' if status is not ToolReceiptStatus.EXECUTED else None)
def test_continuation_requires_governed_receipt_and_preserves_all_identities():
    result=continuation_from_receipt(provider_tool_call_id='provider1',lbe_call_id='lbe1',receipt=_receipt())
    assert result.runtime_operation_id=='op1' and result.tool_receipt_id.startswith('receipt-') and result.output=={'text':'ok'}
def test_escalation_stops_before_provider_continuation():
    with pytest.raises(ValueError,match='stop'): continuation_from_receipt(provider_tool_call_id='provider1',lbe_call_id='lbe1',receipt=_receipt(ToolReceiptStatus.ESCALATED))
def test_sender_receives_only_receipt_backed_continuation():
    item=continuation_from_receipt(provider_tool_call_id='provider1',lbe_call_id='lbe1',receipt=_receipt())
    assert continue_provider(continuation=item,sender=lambda value:value.tool_receipt_id)==item.tool_receipt_id
