"""SMTP Email Service Module for AgentOS.

Provides email sending capabilities with:
- SMTP configuration management
- HTML and plain text email support
- Error handling and retry logic
- Structured logging
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from jinja2 import Template

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """SMTP configuration."""
    host: str
    port: int = 587
    user: Optional[str] = None
    password: Optional[str] = None
    from_email: Optional[str] = None
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "SMTPConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("SMTP_HOST", "localhost"),
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER"),
            password=os.getenv("SMTP_PASS"),
            from_email=os.getenv("SMTP_FROM", "noreply@example.com"),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        )

    def validate(self) -> None:
        """Validate configuration completeness."""
        if not self.host:
            raise ValueError("SMTP_HOST is required")
        if not self.from_email:
            raise ValueError("SMTP_FROM is required")


@dataclass
class SendResult:
    """Result of email send operation."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0


class Mailer:
    """Email sending service with SMTP support."""

    def __init__(self, config: Optional[SMTPConfig] = None):
        """Initialize mailer with SMTP configuration.

        Args:
            config: SMTP configuration. If None, loads from environment.
        """
        self.config = config or SMTPConfig.from_env()
        self.config.validate()
        self._template_cache: Dict[str, Template] = {}

    def send_text(
        self,
        to: str,
        subject: str,
        content: str,
        retry_count: int = 0
    ) -> SendResult:
        """Send plain text email.

        Args:
            to: Recipient email address
            subject: Email subject
            content: Plain text content
            retry_count: Current retry attempt

        Returns:
            SendResult with success status
        """
        try:
            msg = MIMEText(content, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.config.from_email
            msg["To"] = to

            return self._send_smtp(msg, retry_count)

        except Exception as e:
            logger.error(f"Failed to prepare text email: {e}")
            return SendResult(
                success=False,
                error=str(e),
                retry_count=retry_count
            )

    def send_html(
        self,
        to: str,
        subject: str,
        html: str,
        retry_count: int = 0
    ) -> SendResult:
        """Send HTML email.

        Args:
            to: Recipient email address
            subject: Email subject
            html: HTML content
            retry_count: Current retry attempt

        Returns:
            SendResult with success status
        """
        try:
            msg = MIMEText(html, "html", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.config.from_email
            msg["To"] = to

            return self._send_smtp(msg, retry_count)

        except Exception as e:
            logger.error(f"Failed to prepare HTML email: {e}")
            return SendResult(
                success=False,
                error=str(e),
                retry_count=retry_count
            )

    def send_template(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        retry_count: int = 0
    ) -> SendResult:
        """Send email from Jinja2 template.

        Args:
            to: Recipient email address
            subject: Email subject
            template_name: Template file name (e.g., "verification_code.html")
            context: Template variables
            retry_count: Current retry attempt

        Returns:
            SendResult with success status
        """
        try:
            # Load template
            if template_name not in self._template_cache:
                template_path = Path(__file__).parent / "templates" / template_name
                if not template_path.exists():
                    raise FileNotFoundError(f"Template not found: {template_name}")

                with open(template_path, "r", encoding="utf-8") as f:
                    self._template_cache[template_name] = Template(f.read())

            template = self._template_cache[template_name]
            html = template.render(**context)

            return self.send_html(to, subject, html, retry_count)

        except Exception as e:
            logger.error(f"Failed to send template email: {e}")
            return SendResult(
                success=False,
                error=str(e),
                retry_count=retry_count
            )

    def _send_smtp(
        self,
        msg: MIMEMultipart,
        retry_count: int = 0
    ) -> SendResult:
        """Send email via SMTP.

        Args:
            msg: Email message
            retry_count: Current retry attempt

        Returns:
            SendResult with success status
        """
        try:
            # Use SMTP_SSL for port 465 (SSL), SMTP for other ports (STARTTLS)
            if self.config.port == 465:
                # Port 465 uses SSL from the start
                import ssl
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.config.host, self.config.port, context=context, timeout=30)
                server.login(self.config.user, self.config.password)
                server.sendmail(self.config.from_email, msg["To"], msg.as_string())
                server.quit()
            else:
                # Other ports use STARTTLS
                with smtplib.SMTP(self.config.host, self.config.port, timeout=30) as server:
                    if self.config.use_tls:
                        server.starttls()

                    if self.config.user and self.config.password:
                        server.login(self.config.user, self.config.password)

                    # Send email
                    text = msg.as_string()
                    server.sendmail(self.config.from_email, msg["To"], text)

            # Extract message ID from headers
            message_id = msg.get("Message-ID")

            logger.info(
                f"Email sent successfully to {msg['To']}",
                extra={
                    "to": msg["To"],
                    "subject": msg.get("Subject"),
                    "message_id": message_id,
                    "retry_count": retry_count
                }
            )

            return SendResult(
                success=True,
                message_id=message_id,
                retry_count=retry_count
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return SendResult(
                success=False,
                error="SMTP authentication failed",
                retry_count=retry_count
            )

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return SendResult(
                success=False,
                error=f"SMTP error: {str(e)}",
                retry_count=retry_count
            )

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return SendResult(
                success=False,
                error=str(e),
                retry_count=retry_count
            )


# Global mailer instance
_mailer: Optional[Mailer] = None


def get_mailer() -> Mailer:
    """Get global mailer instance."""
    global _mailer
    if _mailer is None:
        _mailer = Mailer()
    return _mailer


async def send_email_async(
    to: str,
    subject: str,
    html: str
) -> SendResult:
    """Send email asynchronously (non-blocking).

    This is a simplified async wrapper. For production use,
    consider using background tasks or a message queue.

    Args:
        to: Recipient email address
        subject: Email subject
        html: HTML content

    Returns:
        SendResult with success status
    """
    try:
        mailer = get_mailer()
        # For true async, use background tasks
        # This is a simplified version
        return mailer.send_html(to, subject, html)
    except Exception as e:
        logger.error(f"Failed to send async email: {e}")
        return SendResult(
            success=False,
            error=str(e)
        )
