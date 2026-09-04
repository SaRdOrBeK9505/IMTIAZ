"""
QR Codes app — biznes logika qatlami.

QRGeneratorService  — QR PNG rasm generatsiya
QRScanService       — QR kod validatsiya va chegirmani hisoblash
QRRedemptionService — chegirmani bronni qo'llash va qayd etish
QRAnalyticsService  — kunlik statistika hisoblash
"""

from __future__ import annotations

import io
import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache settings
QR_CACHE_TIMEOUT = getattr(settings, 'QR_CACHE_TIMEOUT', 300)  # 5 minutes default


# ─── QRGeneratorService ───────────────────────────────────────────────────────

class QRGeneratorService:
    """QR PNG rasm generatsiya — qrcode kutubxonasi orqali."""

    @staticmethod
    def generate_qr_image(qr_code_obj) -> None:
        """
        QRCode ob'ektiga PNG rasm yaratadi va saqlaydi.
        URL ko'rinishi: /api/qr/<code>/
        """
        try:
            import qrcode
            from django.core.files.base import ContentFile

            base_url = getattr(
                settings, 'QR_SCAN_BASE_URL',
                f"{getattr(settings, 'FRONTEND_URL', 'https://imtiaz-crm.vercel.app').rstrip('/')}/qr/"
            )
            if not base_url.endswith('/'):
                base_url += '/'
            url = f"{base_url}{qr_code_obj.code}"

            qr = qrcode.QRCode(
                version       = 1,
                error_correction = qrcode.constants.ERROR_CORRECT_M,
                box_size      = 10,
                border        = 4,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img    = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            filename = f"qr_{qr_code_obj.code}.png"
            qr_code_obj.qr_image.save(filename, ContentFile(buffer.getvalue()), save=True)
            logger.info("QR image generated for code: %s", qr_code_obj.code)
        except ImportError:
            logger.warning("qrcode kutubxonasi o'rnatilmagan. pip install qrcode[pil]")
        except Exception as e:
            logger.error("QR generatsiyada xato: %s", e)


# ─── QRScanService ────────────────────────────────────────────────────────────

class QRScanService:
    """QR kod validatsiya va chegirma hisoblash."""

    @staticmethod
    def _get_cache_key(code: str, user_id: int | None = None) -> str:
        """Generate cache key for QR validation."""
        cache_key = f"qr_validate:{code.strip().upper()}"
        if user_id:
            cache_key += f":user_{user_id}"
        return cache_key

    @staticmethod
    def clear_cache(code: str, user_id: int | None = None) -> None:
        """Clear cached validation results for a QR code."""
        cache_key = QRScanService._get_cache_key(code, user_id)
        cache.delete(cache_key)
        # Also clear the generic cache (without user_id)
        cache.delete(f"qr_validate:{code.strip().upper()}")

    @staticmethod
    def validate_and_get_info(code: str, *, user=None, order_amount: Optional[Decimal] = None) -> dict:
        """
        QR kodni tekshiradi va chegirma ma'lumotlarini qaytaradi.
        Foydalanuvchi/bot scan qilinganda chaqiriladi.

        Returns:
            {
                'is_valid': bool,
                'qr_code': QRCode,
                'discount_amount': Decimal,
                'message': str,
                'user_usage_count': int,
                'remaining_uses': int | None,
            }
        """
        from .models import QRCode, QRCodeRedemption

        # Generate cache key
        user_id = user.id if user and user.is_authenticated else None
        cache_key = QRScanService._get_cache_key(code, user_id)
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            # Recalculate discount based on current order_amount
            if cached_result.get('qr_code'):
                qr = QRCode.objects.get(id=cached_result['qr_code']['id'])
                cached_result['discount_amount'] = Decimal(str(qr.calculate_discount(float(order_amount or 0))))
            return cached_result

        try:
            qr = QRCode.objects.select_related('organization', 'branch').get(code=code.strip().upper())
        except QRCode.DoesNotExist:
            result = {'is_valid': False, 'message': 'QR kod topilmadi.', 'qr_code': None}
            cache.set(cache_key, result, QR_CACHE_TIMEOUT)
            return result

        if not qr.is_valid:
            reason = _get_invalid_reason(qr)
            result = {'is_valid': False, 'message': reason, 'qr_code': qr}
            cache.set(cache_key, result, QR_CACHE_TIMEOUT)
            return result

        # Foydalanuvchi cheklovini tekshirish
        if user and user.is_authenticated:
            user_count = QRCodeRedemption.objects.filter(
                qr_code=qr, user=user, status='applied'
            ).count()
            if user_count >= qr.max_uses_per_user:
                result = {
                    'is_valid': False,
                    'message': f'Siz bu QR kodni {qr.max_uses_per_user} marta ishlatdingiz.',
                    'qr_code': qr,
                }
                cache.set(cache_key, result, QR_CACHE_TIMEOUT)
                return result
        else:
            user_count = 0

        # Chegirmani hisoblash
        discount = Decimal(str(qr.calculate_discount(float(order_amount or 0))))

        # Qolgan ishlatishlar
        remaining = None
        if qr.max_total_uses is not None:
            remaining = max(qr.max_total_uses - qr.total_used_count, 0)

        result = {
            'is_valid':        True,
            'qr_code':         qr,
            'discount_amount': discount,
            'message':         f'QR kod amal qiladi. {qr.get_qr_type_display()}: {qr.discount_value}',
            'user_usage_count': user_count,
            'remaining_uses':   remaining,
            'applicable_services': qr.applicable_services,
            'organization_name':   qr.organization.name,
            'valid_until':         qr.valid_until.isoformat() if qr.valid_until else None,
        }
        
        # Cache the result (exclude the actual qr object to avoid serialization issues)
        cache_data = result.copy()
        cache_data['qr_code'] = {
            'id': qr.id,
            'code': qr.code,
            'title': qr.title,
            'qr_type': qr.qr_type,
            'discount_value': str(qr.discount_value),
        }
        cache.set(cache_key, cache_data, QR_CACHE_TIMEOUT)
        
        return result


def _get_invalid_reason(qr) -> str:
    now = timezone.now()
    if not qr.is_active:
        return 'QR kod faol emas.'
    if qr.valid_from and now < qr.valid_from:
        return f'QR kod {qr.valid_from.strftime("%d.%m.%Y")} dan boshlab amal qiladi.'
    if qr.valid_until and now > qr.valid_until:
        return 'QR kod muddati tugagan.'
    if qr.max_total_uses is not None and qr.total_used_count >= qr.max_total_uses:
        return 'QR kod foydalanish limiti tugagan.'
    return 'QR kod amal qilmaydi.'


# ─── QRRedemptionService ──────────────────────────────────────────────────────

class QRRedemptionService:
    """Chegirmani qo'llash va qayd etish."""

    @staticmethod
    @transaction.atomic
    def redeem(
        code:         str,
        *,
        user=None,
        order_amount: Decimal,
        service_type: str      = 'general',
        booking_id:   Optional[str] = None,
        ip_address:   str      = '',
        user_agent:   str      = '',
        customer_name:  str    = '',
        customer_phone: str    = '',
        staff_user=None,
    ) -> dict:
        """
        QR kod chegirmasini qo'llaydi.

        Returns:
            {
                'success': bool,
                'redemption': QRCodeRedemption,
                'discount_applied': Decimal,
                'final_amount': Decimal,
                'message': str,
            }
        """
        from .models import QRCode, QRCodeRedemption, QRCodeType

        # Avval validatsiya
        info = QRScanService.validate_and_get_info(code, user=user, order_amount=order_amount)
        if not info['is_valid']:
            return {'success': False, 'message': info['message']}

        qr       = info['qr_code']
        discount = info['discount_amount']

        if float(order_amount) < float(qr.minimum_order_amount):
            return {
                'success': False,
                'message': f'Minimal buyurtma summasi: {qr.minimum_order_amount} UZS',
            }

        final_amount = max(Decimal(str(order_amount)) - discount, Decimal('0'))

        # Bonus ball — foydalanuvchi balansiga qo'shish
        bonus_points_awarded = 0
        if qr.qr_type == QRCodeType.BONUS_POINTS and user and user.is_authenticated:
            bonus_points_awarded = int(qr.discount_value)
            from apps.users.models import User
            User.objects.filter(id=user.id).update(
                bonus_points=user.bonus_points + bonus_points_awarded
            )

        # Redemption yaratish
        redemption = QRCodeRedemption.objects.create(
            qr_code          = qr,
            user             = user if (user and user.is_authenticated) else None,
            customer_name    = customer_name[:255] if customer_name else '',
            customer_phone   = customer_phone[:20] if customer_phone else '',
            booking_id       = booking_id,
            service_type     = service_type,
            order_amount     = order_amount,
            discount_applied = discount,
            final_amount     = final_amount,
            ip_address       = ip_address or None,
            user_agent       = user_agent[:500],
            status           = 'applied',
        )

        # total_used_count yangilash
        QRCode.objects.filter(id=qr.id).update(
            total_used_count=qr.total_used_count + 1
        )

        # Clear cache for this QR code
        QRScanService.clear_cache(code, user_id=user.id if user and user.is_authenticated else None)

        # Send QR scan success notification
        if user and user.is_authenticated:
            from apps.notifications.tasks import notify_user
            from apps.notifications.models import Notification
            
            notify_user(
                user=user,
                notification_type=Notification.NotificationType.QR_SCAN_SUCCESS,
                title=f'QR kod skanlandi: {qr.title}',
                body=f'{discount} UZS chegirma qo\'llandi. Yakuniy to\'lov: {final_amount} UZS',
                metadata={
                    'qr_code_id': str(qr.id),
                    'qr_code_title': qr.title,
                    'discount_applied': str(discount),
                    'final_amount': str(final_amount),
                }
            )

        logger.info(
            "QR redeemed: code=%s, user=%s, discount=%s, staff=%s",
            code, user, discount, staff_user,
        )

        message = f'{discount} UZS chegirma qo\'llandi.'
        if bonus_points_awarded:
            message = f'{bonus_points_awarded} bonus ball qo\'shildi.'

        return {
            'success':              True,
            'redemption':           redemption,
            'discount_applied':     discount,
            'final_amount':         final_amount,
            'bonus_points_awarded': bonus_points_awarded,
            'message':              message,
        }

    @staticmethod
    def log_scan_only(code: str, *, user=None, ip_address: str = '', user_agent: str = '') -> None:
        """Faqat skanerlash qayd etiladi (chegirma qo'llanmaydi)."""
        from .models import QRCode, QRCodeRedemption
        try:
            qr = QRCode.objects.get(code=code)
            QRCodeRedemption.objects.create(
                qr_code    = qr,
                user       = user if (user and user.is_authenticated) else None,
                status     = 'scanned',
                ip_address = ip_address or None,
                user_agent = user_agent[:500],
            )
        except Exception as e:
            logger.warning("QR scan log xato: %s", e)


# ─── QRAnalyticsService ───────────────────────────────────────────────────────

class QRAnalyticsService:
    """Kunlik analitika hisoblash — Celery task da ishlatiladi."""

    @staticmethod
    def calculate_daily_analytics(date=None) -> int:
        """
        Berilgan sana uchun barcha QR kodlar analitikasini hisoblaydi.
        Returns: yangilangan yozuvlar soni
        """
        from .models import QRCode, QRCodeRedemption, QRAnalyticsSummary
        from django.db.models import Sum, Count, Q

        if date is None:
            from django.utils import timezone
            date = timezone.now().date() - timezone.timedelta(days=1)

        qr_codes = QRCode.objects.filter(is_active=True)
        updated  = 0

        for qr in qr_codes:
            qs = QRCodeRedemption.objects.filter(qr_code=qr, scanned_at__date=date)

            stats = qs.aggregate(
                scan_count   = Count('id'),
                apply_count  = Count('id', filter=Q(status='applied')),
                reject_count = Count('id', filter=Q(status__in=['rejected', 'expired'])),
                total_discount = Sum('discount_applied'),
                total_revenue  = Sum('final_amount'),
            )

            unique_users = qs.filter(user__isnull=False).values('user').distinct().count()

            QRAnalyticsSummary.objects.update_or_create(
                qr_code=qr,
                date=date,
                defaults={
                    'scan_count':              stats['scan_count'] or 0,
                    'apply_count':             stats['apply_count'] or 0,
                    'reject_count':            stats['reject_count'] or 0,
                    'total_discount_given':    stats['total_discount'] or 0,
                    'total_revenue_generated': stats['total_revenue'] or 0,
                    'unique_users':            unique_users,
                }
            )
            updated += 1

        logger.info("QR analytics calculated for %s: %d records", date, updated)
        return updated
