import pytest
from lbe_guard_inspector.control_protocol import ControlMethod,ControlOutcome,ControlRequest
def test_control_protocol_accepts_typed_steering_request_and_explicit_outcome():
    request=ControlRequest('r1',ControlMethod.TURN_STEER,{'text':'focus tests'})
    assert ControlOutcome(request.request_id,True,'queued').state=='queued'
def test_control_protocol_rejects_untyped_or_silent_rejection():
    with pytest.raises(ValueError): ControlRequest('',ControlMethod.TURN_CANCEL,{})
    with pytest.raises(ValueError): ControlOutcome('r1',False,'rejected')
