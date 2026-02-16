"""Unit tests for Auth Mailer module.

Tests B-03A: SMTP email service configuration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from agent_os.auth.mailer import (
    SMTPConfig,
    Mailer,
    SendResult,
    get_mailer
)


class TestSMTPConfig:
    """Test SMTP configuration."""

    def test_from_env(self, monkeypatch):
        """Test loading config from environment variables."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "password123")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
        monkeypatch.setenv("SMTP_USE_TLS", "true")

        config = SMTPConfig.from_env()

        assert config.host == "smtp.example.com"
        assert config.port == 587
        assert config.user == "user@example.com"
        assert config.password == "password123"
        assert config.from_email == "noreply@example.com"
        assert config.use_tls is True

    def test_from_env_defaults(self, monkeypatch):
        """Test default values for optional config."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

        config = SMTPConfig.from_env()

        assert config.host == "smtp.example.com"
        assert config.port == 587  # Default
        assert config.user is None
        assert config.password is None
        assert config.from_email == "noreply@example.com"  # Default
        assert config.use_tls is True  # Default

    def test_from_env_tls_disabled(self, monkeypatch):
        """Test TLS can be disabled."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_USE_TLS", "false")

        config = SMTPConfig.from_env()
        assert config.use_tls is False

    def test_validate_success(self, monkeypatch):
        """Test validation passes with required fields."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        config = SMTPConfig.from_env()
        config.validate()  # Should not raise

    def test_validate_missing_host(self, monkeypatch):
        """Test validation fails without host."""
        monkeypatch.setenv("SMTP_HOST", "")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        config = SMTPConfig.from_env()
        with pytest.raises(ValueError, match="SMTP_HOST"):
            config.validate()

    def test_validate_missing_from(self, monkeypatch):
        """Test validation fails without from_email."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "")

        config = SMTPConfig.from_env()
        with pytest.raises(ValueError, match="SMTP_FROM"):
            config.validate()


class TestMailer:
    """Test Mailer service."""

    def test_init(self, monkeypatch):
        """Test mailer initialization."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        config = SMTPConfig.from_env()
        mailer = Mailer(config)

        assert mailer.config == config

    def test_init_from_env(self, monkeypatch):
        """Test mailer initializes from env by default."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        mailer = Mailer()
        assert mailer.config.host == "smtp.example.com"

    @patch('agent_os.auth.mailer.smtplib.SMTP')
    def test_send_text_success(self, mock_smtp, monkeypatch):
        """Test sending plain text email successfully."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        mailer = Mailer()
        result = mailer.send_text(
            to="recipient@example.com",
            subject="Test Subject",
            content="Test content"
        )

        assert result.success is True
        assert result.retry_count == 0
        assert result.error is None

        # Verify SMTP calls
        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()

    @patch('agent_os.auth.mailer.smtplib.SMTP')
    def test_send_html_success(self, mock_smtp, monkeypatch):
        """Test sending HTML email successfully."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        mailer = Mailer()
        result = mailer.send_html(
            to="recipient@example.com",
            subject="HTML Test",
            html="<h1>Test HTML</h1>"
        )

        assert result.success is True

    @patch('agent_os.auth.mailer.smtplib.SMTP')
    def test_send_with_auth(self, mock_smtp, monkeypatch):
        """Test sending with authentication."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "password")

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        mailer = Mailer()
        result = mailer.send_text(
            to="recipient@example.com",
            subject="Auth Test",
            content="Test"
        )

        assert result.success is True
        mock_server.login.assert_called_once_with(
            "user@example.com",
            "password"
        )

    @patch('agent_os.auth.mailer.smtplib.SMTP')
    def test_send_without_tls(self, mock_smtp, monkeypatch):
        """Test sending without TLS."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
        monkeypatch.setenv("SMTP_USE_TLS", "false")

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        mailer = Mailer()
        result = mailer.send_text(
            to="recipient@example.com",
            subject="No TLS Test",
            content="Test"
        )

        assert result.success is True
        mock_server.starttls.assert_not_called()

    @patch('agent_os.auth.mailer.smtplib.SMTP')
    def test_send_failure(self, mock_smtp, monkeypatch):
        """Test handling send failure."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        mock_server = MagicMock()
        mock_server.sendmail.side_effect = Exception("SMTP error")
        mock_smtp.return_value.__enter__.return_value = mock_server

        mailer = Mailer()
        result = mailer.send_text(
            to="recipient@example.com",
            subject="Fail Test",
            content="Test"
        )

        assert result.success is False
        assert "SMTP error" in result.error

    @patch('agent_os.auth.mailer.smtplib.SMTP')
    def test_send_template_success(self, mock_smtp, monkeypatch, tmp_path):
        """Test sending email from template."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        # Create template file
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "test.html"
        template_file.write_text("Hello {{ name }}")

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        mailer = Mailer()

        # Patch template path
        with patch('agent_os.auth.mailer.Path') as mock_path:
            mock_path.return_value.__truediv__ = mock_path
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__enter__.return_value.read_text.return_value = "Hello {{ name }}"

            result = mailer.send_template(
                to="recipient@example.com",
                subject="Template Test",
                template_name="test.html",
                context={"name": "World"}
            )

        assert result.success is True


class TestSendResult:
    """Test SendResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = SendResult(
            success=True,
            message_id="msg-123",
            retry_count=0
        )

        assert result.success is True
        assert result.message_id == "msg-123"
        assert result.retry_count == 0
        assert result.error is None

    def test_failure_result(self):
        """Test failed result."""
        result = SendResult(
            success=False,
            error="Connection failed",
            retry_count=2
        )

        assert result.success is False
        assert result.error == "Connection failed"
        assert result.retry_count == 2
        assert result.message_id is None


class TestGlobalMailer:
    """Test global mailer instance."""

    def test_get_mailer_singleton(self, monkeypatch):
        """Test get_mailer returns singleton."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        mailer1 = get_mailer()
        mailer2 = get_mailer()

        # Should return same instance
        assert mailer1 is mailer2

    def test_get_mailer_creates_once(self, monkeypatch):
        """Test mailer is created only once."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

        # Patch to track creation
        with patch('agent_os.auth.mailer.Mailer') as mock_mailer_class:
            mock_instance = MagicMock()
            mock_mailer_class.return_value = mock_instance

            mailer1 = get_mailer()
            mailer2 = get_mailer()

            # Should create only once
            mock_mailer_class.assert_called_once()
