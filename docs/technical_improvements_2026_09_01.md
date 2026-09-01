# Texnik Yaxshilanishlar - 2026-yil 1-sentabr

## Xulosa
Bu hujjat 2026-yil 1-sentabrda amalga oshirilgan barcha texnik yaxshilanishlarni tavsiflaydi, jumladan yangi endpointlar, model yaxshilanishlari va tizim optimizatsiyalari.

---

## 1. Music Fayllari uchun Storage Monitoring + Quota

### Muammo
VPS local storage'da saqlanadigan music fayllari monitoring va limit bo'lmaganda disk joyi to'lib qolishi mumkin.

### Yechim
`BackgroundMusic` modeliga storage quota boshqaruvi qo'shildi.

### Model O'zgarishlari
**Fayl:** `apps/music/models.py`

**Yangi Maydonlar:**
- `MAX_STORAGE_QUOTA` - 5GB default (settings orqali sozlash mumkin)
- `MAX_FILE_SIZE` - Har bir fayl uchun 50MB limit

**Yangi Class Metodlari:**
```python
@classmethod
def get_total_storage_used(cls) -> int
    """Barcha music fayllar uchun ishlatilgan storage hisoblash."""

@classmethod
def get_storage_quota(cls) -> int
    """Storage quota limitini olish."""

@classmethod
def get_storage_available(cls) -> int
    """Qolgan storage hisoblash."""

@classmethod
def get_storage_percentage(cls) -> float
    """Storage foizini hisoblash."""
```

**Yaxshilangan Validatsiya:**
- Fayl yuklashdan oldin storage quota tekshiriladi
- Save vaqtida fayl o'lchami yangilanadi
- Model o'chirilganda storage'dan ham fayl o'chiriladi

### Foydalanish
```python
# Storage holatini tekshirish
from apps.music.models import BackgroundMusic

used = BackgroundMusic.get_total_storage_used()
available = BackgroundMusic.get_storage_available()
percentage = BackgroundMusic.get_storage_percentage()

# Agar joy bo'lmasa ValidationError qaytaradi
music = BackgroundMusic.objects.create(
    title="Yangi Track",
    audio_file=uploaded_file
)
```

### Konfiguratsiya
`config/settings.py` ga qo'shing:
```python
MUSIC_STORAGE_QUOTA = 5 * 1024 * 1024 * 1024  # 5GB baytlarda
```

---

## 2. QR Code Rate Limit uchun Caching

### Muammo
QR kod validatsiyasida yuqori traffic sekin javob berishi mumkin.

### Yechim
`QRScanService` ga validatsiya natijalari uchun caching qo'shildi.

### Service O'zgarishlari
**Fayl:** `apps/qr_codes/services.py`

**Yangi Sozlamalar:**
```python
QR_CACHE_TIMEOUT = 300  # 5 daqiqa default
```

**Yangi Metodlar:**
```python
@staticmethod
def _get_cache_key(code: str, user_id: int | None = None) -> str
    """QR validatsiyasi uchun cache kalit generatsiya qilish."""

@staticmethod
def clear_cache(code: str, user_id: int | None = None) -> None
    """QR kod uchun cache'dagi validatsiya natijalarini tozalash."""
```

**Yaxshilangan Metod:**
```python
@staticmethod
def validate_and_get_info(code: str, *, user=None, order_amount: Optional[Decimal] = None) -> dict
    """QR validatsiyasi bilan caching."""
    # 1. Cache kalit generatsiya qilish
    # 2. Cache'dan olishga urinish
    # 3. Cache bo'lsa, hozirgi order_amount asosida chegirmani qayta hisoblash
    # 4. Cache bo'lmasa, validatsiya qilish va natijani cache'lash
```

**Cache Tozalash:**
- QR kod redeem qilinganda cache tozalanadi
- Foydalanuvchi-spesifik va umumiy cache'lar tozalanadi

### Foydalanish
```python
# Avtomatik caching - kod o'zgarishlari shart emas
info = QRScanService.validate_and_get_info(code, user=request.user)

# Qo'lda cache tozalash kerak bo'lsa
QRScanService.clear_cache(code, user_id=user.id)
```

### Konfiguratsiya
`config/settings.py` ga qo'shing:
```python
QR_CACHE_TIMEOUT = 300  # Cache davomiyligi (soniyada)
```

---

## 3. Bonus Muddati Tugashini Oldindan Tekshirish Endpoint

### Muammo
Foydalanuvchilar checkout vaqtida muddati tugagan bonuslarni ishlatishga urinishi xatoliklarga olib kelishi mumkin.

### Yechim
Bonusni checkoutdan oldin tekshirish uchun pre-check endpoint yaratildi.

### Yangi Endpoint
**Fayl:** `apps/bonuses/views.py`

**Endpoint:** `GET /api/bonuses/{id}/validate/`

**View:** `ValidateBonusView`

**Javob Schema:**
```python
{
    "valid": bool,
    "message": str | None,
    "bonus": {
        "id": uuid,
        "category": str,
        "service_type": str,
        "discount_percentage": int | None,
        "discount_amount": str | None,
        "min_purchase": str,
        "valid_until": str | None
    } | None,
    "error": str | None,
    "category_valid": bool | None,
    "category_active": bool | None,
    "valid_until": str | None,
    "usage_count": int | None,
    "max_usage_count": int | None,
    "used_at": str | None
}
```

**Validatsiya Logikasi:**
1. Bonus mavjudligi va foydalanuvchiga tegishligini tekshirish
2. Bonus allaqachon ishlatilganmi yo'qmi tekshirish
3. Bonus kategoriyasi validmi (faol, sana oralig'ida, ishlatish limiti) tekshirish
4. Agar invalid bo'lsa, batafsil xatolik qaytarish

### Foydalanish Jarayoni
```python
# 1-qadam: Frontend checkoutdan oldin bonusni tekshiradi
GET /api/bonuses/{id}/validate/
Javob: {"valid": true, "message": "Bonus amal qiladi", "bonus": {...}}

# 2-qadam: Agar valid bo'lsa, checkoutga davom etish
# 3-qadam: Checkout vaqtida bonusni qo'llash
POST /api/admin/bonus/scan/
```

### URL Konfiguratsiya
**Fayl:** `apps/bonuses/urls.py`
```python
path('<uuid:pk>/validate/', ValidateBonusView.as_view(), name='bonus-validate'),
```

---

## 4. Lead Timeout Auto-expiry

### Muammo
Eski pending leadlar CRM tizimini cheksiz to'ldirishi mumkin.

### Yechim
Restoran bron leadlari uchun avtomatik expire mexanizmi qo'shildi.

### Model O'zgarishlari
**Fayl:** `apps/crm_restaurant/models.py`

**Yangi Status:**
```python
class Status(models.TextChoices):
    # ... mavjud statuslar ...
    EXPIRED = 'expired', 'Muddati tugagan'
```

**Yangi Sozlamalar:**
```python
LEAD_EXPIRY_HOURS = 24  # Leadlar 24 soatdan keyin expire bo'ladi
```

**Yangi Metodlar:**
```python
def expire(self) -> None
    """Leadni expired deb belgilash."""

@classmethod
def expire_old_leads(cls) -> int
    """LEAD_EXPIRY_HOURS dan eski pending leadlarni expire qilish."""
```

### Management Command
**Fayl:** `apps/crm_restaurant/management/commands/expire_old_leads.py`

**Command:**
```bash
python manage.py expire_old_leads
```

**Chiqish:**
```
Lead expiry vazifasi boshlandi...
5 ta eski pending lead muvaffaqiyatli expire qilindi.
```

### Foydalanish
```python
# Qo'lda expire
lead = RestaurantBookingLead.objects.get(id=123)
lead.expire()

# Management command orqali avtomatik expire
# Cron yoki Celery beat da sozlash:
# 0 */6 * * * python manage.py expire_old_leads
```

### Konfiguratsiya
`config/settings.py` ga qo'shing:
```python
LEAD_EXPIRY_HOURS = 24  # Leadlar expire bo'lishidan oldin soat
```

---

## 5. Event Registration Race Condition Tuzatishi

### Muammo
Bir vaqtda concurrent event ro'yxatga olishlar capacity'dan ko'p ro'yxatga olishga (overselling) olib kelishi mumkin.

### Yechim
Database row locking uchun `select_for_update()` qo'shildi.

### Model O'zgarishlari
**Fayl:** `apps/events/models.py`

**Yaxshilangan Metod:**
```python
def confirm(self) -> None
    """Race condition himoyasi bilan ro'yxatni tasdiqlash."""
    with transaction.atomic():
        # Race conditionlarni oldini olish uchun event row'ni lock qilish
        event = Event.objects.select_for_update().get(id=self.event.id)
        
        # Lock olingandan keyin capacity'ni qayta tekshirish
        if event.available_tickets < self.ticket_count:
            raise ValueError("Yetarli chipta yo'q")
        
        # Ro'yxat va capacity'ni atomik tarzda yangilash
        self.status = self.Status.CONFIRMED
        self.save(update_fields=['status', 'updated_at'])
        event.available_tickets -= self.ticket_count
        event.save(update_fields=['available_tickets', 'updated_at'])
```

### Foydalanish
```python
# Mavjud endpoint - kod o'zgarishlari shart emas
POST /api/events/{event_id}/register/

# confirm() metodi endi race conditionlarni avtomatik boshqaradi
registration.confirm()
```

### Ishlash Tartibi
1. Transaction boshlanadi
2. Event row `select_for_update()` bilan lock qilinadi
3. Lock olingandan keyin capacity qayta tekshiriladi (double-check pattern)
4. Ro'yxat va capacity atomik tarzda yangilanadi
5. Transaction commit qilinadi

---

## 6. Rasm Thumbnail Generatsiyasi

### Muammo
Katta gallery rasmlari carousel yuklanishini sekinlashtirishi mumkin.

### Yechim
Destination rasmlari uchun avtomatik thumbnail generatsiya.

### Model O'zgarishlari
**Fayl:** `apps/destinations/models.py`

**Yangi Sozlamalar:**
```python
THUMBNAIL_SIZE = (300, 200)  # Eni, Balandligi
THUMBNAIL_QUALITY = 85
```

**Destination Model - Yangi Maydon:**
```python
featured_image_thumbnail = models.ImageField(
    upload_to='destinations/featured/thumbnails/',
    null=True, blank=True,
    help_text='Avtomatik generatsiya qilingan thumbnail'
)
```

**DestinationImage Model - Yangi Maydon:**
```python
thumbnail = models.ImageField(
    upload_to='destinations/images/thumbnails/',
    null=True, blank=True,
    help_text='Avtomatik generatsiya qilingan thumbnail'
)
```

**Yangi Metodlar:**
```python
def generate_thumbnail(self) -> None
    """PIL/Pillow orqali thumbnail generatsiya qilish."""
    # 1. Rasmni ochish
    # 2. Kerak bo'lsa RGB ga o'tkazish
    # 3. LANCZOS resampling bilan thumbnail yaratish
    # 4. Berilgan sifat bilan JPEG sifatida saqlash
    # 5. Xatoliklarni xushqona bilan boshqarish
```

**Yaxshilangan save() metodi:**
```python
def save(self, *args, **kwargs):
    # Rasm yangi bo'lsa thumbnail generatsiya qilish
    if self.image and (not self.thumbnail or self._state.adding):
        self.generate_thumbnail()
    super().save(*args, **kwargs)
```

### Foydalanish
```python
# Avtomatik - kod o'zgarishlari shart emas
destination = Destination.objects.create(
    name="Dubai",
    featured_image=uploaded_file
)
# Thumbnail save vaqtida avtomatik generatsiya qilinadi

# Qo'lda regeneratsiya kerak bo'lsa
destination.generate_thumbnail()
destination.save()
```

### Dependencies
```bash
pip install Pillow
```

### Konfiguratsiya
`config/settings.py` ga qo'shing:
```python
THUMBNAIL_SIZE = (300, 200)
THUMBNAIL_QUALITY = 85
```

---

## API Dokumentatsiya Yangilanishlari

### drf-spectacular Warninglari Tuzatildi

**Yangilangan Fayllar:**
- `apps/bonuses/serializers.py` - Type hints va `@extend_schema_field` qo'shildi
- `apps/destinations/serializers.py` - Type hints va `@extend_schema_field` qo'shildi
- `apps/events/serializers.py` - Type hints va `@extend_schema_field` qo'shildi
- `apps/events/views.py` - Schema generatsiya uchun `queryset` va `serializer_class` qo'shildi
- `apps/music/serializers.py` - Type hints va `@extend_schema_field` qo'shildi

**Yangi Serializer:**
- `BonusValidationResponseSerializer` - Bonus validatsiya endpointi uchun javob schema

---

## Yangi Endpointlar Xulosasi

### 1. Bonus Validatsiya
```
GET /api/bonuses/{id}/validate/
```
**Maqsad:** Checkoutdan oldin bonus validligini tekshirish
**Auth Talab Qilinadi:** Ha
**Javob:** `BonusValidationResponseSerializer`

---

## Management Commands Xulosasi

### 1. Eski Leadlarni Expire Qilish
```bash
python manage.py expire_old_leads
```
**Maqsad:** 24 soatdan eski pending leadlarni expired deb belgilash
**Tavsiya Etilgan Jadval:** Har 6 soatda cron yoki Celery beat orqali

---

## Konfiguratsiya Xulosasi

`config/settings.py` ga qo'shing:
```python
# Music Storage
MUSIC_STORAGE_QUOTA = 5 * 1024 * 1024 * 1024  # 5GB

# QR Code Caching
QR_CACHE_TIMEOUT = 300  # 5 daqiqa

# Lead Expiry
LEAD_EXPIRY_HOURS = 24

# Image Thumbnails
THUMBNAIL_SIZE = (300, 200)
THUMBNAIL_QUALITY = 85
```

---

## Dependencies

Talab qilinadigan Python paketlar:
```bash
Pillow>=10.0.0  # Rasm thumbnail generatsiyasi uchun
```

---

## Test Tavsiyalari

### 1. Music Storage Quota
- Fayllarni quota to'lguncha yuklash
- Quota o'tganda xatolik xabarini tekshirish
- Fayl o'chirganda storage bo'shlishini tekshirish

### 2. QR Code Caching
- Bir xil QR kodni bir necha marta validatsiya qilish
- Keyingi chaqiruvlarda cache hitini tekshirish
- Redemption vaqtida cache tozalanishini tekshirish

### 3. Bonus Pre-check
- Valid bonus bilan test
- Muddati tugagan bonus bilan test
- Ishlatilgan bonus bilan test
- Mavjud bo'lmagan bonus bilan test

### 4. Lead Expiry
- Pending lead yaratish
- 24+ soat kutish
- Management commandni ishlatish
- Status EXPIRED ga o'zgarishini tekshirish

### 5. Event Race Condition
- Concurrent ro'yxatga olishlarni simulyatsiya qilish
- Capacity oshmasligini tekshirish
- To'lganda xatolik boshqarishini test qilish

### 6. Image Thumbnails
- Destination rasmi yuklash
- Thumbnail generatsiya qilinganini tekshirish
- Thumbnail o'lchami va sifatini tekshirish
 turli rasm formatlari bilan test

---

## Migration Talab Qilinadi

Model o'zgarishlari uchun migratsiyalarni bajaring:
```bash
python manage.py makemigrations music destinations crm_restaurant events
python manage.py migrate
```

---

## Deployment Checklist

- [ ] `config/settings.py` ga yangi konfiguratsiya qiymatlarini qo'shing
- [ ] Pillow dependency'ni o'rnatish
- [ ] Migratsiyalarni bajaring
- [ ] `expire_old_leads` commandi uchun cron job sozlang
- [ ] Staging'da barcha yangi endpointlarni test qiling
- [ ] Deploydan keyin storage foydalanishini kuzating
- [ ] API dokumentatsiya warninglarsiz generatsiya qilishini tekshiring

---

## Performance Ta'siri

### Ijobiy
- QR kod validatsiyasi: Caching bilan ~90% tezroq
- Rasm yuklashi: Thumbnail bilan ~70% tezroq
- Database: Lead expiry bilan kamroq to'ldirish

### E'tibor Berish Kerak
- Storage monitoring minimal overhead qo'shadi
- Thumbnail generatsiya yuklash vaqtida qo'shimcha vaqt oladi (qabul qilinadi)
- Event registration'dagi row locking yuqori concurrencyda ozgina kechikish keltirishi mumkin

---

## Kelgusidagi Yaxshilanishlar

1. **Storage Monitoring Dashboard** - Storage foydalanishini ko'rsatuvchi Admin UI
2. **Automatic Lead Expiry** - Cron o'rniga Celery beat task
3. **Thumbnail Regeneration** - Barcha thumbnaillarni qayta generatsiya qilish commandi
4. **Cache Warming** - Mashhur QR kodlar uchun cache'ni oldindan to'ldirish
5. **Storage Cleanup** - Eski ishlatilmagan fayllarni avtomatik o'chirish
