"""ID generation utilities"""

import uuid
from datetime import datetime


def generate_hypothesis_id() -> str:
    """Generate unique hypothesis ID: hyp_<timestamp>_<uuid>"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"hyp_{timestamp}_{short_uuid}"


def generate_review_id() -> str:
    """Generate unique review ID: rev_<timestamp>_<uuid>"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"rev_{timestamp}_{short_uuid}"


def generate_match_id() -> str:
    """Generate unique tournament match ID: match_<timestamp>_<uuid>"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"match_{timestamp}_{short_uuid}"


def generate_task_id() -> str:
    """Generate unique task ID: task_<timestamp>_<uuid>"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"task_{timestamp}_{short_uuid}"
