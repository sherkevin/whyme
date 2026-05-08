"""Filesystem-backed upload storage helper.

Production deployments are expected to swap this for an S3/R2/OSS adapter;
the API surface (``write_bytes`` / ``open_stream`` / ``relative_path``) is
deliberately small so that swap is mechanical.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DEFAULT_BASE = Path(os.getenv("PRD10_UPLOADS_BASE", "data/uploads"))
_DEFAULT_MULTIPART_BASE = Path(
    os.getenv("PRD10_UPLOADS_MULTIPART_BASE", "data/uploads/multipart")
)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fa5]+")


def _multipart_chunk_size_default() -> int:
    """Default chunk size in bytes (env-overridable, hard-clamped to safe range).

    PRD10 §16.3 risk: too small → many tiny PUTs hammer the server; too
    large → defeats the purpose. 5 MiB matches the S3 multipart minimum so
    a future swap to S3/R2 can reuse the same client code.
    """

    raw = os.getenv("AGENTOS_UPLOAD_MULTIPART_CHUNK_SIZE", "").strip()
    if not raw:
        return 5 * 1024 * 1024
    try:
        value = int(raw)
    except ValueError:
        return 5 * 1024 * 1024
    return max(64 * 1024, min(value, 64 * 1024 * 1024))


def _multipart_ttl_seconds_default() -> int:
    """Default TTL for an in-flight multipart session (env-overridable)."""

    raw = os.getenv("AGENTOS_UPLOAD_MULTIPART_TTL_SECONDS", "").strip()
    if not raw:
        return 24 * 60 * 60  # 24h
    try:
        value = int(raw)
    except ValueError:
        return 24 * 60 * 60
    return max(60, min(value, 7 * 24 * 60 * 60))


def _multipart_max_total_size_default() -> int:
    """Hard cap on the total upload size (env-overridable, default 2 GiB)."""

    raw = os.getenv("AGENTOS_UPLOAD_MULTIPART_MAX_BYTES", "").strip()
    if not raw:
        return 2 * 1024 * 1024 * 1024
    try:
        value = int(raw)
    except ValueError:
        return 2 * 1024 * 1024 * 1024
    return max(1024 * 1024, value)


@dataclass(frozen=True)
class StoredUpload:
    """Result of a successful ``write_bytes`` call."""

    filename: str
    relative_path: str
    absolute_path: Path
    size_bytes: int


class UploadStorage:
    """Tiny filesystem-backed object store used by V1.

    Files are organized under ``<base>/<user_id>/<upload_id>/<filename>``.
    Filenames are sanitized so a hostile client can't escape the upload root.
    """

    def __init__(self, base: Path | str | None = None) -> None:
        self._base = Path(base) if base is not None else _DEFAULT_BASE

    @property
    def base(self) -> Path:
        return self._base

    # ---------------- write ----------------

    def write_bytes(
        self,
        *,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        filename: str,
        data: bytes,
    ) -> StoredUpload:
        safe_name = self._safe_filename(filename)
        target_dir = self._base / str(user_id) / str(upload_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_name
        target_path.write_bytes(data)

        return StoredUpload(
            filename=safe_name,
            relative_path=str(target_path.relative_to(self._base)),
            absolute_path=target_path,
            size_bytes=len(data),
        )

    # ---------------- read ----------------

    def open_stream(
        self,
        *,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
    ) -> tuple[Path, Iterator[bytes]] | None:
        """Return the resolved on-disk path and a streaming iterator.

        Returns ``None`` when the upload directory is missing or empty.
        """

        upload_dir = self._base / str(user_id) / str(upload_id)
        if not upload_dir.exists() or not upload_dir.is_dir():
            return None
        files = [p for p in upload_dir.iterdir() if p.is_file()]
        if not files:
            return None
        # Pick the newest file in the directory; uploads typically only
        # contain a single artifact but we tolerate retries by preferring
        # the most recently written file.
        path = max(files, key=lambda p: p.stat().st_mtime)
        return path, _stream_file(path)

    # ---------------- helpers ----------------

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = _SAFE_NAME.sub("_", name).strip("._-")
        return cleaned or "upload.bin"


def _stream_file(path: Path, *, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            buf = handle.read(chunk_size)
            if not buf:
                break
            yield buf


_default_storage: UploadStorage | None = None


def get_default_storage() -> UploadStorage:
    """Return a process-wide singleton storage instance."""

    global _default_storage
    if _default_storage is None:
        _default_storage = UploadStorage()
    return _default_storage


def set_default_storage(storage: UploadStorage | None) -> None:
    """Replace the singleton (used by tests for isolated temp directories)."""

    global _default_storage
    _default_storage = storage


# ===========================================================================
# Multipart upload (PRD10 §12.5 / §16.3)
# ===========================================================================


_META_FILENAME = "meta.json"
_CHUNK_SUBDIR = "chunks"
_CHUNK_TEMPLATE = "{index:08d}.part"
_META_VERSION = 1


@dataclass
class ChunkInfo:
    """One uploaded chunk's metadata as returned to the client."""

    index: int
    size_bytes: int
    sha256: str


@dataclass
class MultipartSession:
    """Persisted state of an in-flight multipart upload session.

    Kept on disk as ``meta.json`` alongside the chunk files so the session
    survives process restarts (operators can resume an upload after a deploy).
    Mutable: ``chunks`` is updated by :meth:`MultipartStorage.write_chunk`.
    """

    upload_id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    mime_type: str | None
    total_size_bytes: int
    chunk_size: int
    total_chunks: int
    created_at: datetime
    expires_at: datetime
    chunks: dict[int, ChunkInfo] = field(default_factory=dict)
    completed_at: datetime | None = None

    # ---------------- persistence ----------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _META_VERSION,
            "upload_id": str(self.upload_id),
            "user_id": str(self.user_id),
            "filename": self.filename,
            "mime_type": self.mime_type,
            "total_size_bytes": self.total_size_bytes,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "chunks": {
                str(idx): {
                    "index": c.index,
                    "size_bytes": c.size_bytes,
                    "sha256": c.sha256,
                }
                for idx, c in sorted(self.chunks.items())
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MultipartSession:
        chunks_raw = raw.get("chunks") or {}
        chunks: dict[int, ChunkInfo] = {}
        for key, value in chunks_raw.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(value, dict):
                continue
            chunks[idx] = ChunkInfo(
                index=idx,
                size_bytes=int(value.get("size_bytes") or 0),
                sha256=str(value.get("sha256") or ""),
            )

        return cls(
            upload_id=uuid.UUID(str(raw["upload_id"])),
            user_id=uuid.UUID(str(raw["user_id"])),
            filename=str(raw.get("filename") or "upload.bin"),
            mime_type=(raw.get("mime_type") or None),
            total_size_bytes=int(raw.get("total_size_bytes") or 0),
            chunk_size=int(raw.get("chunk_size") or _multipart_chunk_size_default()),
            total_chunks=int(raw.get("total_chunks") or 0),
            created_at=_parse_iso(raw.get("created_at")),
            expires_at=_parse_iso(raw.get("expires_at")),
            chunks=chunks,
            completed_at=(
                _parse_iso(raw["completed_at"])
                if raw.get("completed_at")
                else None
            ),
        )

    # ---------------- query ----------------

    def is_expired(self, now: datetime | None = None) -> bool:
        ref = now or datetime.now(UTC)
        return ref >= self.expires_at

    def is_complete(self) -> bool:
        if self.total_chunks <= 0:
            return False
        return len(self.chunks) >= self.total_chunks

    def received_indices(self) -> list[int]:
        return sorted(self.chunks.keys())

    def missing_indices(self) -> list[int]:
        if self.total_chunks <= 0:
            return []
        seen = set(self.chunks.keys())
        return [i for i in range(self.total_chunks) if i not in seen]


class MultipartUploadError(ValueError):
    """Raised by :class:`MultipartStorage` for caller-recoverable problems."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class MultipartStorage:
    """Filesystem-backed multipart upload registry.

    Layout::

        <multipart_base>/<user_id>/<upload_id>/
            meta.json
            chunks/
                00000000.part
                00000001.part
                ...

    On :meth:`assemble` the chunks are concatenated in order and written via
    the supplied :class:`UploadStorage`; the multipart session directory is
    then deleted. On :meth:`cancel` the session directory is deleted without
    materialising a final file.
    """

    def __init__(
        self,
        base: Path | str | None = None,
        *,
        chunk_size: int | None = None,
        ttl_seconds: int | None = None,
        max_total_size_bytes: int | None = None,
    ) -> None:
        self._base = Path(base) if base is not None else _DEFAULT_MULTIPART_BASE
        self._chunk_size = chunk_size or _multipart_chunk_size_default()
        self._ttl_seconds = ttl_seconds or _multipart_ttl_seconds_default()
        self._max_total_size = (
            max_total_size_bytes or _multipart_max_total_size_default()
        )

    @property
    def base(self) -> Path:
        return self._base

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    @property
    def max_total_size_bytes(self) -> int:
        return self._max_total_size

    # ---------------- session lifecycle ----------------

    def init_session(
        self,
        *,
        user_id: uuid.UUID,
        upload_id: uuid.UUID | None,
        filename: str,
        total_size_bytes: int,
        mime_type: str | None = None,
        chunk_size: int | None = None,
    ) -> MultipartSession:
        if total_size_bytes <= 0:
            raise MultipartUploadError(
                "VALIDATION_ERROR",
                "total_size_bytes must be > 0",
            )
        if total_size_bytes > self._max_total_size:
            raise MultipartUploadError(
                "VALIDATION_ERROR",
                (
                    "total_size_bytes exceeds the multipart cap"
                    f" ({self._max_total_size} bytes)"
                ),
            )

        chunk = chunk_size or self._chunk_size
        if chunk <= 0:
            raise MultipartUploadError(
                "VALIDATION_ERROR", "chunk_size must be > 0"
            )

        upload = upload_id or uuid.uuid4()
        total_chunks = (total_size_bytes + chunk - 1) // chunk
        now = datetime.now(UTC)
        session = MultipartSession(
            upload_id=upload,
            user_id=user_id,
            filename=UploadStorage._safe_filename(filename),
            mime_type=mime_type,
            total_size_bytes=total_size_bytes,
            chunk_size=chunk,
            total_chunks=total_chunks,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )
        self._session_dir(user_id, upload).mkdir(parents=True, exist_ok=True)
        (self._session_dir(user_id, upload) / _CHUNK_SUBDIR).mkdir(
            parents=True, exist_ok=True
        )
        self._write_meta(session)
        return session

    def get_session(
        self, *, user_id: uuid.UUID, upload_id: uuid.UUID
    ) -> MultipartSession | None:
        meta_path = self._session_dir(user_id, upload_id) / _META_FILENAME
        if not meta_path.exists():
            return None
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        try:
            return MultipartSession.from_dict(raw)
        except (KeyError, ValueError):
            return None

    def write_chunk(
        self,
        *,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        chunk_index: int,
        data: bytes,
    ) -> ChunkInfo:
        session = self.get_session(user_id=user_id, upload_id=upload_id)
        if session is None:
            raise MultipartUploadError(
                "NOT_FOUND", "Multipart session not found"
            )
        if session.is_expired():
            raise MultipartUploadError(
                "VALIDATION_ERROR", "Multipart session has expired"
            )
        if session.completed_at is not None:
            raise MultipartUploadError(
                "VALIDATION_ERROR", "Multipart session is already completed"
            )
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise MultipartUploadError(
                "VALIDATION_ERROR",
                (
                    f"chunk_index {chunk_index} out of range"
                    f" [0, {session.total_chunks})"
                ),
            )
        if not data:
            raise MultipartUploadError(
                "VALIDATION_ERROR", "Empty chunk body"
            )

        is_last_chunk = chunk_index == session.total_chunks - 1
        if not is_last_chunk and len(data) != session.chunk_size:
            raise MultipartUploadError(
                "VALIDATION_ERROR",
                (
                    f"Chunk size mismatch: expected {session.chunk_size},"
                    f" got {len(data)} for index {chunk_index}"
                ),
            )
        if is_last_chunk:
            expected_last = session.total_size_bytes - session.chunk_size * (
                session.total_chunks - 1
            )
            if len(data) != expected_last:
                raise MultipartUploadError(
                    "VALIDATION_ERROR",
                    (
                        "Last chunk size mismatch:"
                        f" expected {expected_last}, got {len(data)}"
                    ),
                )

        chunk_dir = self._session_dir(user_id, upload_id) / _CHUNK_SUBDIR
        chunk_dir.mkdir(parents=True, exist_ok=True)
        target = chunk_dir / _CHUNK_TEMPLATE.format(index=chunk_index)
        target.write_bytes(data)

        info = ChunkInfo(
            index=chunk_index,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        session.chunks[chunk_index] = info
        self._write_meta(session)
        return info

    def assemble(
        self,
        *,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        target_storage: UploadStorage,
    ) -> tuple[MultipartSession, StoredUpload]:
        session = self.get_session(user_id=user_id, upload_id=upload_id)
        if session is None:
            raise MultipartUploadError(
                "NOT_FOUND", "Multipart session not found"
            )
        if session.is_expired():
            raise MultipartUploadError(
                "VALIDATION_ERROR", "Multipart session has expired"
            )
        if not session.is_complete():
            missing = session.missing_indices()
            raise MultipartUploadError(
                "VALIDATION_ERROR",
                (
                    "Cannot complete: missing chunks"
                    f" {missing[:10]}{'…' if len(missing) > 10 else ''}"
                ),
            )

        # Stream chunks into the final blob via the existing UploadStorage
        # helper so the final file lives in the same layout as a single PUT
        # upload (`<base>/<user_id>/<upload_id>/<filename>`). We avoid
        # loading the whole upload into RAM by appending chunk-by-chunk.
        target_dir = target_storage.base / str(user_id) / str(upload_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / session.filename

        total_written = 0
        chunk_dir = self._session_dir(user_id, upload_id) / _CHUNK_SUBDIR
        with target_path.open("wb") as out:
            for index in range(session.total_chunks):
                chunk_path = chunk_dir / _CHUNK_TEMPLATE.format(index=index)
                if not chunk_path.exists():
                    raise MultipartUploadError(
                        "VALIDATION_ERROR",
                        f"Chunk file missing for index {index}",
                    )
                with chunk_path.open("rb") as src:
                    while True:
                        buf = src.read(64 * 1024)
                        if not buf:
                            break
                        out.write(buf)
                        total_written += len(buf)

        if total_written != session.total_size_bytes:
            # Best-effort cleanup of the partial assembled file so a retry
            # can run cleanly; multipart session left in place so the
            # client can resume / cancel.
            try:
                target_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise MultipartUploadError(
                "VALIDATION_ERROR",
                (
                    "Assembled size mismatch:"
                    f" expected {session.total_size_bytes},"
                    f" got {total_written}"
                ),
            )

        stored = StoredUpload(
            filename=session.filename,
            relative_path=str(target_path.relative_to(target_storage.base)),
            absolute_path=target_path,
            size_bytes=total_written,
        )

        session.completed_at = datetime.now(UTC)
        self._write_meta(session)

        # Tear down the multipart workspace; we keep the assembled file
        # under the regular UploadStorage tree.
        self._purge(user_id, upload_id)

        return session, stored

    def cancel(self, *, user_id: uuid.UUID, upload_id: uuid.UUID) -> bool:
        if not self._session_dir(user_id, upload_id).exists():
            return False
        self._purge(user_id, upload_id)
        return True

    # ---------------- helpers ----------------

    def _session_dir(self, user_id: uuid.UUID, upload_id: uuid.UUID) -> Path:
        return self._base / str(user_id) / str(upload_id)

    def _write_meta(self, session: MultipartSession) -> None:
        path = self._session_dir(session.user_id, session.upload_id) / _META_FILENAME
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)

    def _purge(self, user_id: uuid.UUID, upload_id: uuid.UUID) -> None:
        target = self._session_dir(user_id, upload_id)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


_default_multipart_storage: MultipartStorage | None = None


def get_default_multipart_storage() -> MultipartStorage:
    """Return a process-wide singleton multipart storage instance."""

    global _default_multipart_storage
    if _default_multipart_storage is None:
        _default_multipart_storage = MultipartStorage()
    return _default_multipart_storage


def set_default_multipart_storage(storage: MultipartStorage | None) -> None:
    """Replace the singleton (used by tests for isolated temp directories)."""

    global _default_multipart_storage
    _default_multipart_storage = storage
