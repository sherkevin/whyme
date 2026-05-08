"""Local-disk upload storage for PRD10 V1.

This module hosts the actual byte storage that backs the pseudo presigned URLs
returned by ``POST /api/v1/uploads/presign``. It is intentionally minimal: a
single configurable directory tree, no signing, no virus scanning. Production
deployments are expected to swap in S3/R2/OSS by replacing
``agent_os.uploads.storage.UploadStorage``.
"""

from agent_os.uploads.storage import UploadStorage, get_default_storage

__all__ = ["UploadStorage", "get_default_storage"]
