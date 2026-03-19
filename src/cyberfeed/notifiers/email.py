"""Email notifier using aiosmtplib."""

import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from cyberfeed.notifiers.base import AbstractNotifier, NotificationPayload

logger = structlog.get_logger()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class EmailNotifier(AbstractNotifier):
    """Send notifications via SMTP email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    async def send(self, recipient: str, payload: NotificationPayload) -> bool:
        """Send an email to the given address."""
        try:
            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_addr
            msg["To"] = recipient
            msg["Subject"] = payload.subject

            # Plain text
            text_body = payload.body
            if payload.article_url:
                text_body += f"\n\nRead more: {payload.article_url}"
            msg.attach(MIMEText(text_body, "plain"))

            # HTML version
            if payload.html_body:
                msg.attach(MIMEText(payload.html_body, "html"))
            else:
                html = f"<p>{payload.body}</p>"
                if payload.article_url:
                    html += f'<p><a href="{payload.article_url}">Read more</a></p>'
                msg.attach(MIMEText(html, "html"))

            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
            return True

        except Exception as e:
            await logger.awarning("Email send failed", error=str(e), recipient=recipient)
            return False

    async def validate_recipient(self, recipient: str) -> tuple[bool, str]:
        """Validate email address format."""
        if EMAIL_REGEX.match(recipient):
            return True, ""
        return False, "Invalid email address format"
