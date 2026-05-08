"""PRD10 §8.3 / §8.9 — pluggable upload presign backends.

`POST /api/v1/uploads/presign` returns a contract that lets the SPA / SDK
upload bytes directly to wherever blobs really live. V1 ships a
`local` backend that points the client back at our own
`PUT /api/v1/uploads/local/{upload_id}` endpoint; production deploys can
swap to an `s3` backend (boto3 generates real presigned URLs) without any
client-side changes.

Public contract (every backend MUST return these exact keys so the SPA
contract stays stable):

```json
{
  "upload_id":     "<uuid>",
  "upload_url":    "<absolute URL the client PUT/POSTs to>",
  "upload_method": "PUT" | "POST",
  "file_url":      "<absolute URL the *server* will fetch the bytes from later>",
  "expires_in":    900,                 // seconds the URL is valid for
  "expires_at":    "2026-05-07T10:30:00Z",
  "max_size_bytes": 1073741824,         // server-enforced upper bound
  "headers":        { "x-amz-acl": "private", ... },  // headers client MUST send
  "fields":         { "key": "...", ... },             // optional POST form fields
  "backend":        "local" | "s3",
  "bucket":         "<bucket name when s3>"            // optional, debug-only
}
```

`headers` is what the client must echo back in the upload PUT/POST.
`fields` is only populated when the backend uses S3 POST policies; for
plain PUT it is `{}`.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PresignResult:
    """Outcome of a successful :meth:`PresignBackend.presign` call.

    All fields are JSON-serializable; the route handler turns this into a
    PRD10 success envelope as-is.
    """

    upload_id: uuid.UUID
    upload_url: str
    upload_method: Literal["PUT", "POST"]
    file_url: str
    expires_in: int
    expires_at: datetime
    max_size_bytes: int
    backend: str
    headers: dict[str, str] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    bucket: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "upload_id": str(self.upload_id),
            "upload_url": self.upload_url,
            "upload_method": self.upload_method,
            "file_url": self.file_url,
            "expires_in": int(self.expires_in),
            "expires_at": self.expires_at.astimezone(UTC).isoformat(),
            "max_size_bytes": int(self.max_size_bytes),
            "headers": dict(self.headers),
            "fields": dict(self.fields),
            "backend": self.backend,
            "bucket": self.bucket,
        }


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _read_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def get_default_expires_in_seconds() -> int:
    """How long every presigned URL stays valid by default (seconds)."""

    return _read_int_env("AGENTOS_UPLOAD_PRESIGN_EXPIRES_SECONDS", 900)


def get_default_max_size_bytes() -> int:
    """Server-side upper bound on a single upload (bytes)."""

    return _read_int_env("AGENTOS_UPLOAD_MAX_SIZE_BYTES", 1024 * 1024 * 1024)  # 1 GiB


def get_configured_backend_name() -> str:
    """Return ``"local"`` or ``"s3"`` based on env (case-insensitive)."""

    raw = os.getenv("AGENTOS_UPLOAD_BACKEND", "").strip().lower()
    if raw in ("s3", "r2", "minio", "oss"):
        return "s3"
    return "local"


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------


class PresignBackend:
    """Abstract presign backend.

    Implementations must:

    * Validate the request (size / mime) and raise `ValueError` on bad
      input — the route handler translates that to a PRD10 envelope 400.
    * Return a :class:`PresignResult` whose ``upload_url`` and ``file_url``
      are absolute and reachable by the client.

    Stateless by design: each call is independent, no per-instance buckets.
    """

    name: str = "abstract"

    def presign(
        self,
        *,
        user_id: uuid.UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        base_url: str,
        expires_in: int | None = None,
    ) -> PresignResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Local backend (default for V1)
# ---------------------------------------------------------------------------


class LocalPresignBackend(PresignBackend):
    """Hand back a URL that points at our own ``/api/v1/uploads/local/*``.

    Production deploys keep this for environments where the FastAPI app
    *is* the storage backend (single-node demo, on-prem appliance).
    """

    name = "local"

    def presign(
        self,
        *,
        user_id: uuid.UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        base_url: str,
        expires_in: int | None = None,
    ) -> PresignResult:
        upload_id = uuid.uuid4()
        ttl = max(60, expires_in or get_default_expires_in_seconds())
        max_size = get_default_max_size_bytes()
        if size_bytes > max_size:
            raise ValueError(
                f"size_bytes {size_bytes} exceeds upload cap {max_size}"
            )

        clean_base = base_url.rstrip("/")
        upload_url = f"{clean_base}/api/v1/uploads/local/{upload_id}"
        file_url = f"{clean_base}/api/v1/uploads/local/{upload_id}/raw"

        return PresignResult(
            upload_id=upload_id,
            upload_url=upload_url,
            upload_method="PUT",
            file_url=file_url,
            expires_in=ttl,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
            max_size_bytes=max_size,
            backend=self.name,
            headers={
                "Content-Type": mime_type,
                "X-Filename": filename,
            },
            fields={},
            bucket=None,
        )


# ---------------------------------------------------------------------------
# S3 / R2 backend (optional — requires boto3)
# ---------------------------------------------------------------------------


class S3PresignBackend(PresignBackend):
    """Generate an S3-compatible PUT presigned URL (S3 / R2 / MinIO / OSS).

    Requires ``boto3`` to be importable. Lazy-imported so deployments that
    don't use S3 don't need to install it.

    Environment:
        ``AWS_S3_BUCKET`` — destination bucket name (required)
        ``AWS_S3_REGION`` — region for SigV4 signing (default: us-east-1)
        ``AWS_S3_ENDPOINT_URL`` — non-AWS endpoint (R2 / MinIO / OSS)
        ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` — credentials
            (boto3 also reads ``~/.aws/credentials`` and IAM role profiles)
        ``AGENTOS_UPLOAD_S3_KEY_PREFIX`` — optional prefix prepended to
            every object key; default: ``mydow-uploads/``
        ``AGENTOS_UPLOAD_S3_ACL`` — default ``private``
        ``AGENTOS_UPLOAD_S3_PUBLIC_READ_BASE`` — when objects are publicly
            readable via a CDN, this is the URL prefix used as ``file_url``
            (saves one /api/v1/uploads round-trip). Optional.
    """

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        public_read_base: str | None = None,
        key_prefix: str | None = None,
        acl: str | None = None,
    ) -> None:
        self._bucket = bucket or os.getenv("AWS_S3_BUCKET", "").strip() or None
        self._region = region or os.getenv("AWS_S3_REGION", "us-east-1").strip()
        self._endpoint_url = (
            endpoint_url
            or os.getenv("AWS_S3_ENDPOINT_URL", "").strip()
            or None
        )
        self._public_read_base = (
            public_read_base
            or os.getenv("AGENTOS_UPLOAD_S3_PUBLIC_READ_BASE", "").strip()
            or None
        )
        self._key_prefix = (
            key_prefix
            or os.getenv("AGENTOS_UPLOAD_S3_KEY_PREFIX", "mydow-uploads/").strip()
        )
        if self._key_prefix and not self._key_prefix.endswith("/"):
            self._key_prefix = f"{self._key_prefix}/"
        self._acl = acl or os.getenv("AGENTOS_UPLOAD_S3_ACL", "private").strip()

    @property
    def bucket(self) -> str | None:
        return self._bucket

    def _ensure_client(self):
        try:
            import boto3  # noqa: F401  (boto3 is intentionally optional)
        except ImportError as exc:  # pragma: no cover - covered by env-skip
            raise RuntimeError(
                "S3 presign backend requires boto3. Install with"
                " `pip install boto3` or set AGENTOS_UPLOAD_BACKEND=local."
            ) from exc

        return boto3.client(  # noqa: F821 - guarded above
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
        )

    def _build_object_key(self, *, user_id: uuid.UUID, upload_id: uuid.UUID, filename: str) -> str:
        # Sanitize filename — S3 allows almost everything but slashes break
        # our prefix scheme. We keep ASCII letters/digits/dot/dash/underscore
        # and replace the rest with '_'. Worst-case the original name is
        # also recorded on the Source row.
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        if not safe:
            safe = "upload.bin"
        return f"{self._key_prefix}{user_id}/{upload_id}/{safe}"

    def presign(
        self,
        *,
        user_id: uuid.UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        base_url: str,
        expires_in: int | None = None,
    ) -> PresignResult:
        if not self._bucket:
            raise RuntimeError(
                "S3 presign backend requires AWS_S3_BUCKET to be set"
            )

        max_size = get_default_max_size_bytes()
        if size_bytes > max_size:
            raise ValueError(
                f"size_bytes {size_bytes} exceeds upload cap {max_size}"
            )

        ttl = max(60, expires_in or get_default_expires_in_seconds())
        upload_id = uuid.uuid4()
        key = self._build_object_key(
            user_id=user_id, upload_id=upload_id, filename=filename
        )

        client = self._ensure_client()
        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "ContentType": mime_type,
        }
        if self._acl:
            params["ACL"] = self._acl

        upload_url = client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=ttl,
        )

        if self._public_read_base:
            file_url = f"{self._public_read_base.rstrip('/')}/{key}"
        elif self._endpoint_url:
            file_url = f"{self._endpoint_url.rstrip('/')}/{self._bucket}/{key}"
        else:
            file_url = (
                f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
            )

        return PresignResult(
            upload_id=upload_id,
            upload_url=upload_url,
            upload_method="PUT",
            file_url=file_url,
            expires_in=ttl,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
            max_size_bytes=max_size,
            backend=self.name,
            headers={"Content-Type": mime_type},
            fields={},
            bucket=self._bucket,
        )


# ---------------------------------------------------------------------------
# Singleton + factory
# ---------------------------------------------------------------------------


_default_backend: PresignBackend | None = None


def get_default_backend() -> PresignBackend:
    """Return a process-wide presign backend chosen from env.

    Memoized: the env is read once at first call. Tests can call
    :func:`set_default_backend` to override / reset between tests.
    """

    global _default_backend
    if _default_backend is None:
        _default_backend = build_backend_from_env()
    return _default_backend


def set_default_backend(backend: PresignBackend | None) -> None:
    """Replace the singleton (test helper). ``None`` resets to env default."""

    global _default_backend
    _default_backend = backend


def build_backend_from_env() -> PresignBackend:
    """Construct a backend matching the current env (no memoization)."""

    name = get_configured_backend_name()
    if name == "s3":
        return S3PresignBackend()
    return LocalPresignBackend()
