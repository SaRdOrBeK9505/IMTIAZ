"""DigitalOcean Spaces (S3-compatible) uchun custom storage backendlar."""

from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    """Foydalanuvchi/admin yuklagan barcha media fayllar (rasm, video)."""
    location = 'media'
    default_acl = 'public-read'
    file_overwrite = False
    querystring_auth = False
