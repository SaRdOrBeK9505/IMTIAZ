"""QR Code Service — centralized QR generation and verification."""

import qrcode
from io import BytesIO
from django.core.files import File
from django.core.cache import cache
from django.conf import settings
import time
import hmac
import hashlib


class QRCodeService:
    """Centralized QR code generation and verification service."""
    
    @staticmethod
    def generate_qr_code(payload: str, size: int = 10) -> BytesIO:
        """
        Generate QR code image from payload.
        
        Args:
            payload: Data to encode in QR
            size: Box size (default 10)
        
        Returns:
            BytesIO containing PNG image
        """
        qr = qrcode.QRCode(
            version=1,
            box_size=size,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        return img_io
    
    @staticmethod
    def generate_signed_payload(entity_id: int, user_id: int, entity_type: str = 'bonus') -> str:
        """
        Generate signed QR payload with HMAC signature.
        
        Args:
            entity_id: ID of the entity (bonus, booking, etc.)
            user_id: User ID
            entity_type: Type of entity (bonus, booking, etc.)
        
        Returns:
            Signed payload string: {entity_type}:{entity_id}:{user_id}:{timestamp}:{signature}
        """
        timestamp = int(time.time())
        payload = f"{entity_type}:{entity_id}:{user_id}:{timestamp}"
        
        secret = getattr(settings, 'QR_SECRET', 'imtiaz-secret-key')
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:8]
        
        return f"{payload}:{signature}"
    
    @staticmethod
    def verify_signed_payload(qr_code: str) -> dict:
        """
        Verify signed QR payload.
        
        Args:
            qr_code: QR code string to verify
        
        Returns:
            dict with 'valid' (bool) and 'data' (dict) if valid
        """
        try:
            parts = qr_code.split(':')
            if len(parts) != 5:
                return {'valid': False, 'error': 'Invalid format'}
            
            entity_type, entity_id, user_id, timestamp, signature = parts
            
            # Verify signature
            payload = ':'.join(parts[:4])
            secret = getattr(settings, 'QR_SECRET', 'imtiaz-secret-key')
            expected_sig = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()[:8]
            
            if signature != expected_sig:
                return {'valid': False, 'error': 'Invalid signature'}
            
            # Check timestamp (QR codes expire after 24 hours)
            qr_time = int(timestamp)
            current_time = int(time.time())
            if current_time - qr_time > 86400:  # 24 hours
                return {'valid': False, 'error': 'QR code expired'}
            
            return {
                'valid': True,
                'data': {
                    'entity_type': entity_type,
                    'entity_id': int(entity_id),
                    'user_id': int(user_id),
                    'timestamp': qr_time,
                }
            }
            
        except (ValueError, IndexError):
            return {'valid': False, 'error': 'Invalid QR code format'}
    
    @staticmethod
    def cache_qr_verification(qr_code: str, result: dict, timeout: int = 300) -> None:
        """
        Cache QR verification result to prevent replay attacks.
        
        Args:
            qr_code: QR code string
            result: Verification result dict
            timeout: Cache timeout in seconds (default 5 minutes)
        """
        cache_key = f"qr_verification:{qr_code}"
        cache.set(cache_key, result, timeout=timeout)
    
    @staticmethod
    def get_cached_verification(qr_code: str) -> dict | None:
        """
        Get cached QR verification result.
        
        Args:
            qr_code: QR code string
        
        Returns:
            Cached result dict or None if not cached
        """
        cache_key = f"qr_verification:{qr_code}"
        return cache.get(cache_key)
    
    @staticmethod
    def generate_bonus_qr(user_bonus) -> str:
        """
        Generate QR code for UserBonus entity.
        
        Args:
            user_bonus: UserBonus instance
        
        Returns:
            QR code string
        """
        payload = QRCodeService.generate_signed_payload(
            entity_id=user_bonus.id,
            user_id=user_bonus.user.id,
            entity_type='bonus'
        )
        
        # Generate QR image
        img_io = QRCodeService.generate_qr_code(payload)
        filename = f"qr_bonus_{user_bonus.id}_{user_bonus.user.id}.png"
        user_bonus.qr_code_image.save(filename, File(img_io), save=False)
        user_bonus.qr_code = payload
        user_bonus.save(update_fields=['qr_code', 'qr_code_image', 'updated_at'])
        
        return payload
