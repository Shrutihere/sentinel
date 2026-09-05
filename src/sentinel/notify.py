"""Best-effort notifications for pending approvals (M3).

Optional: if SENTINEL_SLACK_WEBHOOK_URL is set, post a message when an action is
parked for review. Failures are swallowed — the durable ApprovalRequest row is
the source of truth, so a missed notification never blocks or loses a request.
"""

from __future__ import annotations

import json
import urllib.request

from .config import settings
from .models import ApprovalRequest


def notify_pending(ar: ApprovalRequest) -> None:
    url = settings.slack_webhook_url
    if not url:
        return
    text = (
        f":warning: *Sentinel — approval needed* (#{ar.id})\n"
        f"> *{ar.tool}*: `{ar.action}`\n"
        f"> env=`{ar.target.get('env')}`  severity=`{ar.severity}`\n"
        f"> {ar.reasons[0] if ar.reasons else ''}\n"
        f"Approve: `POST /v1/approvals/{ar.id}/approve`  ·  Deny: `/deny`"
    )
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"text": text}).encode(),
            headers={"content-type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=3)  # noqa: S310 (trusted operator URL)
    except Exception:
        pass  # best-effort by design
