
import queue
import datetime
import uuid

# Global queue for observability events
observability_queue = queue.Queue()


def log_step(operation: str, detail: str = None):
    """Push a step into the observability queue."""
    event = {"operation": operation}
    if detail:
        event["detail"] = detail
    observability_queue.put(event)

def log_event(message: str):
    """Push a log event into the observability queue."""
    event = {"operation": message}
    observability_queue.put(event)

def log_trace(intent: str, system: str, agent: str, operation: str, attributes=None):
    """Push a trace summary into the observability queue."""
    trace_event = {
        "operation": "TRACE SUMMARY",
        "intent": intent,
        "system": system,
        "agent": agent,
        "operation_type": operation,
        "attributes": attributes
    }
    observability_queue.put(trace_event)
