"""Static contract checks for nginx reverse proxy + HTTPS configuration.

PRD10 §11.3 / todo-tasks.md §11.3 (Owner: my-mcp-20 @ 2026-05-06).

These tests validate the nginx config files at rest — they do NOT actually
boot nginx (which would require docker). They guard the high-intent
behaviours so a future edit cannot silently regress:

* HTTP server (port 80) exists with ACME passthrough.
* HTTPS server (port 443) exists with HSTS.
* Shared `locations.conf.inc` is referenced from both server blocks.
* Locations file declares: SSE non-buffering, WebSocket upgrade,
  hashed-asset immutable cache, HTML no-cache, security headers,
  rate-limit zones (auth/ai/search), health/ready endpoints.
* docker-compose nginx service mounts the shared include + ssl dir +
  acme-webroot volume + entrypoint script + healthcheck.
* docs/11-deployment/https.md exists with the curl self-check section.

Why static contract: docker isn't always installed in CI; nginx -t needs
real nginx + the resolver host; the keys we want stable are the file
content & compose mounts, not the running daemon.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
NGINX_DIR = REPO_ROOT / "docker" / "nginx"
COMPOSE_FILE = REPO_ROOT / "docker-compose.prd10.yml"
HTTPS_DOC = REPO_ROOT / "docs" / "11-deployment" / "https.md"


# ---------------------------------------------------------------------------
# Files exist
# ---------------------------------------------------------------------------


def test_nginx_config_files_exist() -> None:
    """All three nginx config files ship with the repo."""
    assert (NGINX_DIR / "mydow.conf").is_file()
    assert (NGINX_DIR / "locations.conf.inc").is_file()
    assert (NGINX_DIR / "entrypoint.sh").is_file()


def test_https_doc_exists_with_self_check() -> None:
    """docs/11-deployment/https.md contains the upline 8-step self-check."""
    assert HTTPS_DOC.is_file()
    body = HTTPS_DOC.read_text(encoding="utf-8")
    # Headline self-check section
    assert "上线前自检清单" in body
    # Specific commands engineers must be able to grep for
    for fragment in (
        "openssl s_client -connect",
        "Strict-Transport",
        "Cache-Control",
        "/api/v1/notifications/stream",
        "certbot renew",
    ):
        assert fragment in body, f"https.md missing required fragment: {fragment!r}"


# ---------------------------------------------------------------------------
# mydow.conf — server blocks
# ---------------------------------------------------------------------------


def test_mydow_conf_has_http_and_https_servers() -> None:
    """mydow.conf must define both :80 and :443 server blocks."""
    body = (NGINX_DIR / "mydow.conf").read_text(encoding="utf-8")
    # HTTP server: port 80 + ACME challenge passthrough
    assert "listen 80" in body
    assert "/.well-known/acme-challenge/" in body
    # HTTPS server: port 443 + ssl + HSTS
    assert "listen 443 ssl" in body
    assert "ssl_certificate" in body
    assert "ssl_certificate_key" in body
    assert "Strict-Transport-Security" in body
    # Both servers must include the shared locations file
    assert body.count("include /etc/nginx/conf.d/locations.conf.inc") >= 2


def test_mydow_conf_has_modern_tls_config() -> None:
    """HTTPS block uses TLS 1.2+1.3 and OCSP stapling."""
    body = (NGINX_DIR / "mydow.conf").read_text(encoding="utf-8")
    assert "ssl_protocols" in body
    assert "TLSv1.2" in body
    assert "TLSv1.3" in body
    assert "ssl_stapling" in body


# ---------------------------------------------------------------------------
# locations.conf.inc — shared behaviour
# ---------------------------------------------------------------------------


def test_locations_inc_security_headers() -> None:
    """Shared locations file declares the canonical security headers."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
        "Content-Security-Policy",
    ):
        assert header in body, f"missing security header: {header}"


def test_locations_inc_sse_no_buffering() -> None:
    """SSE endpoints must opt out of nginx buffering and have 24h timeout."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    # The SSE location pattern matches PRD10 SSE endpoints
    assert "/api/v1/(notifications/stream" in body
    assert "/messages/stream" in body or "/messages?/[^/]+/stream" in body
    # SSE-critical settings
    assert "proxy_buffering    off" in body or "proxy_buffering off" in body
    assert "proxy_read_timeout 24h" in body
    assert "X-Accel-Buffering" in body


def test_locations_inc_websocket_upgrade() -> None:
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    assert "Upgrade $http_upgrade" in body
    assert "Connection \"upgrade\"" in body


def test_locations_inc_immutable_cache_for_hashed_assets() -> None:
    """Hashed assets get 1-year immutable cache; HTML is no-store."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    assert "max-age=31536000, immutable" in body
    # HTML / JSON should be no-store (so demo HTML changes propagate fast)
    assert "no-store" in body and "must-revalidate" in body


def test_locations_inc_rate_limit_zones() -> None:
    """Rate-limit zones for auth / AI / search exist with sane limits."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    assert "auth_zone" in body
    assert "ai_zone" in body
    assert "search_zone" in body
    # The zones are used in actual location blocks
    assert "limit_req zone=auth_zone" in body
    assert "limit_req zone=ai_zone" in body
    assert "limit_req zone=search_zone" in body


def test_locations_inc_health_and_ready_endpoints() -> None:
    """nginx forwards /health and /ready without access logs."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    assert "location = /health" in body
    assert "location = /ready" in body
    # access_log off near these endpoints
    health_block_start = body.find("location = /health")
    health_block_end = body.find("}", health_block_start)
    assert "access_log off" in body[health_block_start:health_block_end]


# ---------------------------------------------------------------------------
# entrypoint.sh — graceful no-cert fallback
# ---------------------------------------------------------------------------


def test_entrypoint_handles_missing_cert() -> None:
    """entrypoint.sh detects missing TLS cert and runs in HTTP-only mode."""
    body = (NGINX_DIR / "entrypoint.sh").read_text(encoding="utf-8")
    assert body.startswith("#!/bin/sh")
    # Cert presence check
    assert "fullchain.pem" in body
    assert "privkey.pem" in body
    # Validates config before exec
    assert "nginx -t" in body
    # Falls back to HTTP-only when no cert
    assert "HTTPS_ENABLED=0" in body


# ---------------------------------------------------------------------------
# docker-compose nginx service
# ---------------------------------------------------------------------------


def test_compose_nginx_mounts_include_and_acme() -> None:
    """compose nginx service mounts the new include + entrypoint + acme volume."""
    raw = COMPOSE_FILE.read_text(encoding="utf-8")
    spec = yaml.safe_load(raw)
    assert "services" in spec
    nginx = spec["services"].get("nginx")
    assert nginx is not None, "compose missing nginx service"

    volumes = " ".join(nginx.get("volumes") or [])
    assert "locations.conf.inc" in volumes, "nginx must mount locations.conf.inc"
    assert "entrypoint.sh" in volumes, "nginx must mount entrypoint.sh"
    assert "ssl:/etc/nginx/ssl" in volumes, "nginx must mount ssl/ dir"
    assert "nginx-acme:/var/www/certbot" in volumes, "nginx must mount acme volume"

    # Healthcheck wired
    assert nginx.get("healthcheck") is not None

    # Profile gating
    assert "nginx" in (nginx.get("profiles") or [])

    # Top-level volumes contains nginx-acme
    assert "nginx-acme" in (spec.get("volumes") or {})


def test_compose_nginx_uses_entrypoint_script() -> None:
    """nginx service overrides entrypoint to call our TLS-aware script."""
    spec = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    nginx = spec["services"]["nginx"]
    # entrypoint can be a string or list; allow both
    ep = nginx.get("entrypoint")
    assert ep is not None
    if isinstance(ep, list):
        ep_text = " ".join(ep)
    else:
        ep_text = str(ep)
    assert "40-mydow-tls.sh" in ep_text


# ---------------------------------------------------------------------------
# Forward-compat: PRD10 §11 deployment readiness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path_fragment",
    [
        "/api/v1/notifications/stream",
        "/api/v1/auth/login",
        "/api/v1/search",
    ],
)
def test_locations_inc_covers_prd10_critical_paths(path_fragment: str) -> None:
    """Every PRD10 critical proxy path is referenced in locations.conf.inc."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    # Substring search; the location regexes contain the path stem
    assert path_fragment.split("/", 4)[3] in body or path_fragment in body, (
        f"locations.conf.inc missing reference to {path_fragment}"
    )


def test_locations_inc_proxies_mydow_shell() -> None:
    """Acceptance Gate §14.9: nginx must forward /mydow/* (and /) to upstream app."""
    body = (NGINX_DIR / "locations.conf.inc").read_text(encoding="utf-8")
    assert "mydow" in body
    assert "location /" in body
    assert "proxy_pass http://mydow_app" in body


DOCKER_DOC = REPO_ROOT / "docs" / "11-deployment" / "docker.md"


def test_docker_md_documents_acceptance_gate_14_9() -> None:
    """Runbook must spell the public HTTPS /mydow/ smoke path (todo §14.9)."""
    text = DOCKER_DOC.read_text(encoding="utf-8")
    for fragment in (
        "Acceptance Gate §14.9",
        "https://demo.example.com/mydow/",
        "locations.conf.inc",
        "BASE_URL",
        "CORS_ORIGINS",
        "--profile nginx",
    ):
        assert fragment in text, f"docker.md missing §14.9 fragment {fragment!r}"
