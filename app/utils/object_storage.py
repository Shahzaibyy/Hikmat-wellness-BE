"""Private object storage for verification documents.

No prior S3/media upload utility existed in this repo. This module provides:
- LocalPrivateStorage (default when S3_BUCKET is unset) — files under PRIVATE_UPLOAD_DIR
- S3PrivateStorage when S3_BUCKET + credentials are configured

Paths follow: hakeem-verification/{temp_id}/{filename}
Stored URLs are opaque keys (not public bucket URLs). Admin views use short-lived signed URLs.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from pathlib import Path
from urllib.parse import quote, unquote

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MiB


class ObjectStorage:
    def upload_private(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        prefix: str = "hakeem-verification",
    ) -> str:
        raise NotImplementedError

    def generate_signed_url(self, stored_url: str, *, expires_in: int = 900) -> str:
        raise NotImplementedError

    def resolve_key(self, stored_url: str) -> str:
        """Normalize stored value to an object key."""
        if stored_url.startswith("private://"):
            return stored_url.removeprefix("private://")
        if stored_url.startswith("s3://"):
            # s3://bucket/key
            without = stored_url.removeprefix("s3://")
            parts = without.split("/", 1)
            return parts[1] if len(parts) == 2 else without
        return stored_url


class LocalPrivateStorage(ObjectStorage):
    def __init__(self, root: Path) -> None:
        self.root = root
        # Do not mkdir here — container cwd may be read-only. Create on first write.

    def _ensure_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Cannot create private upload directory {self.root!s}: {exc}. "
                "Set PRIVATE_UPLOAD_DIR to a writable path (e.g. /tmp/private_uploads)."
            ) from exc

    def upload_private(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        prefix: str = "hakeem-verification",
    ) -> str:
        self._ensure_root()
        ext = ALLOWED_CONTENT_TYPES.get(content_type)
        if ext is None:
            raise ValueError(f"Unsupported content type: {content_type}")
        safe_name = Path(filename).name or f"document{ext}"
        if not safe_name.lower().endswith(ext):
            safe_name = f"{safe_name}{ext}"
        temp_id = uuid.uuid4()
        key = f"{prefix}/{temp_id}/{safe_name}"
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"private://{key}"

    def generate_signed_url(self, stored_url: str, *, expires_in: int = 900) -> str:
        key = self.resolve_key(stored_url)
        exp = int(time.time()) + expires_in
        sig = self._sign(key, exp)
        return f"/api/v1/uploads/signed?key={quote(key, safe='')}&exp={exp}&sig={sig}"

    def verify_signed_request(self, key: str, exp: int, sig: str) -> Path | None:
        if int(time.time()) > exp:
            return None
        expected = self._sign(key, exp)
        if not hmac.compare_digest(expected, sig):
            return None
        path = self.root / key
        if not path.is_file():
            return None
        # Path traversal guard
        try:
            path.resolve().relative_to(self.root.resolve())
        except ValueError:
            return None
        return path

    def _sign(self, key: str, exp: int) -> str:
        msg = f"{key}:{exp}".encode()
        return hmac.new(
            settings.SECRET_KEY.encode(), msg, hashlib.sha256
        ).hexdigest()


class S3PrivateStorage(ObjectStorage):
    def __init__(self) -> None:
        import boto3

        self.bucket = settings.S3_BUCKET
        kwargs: dict = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        self.client = boto3.client("s3", **kwargs)

    def upload_private(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        prefix: str = "hakeem-verification",
    ) -> str:
        ext = ALLOWED_CONTENT_TYPES.get(content_type)
        if ext is None:
            raise ValueError(f"Unsupported content type: {content_type}")
        safe_name = Path(filename).name or f"document{ext}"
        temp_id = uuid.uuid4()
        key = f"{prefix}/{temp_id}/{safe_name}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ACL="private",
        )
        return f"s3://{self.bucket}/{key}"

    def generate_signed_url(self, stored_url: str, *, expires_in: int = 900) -> str:
        key = self.resolve_key(stored_url)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )


_storage: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    global _storage
    if _storage is not None:
        return _storage
    if settings.S3_BUCKET:
        try:
            _storage = S3PrivateStorage()
            logger.info("Using S3 private storage bucket=%s", settings.S3_BUCKET)
            return _storage
        except Exception:
            logger.exception("S3 storage init failed; falling back to local private storage")
    root = Path(settings.PRIVATE_UPLOAD_DIR)
    _storage = LocalPrivateStorage(root)
    logger.info("Using local private storage at %s", root.resolve())
    return _storage
