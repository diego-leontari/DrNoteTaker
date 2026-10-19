import os

from dotenv import load_dotenv

# find_dotenv() searches upward from this file, so it works from mailer/ or the project root.
load_dotenv()

_session = None


def _get_session():
    """Create the Composio session once and reuse it."""
    global _session
    if _session is None:
        from composio import Composio

        user_id = os.environ.get("COMPOSIO_USER_ID")
        if not user_id:
            raise RuntimeError("COMPOSIO_USER_ID is not set")
        _session = Composio().create(user_id=user_id)
    return _session


def send_email(to: str, subject: str, html: str) -> dict:
    """Returns {"ok": True, "error": None} or {"ok": False, "error": "message"}. Never raises."""
    try:
        if not to:
            return {"ok": False, "error": "Missing recipient email"}
        result = _get_session().execute(
            "GMAIL_SEND_EMAIL",
            arguments={
                "recipient_email": to,
                "subject": subject,
                "body": html,
                "is_html": True,
            },
        )
        if result.error or result.result_type == "failed":
            return {"ok": False, "error": str(result.error or "Gmail send failed")}
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
