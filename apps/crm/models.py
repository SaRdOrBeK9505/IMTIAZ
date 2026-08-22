"""
CRM app — Hamkor tashkilotlar va filiallar.
Organization → Branch ierarxiyasi.
BranchStaff ruxsatlari.
TZ 3.6 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class BusinessType(models.TextChoices):
    """
    CRM vertikal yo'nalishi — qaysi panel, serializer va endpoint to'plami ishlatilishini belgilaydi.
    org_type dan farqli: bu faqat CRM routing uchun (restaurant CRM, travel CRM, ...).
    """
    RESTAURANT = 'restaurant', 'Restoran'
    TRAVEL     = 'travel',     'Sayohat kompaniyasi'


class Organization(BaseModel):
    """Hamkor tashkilot (restoran zanjiri, aviakassa va h.k.)."""

    class OrgType(models.TextChoices):
        RESTAURANT      = 'restaurant',      'Restoran'
        BAKERY          = 'bakery',          'Peykari / Kofe'
        WELLNESS        = 'wellness',        'Wellness / Yoga'
        SPORT           = 'sport',           'Sport / Padel'
        FASHION         = 'fashion',         'Fashion / Kiyim'
        KIDS            = 'kids',            'Bolalar mahsulotlari'
        LIFESTYLE       = 'lifestyle',       'Lifestyle / Concept'
        FITNESS         = 'fitness',         'Fitnes / Zallar'
        TECH            = 'tech',            'Texnologiya / Gadjetlar'
        PARFUM          = 'parfum',          'Parfyumeriya / Kosmetika'
        AIRLINE         = 'airline',         'Aviakompaniya'
        RAILWAY         = 'railway',         'Temir yo\'l'
        EVENT_ORGANIZER = 'event_organizer', 'Tadbir tashkilotchisi'
        HOTEL           = 'hotel',           'Mehmonxona'
        TOUR_COMPANY    = 'tour_company',    'Tur kompaniyasi'
        OTHER           = 'other',           'Boshqa'

    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=30, choices=OrgType.choices)
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        default=BusinessType.RESTAURANT,
        db_index=True,
        help_text='CRM vertikali: qaysi panel va API namespace ishlatiladi',
    )
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_organization',
        help_text='Tashkilot egasi (UserRole.OWNER)',
    )
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='orgs/logos/', null=True, blank=True)
    website = models.URLField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    crm_webhook_url = models.URLField(
        blank=True, null=True,
        help_text=(
            "Hamkorning tashqi CRM tizimi lead qabul qiluvchi endpointi. "
            "Bo'sh bo'lsa — lead faqat IMTIAZ ichida (TourLead jadvalida) saqlanadi."
        ),
    )
    crm_webhook_secret = models.CharField(
        max_length=128, blank=True, null=True,
        help_text=(
            "Webhook so'roviga X-Signature sifatida qo'shiladigan maxfiy kalit "
            "(HMAC-SHA256). Hamkor CRM tomonidan so'rov haqiqiyligini tekshirish uchun."
        ),
    )

    class Meta:
        verbose_name = 'Tashkilot'
        verbose_name_plural = 'Tashkilotlar'
        ordering = ['name']

    def __str__(self):
        return self.name


class Branch(BaseModel):
    """
    Tashkilot filiallari.
    Organization → Branch ierarxiyasi: bitta tashkilot ko'p filialga ega bo'lishi mumkin.
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='branches'
    )
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Uzbekistan')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    working_hours = models.JSONField(
        default=dict,
        help_text='{"mon": "09:00-22:00", "tue": "09:00-22:00", ...}'
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Filial'
        verbose_name_plural = 'Filiallar'
        ordering = ['organization', 'name']

    def __str__(self):
        return f'{self.organization.name} — {self.name}'


class BranchStaffPermission(models.TextChoices):
    VIEW_BOOKINGS = 'view_bookings', 'Bronlarni ko\'rish'
    MANAGE_BOOKINGS = 'manage_bookings', 'Bronlarni boshqarish'
    VIEW_ANALYTICS = 'view_analytics', 'Analitikani ko\'rish'
    MANAGE_STAFF = 'manage_staff', 'Xodimlarni boshqarish'


class BranchStaff(BaseModel):
    """
    Filial xodimi — faqat o'z branch_id'siga tegishli ma'lumotni ko'radi.
    Ruxsatlar permissions maydoni orqali boshqariladi.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='branch_staff_profile'
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='staff'
    )
    role = models.CharField(max_length=50, blank=True, help_text='Manager, Cashier va h.k.')
    permissions = models.JSONField(
        default=list,
        help_text='Ruxsatlar ro\'yxati: ["view_bookings", "view_analytics", ...]'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Filial xodimi'
        verbose_name_plural = 'Filial xodimlari'

    def __str__(self):
        return f'{self.user} @ {self.branch}'

    def has_permission(self, permission: str) -> bool:
        return permission in (self.permissions or [])


# ─── RestaurantTable ───────────────────────────────────────────────────────────────────────────

class TableStatus(models.TextChoices):
    AVAILABLE = 'available', 'Bo\'sh'
    RESERVED  = 'reserved',  'Bron qilingan'
    OCCUPIED  = 'occupied',  'Band'
    MAINTENANCE = 'maintenance', 'Ta\'mirda'


class RestaurantTable(BaseModel):
    """
    Restoran stoli — AI faqat active va available stollarni ko'radi.
    Restoran CRM admini tomonidan boshqariladi.
    """
    branch        = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='tables'
    )
    table_number  = models.CharField(max_length=20, help_text='"A1", "VIP-3", "Teras-5"')
    capacity      = models.PositiveSmallIntegerField(help_text='Necha kishilik')
    min_capacity  = models.PositiveSmallIntegerField(default=1)
    section       = models.CharField(max_length=100, blank=True, help_text='"Teras", "Ichki zal", "VIP xona"')
    description   = models.TextField(blank=True)
    is_active     = models.BooleanField(default=True)
    is_vip        = models.BooleanField(default=False)
    features      = models.JSONField(
        default=list,
        help_text='["window_view", "outdoor", "smoking", "projector"]'
    )
    # Real-time holat — AI uchun
    current_status    = models.CharField(
        max_length=20, choices=TableStatus.choices, default=TableStatus.AVAILABLE
    )
    status_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Restoran stoli'
        verbose_name_plural = 'Restoran stollar'
        unique_together     = ('branch', 'table_number')
        ordering            = ['branch', 'section', 'table_number']

    def __str__(self):
        return f'{self.branch.name} — {self.table_number} ({self.capacity} kishi)'


class TableTimeSlot(BaseModel):
    """
    Stol vaqt oralig'i — bron uchun slot tizimi.
    AI qaysi vaqt bo'sh ekanini ko'radi va bronlaydi.
    """
    table      = models.ForeignKey(
        RestaurantTable, on_delete=models.CASCADE, related_name='time_slots'
    )
    date       = models.DateField()
    start_time = models.TimeField()
    end_time   = models.TimeField()
    is_available = models.BooleanField(default=True)
    booking    = models.ForeignKey(
        'booking.RestaurantBooking',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='table_slots',
    )
    notes      = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name        = 'Stol vaqt sloti'
        verbose_name_plural = 'Stol vaqt slotlari'
        ordering            = ['date', 'start_time']
        indexes             = [
            models.Index(fields=['table', 'date', 'is_available']),
        ]

    def __str__(self):
        return f'{self.table} | {self.date} {self.start_time}–{self.end_time}'


# ─── Staff Statistics ─────────────────────────────────────────────────────────────────────

class StaffActivityLog(BaseModel):
    """
    Har bir CRM operator harakati qayd etiladi.
    Rahbar kim qanday ishlayotganini bu jurnaldan ko'radi.
    """

    class ActionType(models.TextChoices):
        # Tur bronlari
        CONFIRM_TOUR_BOOKING  = 'confirm_tour_booking',  'Tur bronini tasdiqlash'
        REJECT_TOUR_BOOKING   = 'reject_tour_booking',   'Tur bronini rad etish'
        GENERATE_VOUCHER      = 'generate_voucher',      'Voaucher yaratish'
        # Restoran
        CONFIRM_TABLE_BOOKING = 'confirm_table_booking', 'Stol bronini tasdiqlash'
        CANCEL_TABLE_BOOKING  = 'cancel_table_booking',  'Stol bronini bekor qilish'
        UPDATE_TABLE_STATUS   = 'update_table_status',   'Stol holatini yangilash'
        ADD_TABLE             = 'add_table',             'Stol qo\'shish'
        # Umumiy
        LOGIN                 = 'login',                 'Tizimga kirish'
        LOGOUT                = 'logout',                'Tizimdan chiqish'
        VIEW_ANALYTICS        = 'view_analytics',        'Analitikani ko\'rish'
        MANAGE_QR             = 'manage_qr',             'QR kod boshqarish'
        MANAGE_PACKAGES       = 'manage_packages',       'Paketlarni boshqarish'

    staff       = models.ForeignKey(
        BranchStaff, on_delete=models.CASCADE, related_name='activity_logs'
    )
    action_type = models.CharField(max_length=50, choices=ActionType.choices)
    entity_type = models.CharField(
        max_length=50, blank=True,
        help_text='Qaysi model: TourBooking, RestaurantBooking, ...'
    )
    entity_id   = models.UUIDField(null=True, blank=True)
    description = models.CharField(max_length=500)
    metadata    = models.JSONField(default=dict, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Xodim faoliyat jurnali'
        verbose_name_plural = 'Xodim faoliyat jurnallari'
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['staff', 'action_type', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f'{self.staff} | {self.action_type} | {self.created_at:%Y-%m-%d %H:%M}'


class StaffPerformanceSummary(BaseModel):
    """
    Xodim ish ko'rsatkichlari (denormalized).
    Celery task kunlik hisoblaydi — tez query uchun.
    Rahbar dashboard'ida to'g'ridan-to'g'ri ishlatiladi.
    """

    class PeriodType(models.TextChoices):
        DAILY   = 'daily',   'Kunlik'
        WEEKLY  = 'weekly',  'Haftalik'
        MONTHLY = 'monthly', 'Oylik'

    staff        = models.ForeignKey(
        BranchStaff, on_delete=models.CASCADE, related_name='performance_summaries'
    )
    period_type  = models.CharField(max_length=10, choices=PeriodType.choices)
    period_start = models.DateField()
    period_end   = models.DateField()

    # Tur statistikasi
    tour_bookings_confirmed = models.PositiveIntegerField(default=0)
    tour_bookings_rejected  = models.PositiveIntegerField(default=0)
    vouchers_generated      = models.PositiveIntegerField(default=0)

    # Restoran statistikasi
    table_bookings_confirmed = models.PositiveIntegerField(default=0)
    table_bookings_cancelled = models.PositiveIntegerField(default=0)

    # Umumiy
    total_revenue_managed    = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    avg_response_time_minutes = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    login_count              = models.PositiveIntegerField(default=0)
    total_actions            = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Xodim ish ko\'rsatkichlari'
        verbose_name_plural = 'Xodim ish ko\'rsatkichlari'
        unique_together     = ('staff', 'period_type', 'period_start')
        ordering            = ['-period_start']
        indexes             = [
            models.Index(fields=['staff', 'period_type', 'period_start']),
        ]

    def __str__(self):
        return f'{self.staff} | {self.period_type} | {self.period_start}'


# ─── TourLead (AI orqali kelgan qiziqish) ────────────────────────────────────

class TourLeadStatus(models.TextChoices):
    NEW        = 'new',        'Yangi'
    SENT       = 'sent',       'CRM ga yuborildi'
    FAILED     = 'failed',     'Yuborishda xato'
    CONTACTED  = 'contacted',  'Mijoz bilan bog\'lanildi'
    CONVERTED  = 'converted',  'Bronga aylandi'
    DECLINED   = 'declined',   'Rad etildi'


class TourLead(BaseModel):
    """
    AI orqali kelgan tur bo'yicha qiziqish (lead).

    Oqim:
        1. Mijoz AI bilan suhbatda biror tur paketiga qiziqish bildiradi
        2. AI mijozdan telefon raqamini so'raydi (majburiy)
        3. submit_tour_lead tool chaqiriladi -> TourLead yaratiladi (status=NEW)
        4. Celery task hamkor tashkilotning crm_webhook_url'iga yuboradi
        5. Muvaffaqiyatli bo'lsa -> status=SENT, aks holda -> FAILED (3 marta qayta urinadi)
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='tour_leads',
        limit_choices_to={'org_type': 'tour_company'},
    )
    package = models.ForeignKey(
        'tours.TourPackage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='leads',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tour_leads',
    )
    session = models.ForeignKey(
        'ai_assistant.ConversationSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tour_leads',
    )

    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    preferred_departure_date = models.DateField(null=True, blank=True)
    passengers = models.PositiveSmallIntegerField(default=1)
    note = models.TextField(blank=True, help_text="Mijoz bildirgan qo'shimcha talablar")

    status = models.CharField(
        max_length=12, choices=TourLeadStatus.choices, default=TourLeadStatus.NEW,
    )
    assigned_staff_name = models.CharField(
        max_length=150, blank=True, help_text="Lead bo'yicha shug'ullanayotgan xodim ismi/username"
    )
    crm_response = models.JSONField(default=dict, blank=True, help_text='Hamkor CRM javobi (debug uchun)')
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Tur lead'
        verbose_name_plural = 'Tur leadlar'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['phone']),
        ]


# ─── RestaurantLead (AI orqali kelgan restoran so'rovi) ──────────────────────────

class RestaurantLeadStatus(models.TextChoices):
    NEW        = 'new',        'Yangi'
    SENT       = 'sent',       'CRM ga yuborildi'
    FAILED     = 'failed',     'Yuborishda xato'
    CONTACTED  = 'contacted',  'Mijoz bilan bog\'lanildi'
    CONFIRMED  = 'confirmed',  'Stol bronlandi'
    DECLINED   = 'declined',   'Rad etildi'


class RestaurantLead(BaseModel):
    """
    AI orqali kelgan restoran bo'yicha so'rov / lead.
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='restaurant_leads',
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='restaurant_leads',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='restaurant_leads',
    )
    session = models.ForeignKey(
        'ai_assistant.ConversationSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='restaurant_leads',
    )

    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    guests = models.PositiveSmallIntegerField(default=2)
    note = models.TextField(blank=True, help_text="Mijoz bildirgan qo'shimcha so'rovlar")

    status = models.CharField(
        max_length=12, choices=RestaurantLeadStatus.choices, default=RestaurantLeadStatus.NEW,
    )
    assigned_staff_name = models.CharField(
        max_length=150, blank=True, help_text="Lead bo'yicha shug'ullanayotgan xodim ismi/username"
    )
    crm_response = models.JSONField(default=dict, blank=True, help_text='Hamkor CRM javobi')
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Restoran lead'
        verbose_name_plural = 'Restoran leadlar'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['phone']),
        ]

    def __str__(self):
        return f'{self.full_name or self.phone} → {self.branch or self.organization} [{self.status}]'


# ─── ServiceLead (AI orqali kelgan barcha xizmatlar leadi) ─────────────────────

class ServiceLeadCategory(models.TextChoices):
    TRAVEL         = 'travel',         'Sayohatlar'
    RESTAURANT     = 'restaurant',     'Stol band qilish'
    ROADSIDE       = 'roadside',       "Yo'lda yordam"
    MEDICAL        = 'medical',        'Tibbiyot'
    INSURANCE      = 'insurance',      "Sug'urta"
    FAMILY_OFFICE  = 'family_office',  'Family Office'
    LEISURE        = 'leisure',        'Dam olish'
    FLIGHT         = 'flight',         'Parvoz bileti'
    OTHER          = 'other',          'Boshqa xizmat'


class ServiceLeadStatus(models.TextChoices):
    NEW        = 'new',        'Yangi'
    SENT       = 'sent',       'CRM / Telegram ga yuborildi'
    FAILED     = 'failed',     'Yuborishda xato'
    CONTACTED  = 'contacted',  'Mijoz bilan bog\'lanildi'
    CONVERTED  = 'converted',  'Bajarildi'
    DECLINED   = 'declined',   'Rad etildi'


class ServiceLead(BaseModel):
    """
    AI orqali kelgan barcha platforma xizmatlari (Sayohat, Stol, Yo'lda yordam,
    Tibbiyot, Sug'urta, Family Office, Dam olish, Parvoz) bo'yicha lead.
    """
    category = models.CharField(
        max_length=30, choices=ServiceLeadCategory.choices, default=ServiceLeadCategory.OTHER,
        db_index=True,
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_leads',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_leads',
    )
    session = models.ForeignKey(
        'ai_assistant.ConversationSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='service_leads',
    )

    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    service_name = models.CharField(max_length=255, blank=True, help_text="So'ralgan xizmat nomi")
    customer_analysis = models.TextField(blank=True, help_text="AI tomonidan mijoz haqida yozilgan tahliliy tavsif")
    note = models.TextField(blank=True, help_text="Mijoz so'rovining to'liq tafsilotlari")

    status = models.CharField(
        max_length=12, choices=ServiceLeadStatus.choices, default=ServiceLeadStatus.NEW,
    )
    assigned_staff_name = models.CharField(
        max_length=150, blank=True, help_text="Lead bo'yicha shug'ullanayotgan xodim ismi/username"
    )
    crm_response = models.JSONField(default=dict, blank=True, help_text='Yuborish javobi')
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Xizmat leadi'
        verbose_name_plural = 'Xizmat leadlari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['phone']),
        ]

    def __str__(self):
        return f'[{self.get_category_display()}] {self.full_name or self.phone} ({self.service_name or "Xizmat"})'


