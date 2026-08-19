"""Receipt-backed provider continuation boundary with no execution authority."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .runtime.tool_orchestration import ToolReceipt, ToolReceiptStatus


@dataclass(frozen=True)
class ProviderToolContinuation:
    provider_tool_call_id: str
    lbe_call_id: str
    runtime_operation_id: str
    tool_receipt_id: str
    tool_name: str
    output: Mapping[str, Any]
    is_error: bool


def continuation_from_receipt(*, provider_tool_call_id: str, lbe_call_id: str, receipt: ToolReceipt) -> ProviderToolContinuation:
    """Convert an already-governed receipt; this function never invokes a tool."""
    for name, value in (("provider_tool_call_id", provider_tool_call_id), ("lbe_call_id", lbe_call_id)):
        if not isinstance(value, str) or not value.strip(): raise ValueError(f"{name} must be non-empty")
    if not isinstance(receipt, ToolReceipt): raise TypeError("receipt must be ToolReceipt")
    if receipt.status is ToolReceiptStatus.ESCALATED: raise ValueError("escalated receipt must stop for approval, not continue provider")
    output = dict(receipt.output or {}) if receipt.status is ToolReceiptStatus.EXECUTED else {
        "status": receipt.status.value, "error_code": receipt.error_code, "error_message": receipt.error_message,
    }
    return ProviderToolContinuation(provider_tool_call_id.strip(),lbe_call_id.strip(),receipt.operation_id,receipt.receipt_id,receipt.tool_id,output,receipt.status is not ToolReceiptStatus.EXECUTED)


def continue_provider(*, continuation: ProviderToolContinuation, sender: Callable[[ProviderToolContinuation], Any]) -> Any:
    """Send only an existing receipt-backed continuation to a provider adapter."""
    if not isinstance(continuation, ProviderToolContinuation): raise TypeError("continuation must be ProviderToolContinuation")
    if not callable(sender): raise TypeError("sender must be callable")
    return sender(continuation)
