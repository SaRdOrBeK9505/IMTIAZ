"""
Management command: cleanup_and_seed_tours

Bajaradi:
  1. Soxta tur kompaniyalarini to'liq o'chiradi
     (East Asia Point, Mystery Travel, Prestige Travel, Asialuxe Travel)
  2. Silk Road Premium Tours uchun yangi tur paketlari qo'shadi

Ishlatish:
    python manage.py cleanup_and_seed_tours
    python manage.py cleanup_and_seed_tours --dry-run   (faqat ko'rsatadi, o'zgartirmaydi)
    python manage.py cleanup_and_seed_tours --skip-cleanup
    python manage.py cleanup_and_seed_tours --skip-seed
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

User = get_user_model()

# ─── O'chiriladigan kompaniyalar (nom bo'yicha) ────────────────────────────────
DELETE_COMPANY_NAMES = [
    'East Asia Point',
    'Mystery Travel',
    'Prestige Travel',
    'Asialuxe Travel',
]

SILK_ROAD_NAME = 'Silk Road Premium Tours'


class Command(BaseCommand):
    help = "Soxta tur kompaniyalarini o'chiradi va Silk Road uchun paketlar qo'shadi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Haqiqatda o'zgartirmasdan faqat natijani ko'rsatadi",
        )
        parser.add_argument(
            '--skip-cleanup',
            action='store_true',
            help="O'chirish bosqichini o'tkazib yuboradi",
        )
        parser.add_argument(
            '--skip-seed',
            action='store_true',
            help="Paket qo'shish bosqichini o'tkazib yuboradi",
        )

    def handle(self, *args, **options):
        dry_run     = options['dry_run']
        skip_clean  = options['skip_cleanup']
        skip_seed   = options['skip_seed']

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Hech narsa o\'zgarmaydi\n'))

        if not skip_clean:
            self._cleanup(dry_run)

        if not skip_seed:
            self._seed_silk_road(dry_run)

        self.stdout.write(self.style.SUCCESS('\n[OK] Hammasi muvaffaqiyatli bajarildi!'))

    # ──────────────────────────────────────────────────────────────────────────
    # 1. O'CHIRISH
    # ──────────────────────────────────────────────────────────────────────────
    def _cleanup(self, dry_run: bool):
        from apps.crm.models import Organization, TourLead

        self.stdout.write(self.style.HTTP_INFO('\n[1] Soxta kompaniyalarni o\'chirish\n'))

        orgs = Organization.objects.filter(name__in=DELETE_COMPANY_NAMES)

        if not orgs.exists():
            self.stdout.write('  Hech qanday soxta kompaniya topilmadi.')
            return

        for org in orgs:
            self.stdout.write(f'\n  Kompaniya: {self.style.WARNING(org.name)} (ID: {org.id})')
            self._cleanup_org(org, dry_run)

    @transaction.atomic
    def _cleanup_org(self, org, dry_run: bool):
        from apps.crm.models import Branch, BranchStaff, TourLead
        from apps.tours.models import TourPackage, TourDestination, TourAvailability, TourItineraryDay

        # 1. TourLead → o'chiriladi
        leads = org.tour_leads.all()
        self.stdout.write(f'     TourLead: {leads.count()} ta')
        if not dry_run:
            leads.delete()

        # 2. TourAvailability + TourItineraryDay → TourPackage orqali
        packages = org.tour_packages.all()
        pkg_count = packages.count()
        avail_count = TourAvailability.objects.filter(package__organization=org).count()
        itin_count  = TourItineraryDay.objects.filter(package__organization=org).count()
        self.stdout.write(f'     TourPackage: {pkg_count} ta')
        self.stdout.write(f'     TourAvailability: {avail_count} ta')
        self.stdout.write(f'     TourItineraryDay: {itin_count} ta')
        if not dry_run:
            TourItineraryDay.objects.filter(package__organization=org).delete()
            TourAvailability.objects.filter(package__organization=org).delete()
            packages.delete()

        # 3. TourDestination (faqat bu tashkilotga tegishlilar)
        dests = TourDestination.objects.filter(organization=org)
        self.stdout.write(f'     TourDestination: {dests.count()} ta')
        if not dry_run:
            dests.delete()

        # 4. BranchStaff → User
        branches = Branch.objects.filter(organization=org)
        staffs   = BranchStaff.objects.filter(branch__organization=org)
        staff_users = list(staffs.values_list('user_id', flat=True))
        self.stdout.write(f'     Branch: {branches.count()} ta')
        self.stdout.write(f'     BranchStaff (xodim): {staffs.count()} ta')
        if not dry_run:
            staffs.delete()
            branches.delete()

        # 5. Owner User
        owner_id = org.owner_id
        self.stdout.write(f'     Owner user: {org.owner}')
        if not dry_run:
            org.owner = None
            org.save(update_fields=['owner'])

        # 6. Organization o'chiriladi
        if not dry_run:
            org.delete()
            self.stdout.write(self.style.SUCCESS(f'     [OK]  {org.name} to\'liq o\'chirildi'))

            # Owner + staff userlarini o'chirish (boshqa tashkilotda bo'lmasa)
            from apps.crm.models import Organization as Org
            for uid in [owner_id] + staff_users:
                if uid and not Org.objects.filter(owner_id=uid).exists():
                    try:
                        u = User.objects.get(id=uid)
                        u_str = str(u)
                        u.delete()
                        self.stdout.write(f'     [USER]  User o\'chirildi: {u_str}')
                    except User.DoesNotExist:
                        pass
        else:
            self.stdout.write(self.style.WARNING(f'     [DRY-RUN] {org.name} o\'chirilardi'))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. SILK ROAD — TUR PAKETLAR QO'SHISH
    # ──────────────────────────────────────────────────────────────────────────
    def _seed_silk_road(self, dry_run: bool):
        from apps.crm.models import Organization
        from apps.tours.models import TourCategory, TourDestination, TourPackage, TourAvailability, TourItineraryDay

        self.stdout.write(self.style.HTTP_INFO('\n[**]  BOSQICH 2: Silk Road Premium Tours — paketlar qo\'shish\n'))

        from django.contrib.auth import get_user_model
        from apps.crm.models import Branch

        User = get_user_model()

        silk, org_created = Organization.objects.get_or_create(
            name=SILK_ROAD_NAME,
            defaults={
                'org_type':      'tour_company',
                'business_type': 'travel',
                'description':   'O\'zbekistonning eng premium tur operatori. VIP sayohatlar, eksklyuziv paketlar va shaxsiy xizmat.',
                'is_active':     True,
            }
        )
        if org_created:
            self.stdout.write(self.style.SUCCESS(f'  [+] Organization yaratildi: {silk.name}'))

        if not silk.owner_id and not dry_run:
            owner, _ = User.objects.get_or_create(
                phone='+998900000001',
                defaults={
                    'first_name': 'Silk Road',
                    'last_name': 'Director',
                    'role': 'owner_tour',
                    'is_active': True,
                }
            )
            silk.owner = owner
            silk.save(update_fields=['owner', 'updated_at'])

        if not dry_run:
            Branch.objects.get_or_create(
                organization=silk,
                name='Bosh Ofis',
                defaults={
                    'address': 'Toshkent, Chilonzor tumani',
                    'city': 'Toshkent',
                    'country': 'Uzbekistan',
                    'is_active': True,
                }
            )

        self.stdout.write(f'  Organization: {silk.name} ({silk.id})')

        # Kategoriyalar (yo'q bo'lsa yaratiladi)
        cats_data = [
            ('Dengiz va VIP Ta\'til',  'beach',    '', 1),
            ('Ekzotika & Osiyo',       'exotic',   '', 2),
            ('Madaniy-Tarixiy',        'culture',  '', 3),
            ('Mualliflik Turlari',     'author',   '', 4),
            ('Yevropa & Madaniyat',    'europe',   '', 5),
        ]
        cats = {}
        for c_name, _, icon, order in cats_data:
            if not dry_run:
                cat, _ = TourCategory.objects.get_or_create(
                    name=c_name,
                    defaults={'icon': icon, 'is_active': True, 'sort_order': order}
                )
                cats[c_name] = cat
            else:
                try:
                    cats[c_name] = TourCategory.objects.get(name=c_name)
                except TourCategory.DoesNotExist:
                    cats[c_name] = None

        # Yangi paketlar ro'yxati
        packages_data = self._get_packages_data()

        created_count = 0
        skipped_count = 0

        for data in packages_data:
            title = data['title']

            if TourPackage.objects.filter(organization=silk, title=title).exists():
                self.stdout.write(f'  [SKIP]   Mavjud, o\'tkazildi: {title}')
                skipped_count += 1
                continue

            cat_name = data.get('category')
            category = cats.get(cat_name)
            if not category:
                self.stdout.write(self.style.WARNING(f'  [WARN]   Kategoriya topilmadi: {cat_name} — skip'))
                skipped_count += 1
                continue

            if not dry_run:
                with transaction.atomic():
                    # TourDestination
                    dest, dest_created = TourDestination.objects.get_or_create(
                        organization=silk,
                        country=data['country'],
                        city=data.get('city', ''),
                        defaults={
                            'name': data['destination_name'],
                            'description': data.get('dest_description', ''),
                            'climate_info': data.get('climate_info', ''),
                            'visa_info': data.get('visa_info', ''),
                            'best_months': data.get('best_months', []),
                            'is_active': True,
                            'is_popular': data.get('is_popular', False),
                        }
                    )

                    # TourPackage
                    pkg = TourPackage.objects.create(
                        organization       = silk,
                        title              = title,
                        category           = category,
                        destination        = dest,
                        short_description  = data['short_description'],
                        description        = data['description'],
                        duration_days      = data['duration_days'],
                        duration_nights    = data.get('duration_nights', data['duration_days'] - 1),
                        base_price         = Decimal(str(data['base_price'])),
                        currency           = 'UZS',
                        price_per          = 'person',
                        max_group_size     = data.get('max_group_size', 15),
                        min_group_size     = data.get('min_group_size', 2),
                        is_active          = True,
                        is_featured        = data.get('is_featured', False),
                        inclusions         = data.get('inclusions', []),
                        exclusions         = data.get('exclusions', []),
                        requirements       = data.get('requirements', []),
                        difficulty_level   = data.get('difficulty', 'easy'),
                        tags               = data.get('tags', []),
                        languages_offered  = data.get('languages', ['uz', 'ru']),
                    )

                    # TourItineraryDay
                    for day in data.get('itinerary', []):
                        TourItineraryDay.objects.create(
                            package     = pkg,
                            day_number  = day['day'],
                            title       = day['title'],
                            description = day.get('description', ''),
                            activities  = day.get('activities', []),
                            accommodation = day.get('accommodation', ''),
                            meals       = day.get('meals', {'breakfast': True, 'lunch': False, 'dinner': True}),
                        )

                    # TourAvailability — 4 ta sanalar (3 oydan boshlab)
                    from django.utils import timezone
                    from datetime import timedelta
                    base_date = timezone.now().date().replace(day=1)
                    for i in range(4):
                        dep_date = base_date + timedelta(days=30 * (i + 1))
                        TourAvailability.objects.create(
                            package        = pkg,
                            departure_date = dep_date,
                            return_date    = dep_date + timedelta(days=data['duration_days']),
                            total_seats    = data.get('max_group_size', 15),
                            booked_seats   = 0,
                            status         = 'open',
                        )

                self.stdout.write(self.style.SUCCESS(
                    f'  [OK]  Qo\'shildi: {title} '
                    f'({data["duration_days"]} kun, {data["base_price"]:,} UZS)'
                ))
                created_count += 1
            else:
                self.stdout.write(self.style.WARNING(
                    f'  [DRY-RUN] Qo\'shilar edi: {title}'
                ))
                created_count += 1

        self.stdout.write(
            f'\n  [SUMMARY] Natija: {created_count} ta yangi, {skipped_count} ta mavjud (o\'tkazildi)'
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PAKETLAR MA'LUMOTLARI
    # ──────────────────────────────────────────────────────────────────────────
    def _get_packages_data(self) -> list[dict]:
        return [
            # ─── 1. ISTANBUL ───────────────────────────────────────────────
            {
                'title': "Istanbul — Ikki Qit'a Shahri VIP Sayohati (5 kun / 4 tun)",
                'category': 'Madaniy-Tarixiy',
                'country': 'Turkey',
                'city': 'Istanbul',
                'destination_name': "Istanbul — Ikki Qit'a Shahri",
                'dest_description': "Yevropa va Osiyo tutashgan buyuk shahar — tarix, madaniyat va zamonaviylikning uyg'unligi.",
                'climate_info': 'Iyun-Sentabr — iliq, quruq. Mart-May — maftunkor bahor.',
                'visa_info': "O'zbekiston fuqarolari uchun e-viza (online, 3-5 kun) yoki chegara vizasi.",
                'best_months': ['April', 'May', 'September', 'October'],
                'is_popular': True,
                'short_description': "Istanbul — tarix, me'morchilik va zamonaviy hayot uyg'unligi. Ayasofiya, Bosphorus, bozorlar va ko'proq.",
                'description': (
                    "Istanbul — dunyoning eng qadimiy va go'zal shaharlaridan biri. "
                    "Ayasofiya, Topkapi saroyi, Kapalı Çarşı (Qopqali bozor) va Bosphorus bo'ylab kemada sayr — "
                    "bularning hammasi bir sayohatda. Premium mehmonxona, shaxsiy gid va maxsus VIP transferlar bilan."
                ),
                'duration_days': 5,
                'duration_nights': 4,
                'base_price': 18_500_000,
                'max_group_size': 12,
                'min_group_size': 2,
                'is_featured': True,
                'difficulty': 'easy',
                'tags': ['vip', 'culture', 'history', 'europe', 'turkey'],
                'languages': ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Istanbul, economy)',
                    'Premium mehmonxona (5★, 4 tun)',
                    'Barcha transferlar (aeroport ↔ mehmonxona)',
                    'Shaxsiy o\'zbek-rus tilida gid',
                    'Ayasofiya, Topkapi, Dolmabahçe ziyoratlari',
                    'Bosphorus kruizi (kechki)',
                    'Kundalik nonushta',
                    'Sug\'urta',
                ],
                'exclusions': [
                    'Viza xarajatlari (~$25)',
                    'Tushlik va kechki ovqat (nonushtadan tashqari)',
                    'Shaxsiy xarajatlar va xarid',
                    'Ixtiyoriy ekskursiyalar',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'E-viza oldindan rasmiylashtirilishi kerak',
                ],
                'itinerary': [
                    {
                        'day': 1,
                        'title': "1-kun: Toshkent → Istanbul. Joylashish",
                        'description': "Toshkentdan parvoz, Istanbul Atatürk/Sabiha aeroportiga etib kelamiz. Transfer va joylashish.",
                        'activities': [
                            {'time': '06:00', 'activity': 'Aeroportga yetkazib borish', 'location': 'Toshkent'},
                            {'time': '11:30', 'activity': "Istanbul aeroportiga qo'nish", 'location': 'Istanbul'},
                            {'time': '13:00', 'activity': 'Mehmonxonaga transfer va joylashish', 'location': 'Istanbul'},
                            {'time': '19:00', 'activity': "Sultanahmet maydonini ko'rish (tashqaridan)", 'location': 'Sultanahmet'},
                        ],
                        'accommodation': 'Five Stars Hotel Istanbul (5★)',
                        'meals': {'breakfast': False, 'lunch': False, 'dinner': True},
                    },
                    {
                        'day': 2,
                        'title': "2-kun: Tarix safari — Ayasofiya, Topkapi, Bozor",
                        'description': "Istanbul tarixi bilan tanishish. Ayasofiya, Topkapi saroyi va Kapalı Çarşı.",
                        'activities': [
                            {'time': '09:00', 'activity': 'Ayasofiya (ichkarisini ziyorat)', 'location': 'Sultanahmet'},
                            {'time': '11:00', 'activity': 'Topkapi saroyi va Harem', 'location': 'Sultanahmet'},
                            {'time': '14:00', 'activity': 'Kapalı Çarşı (Qopqali bozor) sayri', 'location': 'Beyazıt'},
                            {'time': '17:00', 'activity': 'Ko\'k masjid (Blue Mosque)', 'location': 'Sultanahmet'},
                        ],
                        'accommodation': 'Five Stars Hotel Istanbul (5★)',
                        'meals': {'breakfast': True, 'lunch': False, 'dinner': False},
                    },
                    {
                        'day': 3,
                        'title': "3-kun: Dolmabahçe & Bosphorus kruizi",
                        'description': "Dolmabahçe saroyi va kechki Bosphorus bo'ylab kemada sayr.",
                        'activities': [
                            {'time': '10:00', 'activity': 'Dolmabahçe saroyi ziyorati', 'location': 'Beşiktaş'},
                            {'time': '14:00', 'activity': 'Ortaköy — foto va qahva', 'location': 'Ortaköy'},
                            {'time': '18:30', 'activity': "Bosphorus premium kechki kruizi (2 soat)", 'location': 'Eminönü'},
                        ],
                        'accommodation': 'Five Stars Hotel Istanbul (5★)',
                        'meals': {'breakfast': True, 'lunch': False, 'dinner': True},
                    },
                    {
                        'day': 4,
                        'title': "4-kun: Galata, Taksim, Zamonaviy Istanbul",
                        'description': "Zamonaviy Istanbul — Galata minorasi, İstiklal ko'chasi.",
                        'activities': [
                            {'time': '10:00', 'activity': "Galata minorasi — shahar panoramasi", 'location': 'Galata'},
                            {'time': '12:00', 'activity': "İstiklal ko'chasi sayri va xarid", 'location': 'Beyoğlu'},
                            {'time': '15:00', 'activity': "Mısır Çarşısı — ziravorlar bozori", 'location': 'Eminönü'},
                            {'time': '19:00', 'activity': "Erkin kechki vaqt", 'location': 'Istanbul'},
                        ],
                        'accommodation': 'Five Stars Hotel Istanbul (5★)',
                        'meals': {'breakfast': True, 'lunch': False, 'dinner': False},
                    },
                    {
                        'day': 5,
                        'title': "5-kun: Istanbul → Toshkent. Xayrlashuv",
                        'description': "Ertalab erkin vaqt, tushdan keyin aeroportga transfer va parvoz.",
                        'activities': [
                            {'time': '09:00', 'activity': "Erkin vaqt / so'nggi xaridlar", 'location': 'Istanbul'},
                            {'time': '13:00', 'activity': "Aeroportga transfer", 'location': 'Istanbul'},
                            {'time': '16:00', 'activity': "Toshkentga parvoz", 'location': 'Istanbul Aeroporti'},
                        ],
                        'accommodation': '',
                        'meals': {'breakfast': True, 'lunch': False, 'dinner': False},
                    },
                ],
            },

            # ─── 2. PARIJ ──────────────────────────────────────────────────
            {
                'title': "Parij — Sevgi Shahri Premium Sayohat (7 kun / 6 tun)",
                'category': "Yevropa & Madaniyat",
                'country': 'France',
                'city': 'Paris',
                'destination_name': "Parij — Yorug'lik Shahri",
                'dest_description': "Eyffel minorasi, Luvr, fashion va gastronomiyanin butun dunyoga mashhur poytaxti.",
                'climate_info': 'May-Sentabr eng yaxshi. Aprel — gullagan Parij.',
                'visa_info': "Shengen viza kerak (10-15 ish kuni). O'zbekiston fuqarolari uchun Fransiya konsulxonasi.",
                'best_months': ['April', 'May', 'June', 'September'],
                'is_popular': True,
                'short_description': "Eyffel, Luvr, Seine daryosi — Parijning go'zalliklarini VIP darajada kashf eting.",
                'description': (
                    "Parij — romantika, san'at va madaniyatning ramzi. "
                    "Eyffel minorasi, Luvr muzeyi, Notre-Dame, Versailles saroyi va Champs-Élysées — "
                    "bularni shaxsiy gid bilan chuqur kashf etish imkoniyati. "
                    "Premium mehmonxona, biznes class avia chipta va VIP transfer."
                ),
                'duration_days': 7,
                'duration_nights': 6,
                'base_price': 45_000_000,
                'max_group_size': 10,
                'min_group_size': 2,
                'is_featured': True,
                'difficulty': 'easy',
                'tags': ['vip', 'europe', 'romance', 'culture', 'luxury'],
                'languages': ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Parij, business class)',
                    'Butik mehmonxona (5★, 6 tun, markazda)',
                    'Barcha transferlar (VIP avto)',
                    "Shaxsiy o'zbekistonlik gid",
                    'Luvr, Versailles, Eyffel (lift) kirish)',
                    "Seine bo'ylab kechki kruiz",
                    'Kundalik nonushta + 2 ta premium kechki ovqat',
                    "Sug'urta (keng qamrovli)",
                ],
                'exclusions': [
                    'Shengen viza ($80-120)',
                    'Tushlik va aksariyat kechki ovqatlar',
                    'Shaxsiy xaridlar',
                    'Ixtiyoriy Disneyland, shopping ekskursiyalar',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'Shengen viza (bizning yordamimiz bilan)',
                    "Tibbiy sug'urta (kiritilgan)",
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Parij. Joylashish va Marais tumani", 'description': "Parvoz, joylashish, Le Marais tumani sayri.", 'activities': [{'time': '08:00', 'activity': 'Toshkentdan parvoz', 'location': 'TAS'}, {'time': '14:00', 'activity': "Parij CDG aeroportiga qo'nish", 'location': 'CDG'}, {'time': '16:00', 'activity': 'Joylashish', 'location': 'Mehmonxona'}, {'time': '19:00', 'activity': 'Le Marais tumani kechki sayri', 'location': 'Paris'}], 'accommodation': 'Hôtel de Crillon / yoki teng darajali 5★', 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Eyffel, Trocadéro, Invalides", 'description': "Parijning ikoni — Eyffel minorasi lift bilan.", 'activities': [{'time': '09:30', 'activity': "Trocadéro — Eyffel panoramasi", 'location': 'Paris'}, {'time': '11:00', 'activity': "Eyffel minorasi (lift, top)", 'location': 'Paris'}, {'time': '14:00', 'activity': "Invalides va Napoleon qabri", 'location': 'Paris'}, {'time': '18:30', 'activity': "Seine bo'ylab kechki kruiz", 'location': 'Paris'}], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 3, 'title': "Luvr va Tuileriya bog'i", 'description': "Dunyo eng yirik san'at muzeyi — Mona Liza va Venera.", 'activities': [{'time': '09:00', 'activity': "Luvr muzeyi (skip-the-line)", 'location': 'Paris'}, {'time': '14:00', 'activity': "Tuileriya bog'i sayri", 'location': 'Paris'}, {'time': '16:00', 'activity': "Champs-Élysées va Arc de Triomphe", 'location': 'Paris'}], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Versailles saroyi", 'description': "Qirollik saroyi va Frantsiya tarixi.", 'activities': [{'time': '09:00', 'activity': 'Versailles sayohati (VIP avto)', 'location': 'Versailles'}, {'time': '10:00', 'activity': "Versailles saroyi va bog'i", 'location': 'Versailles'}, {'time': '16:00', 'activity': "Qaytish, erkin kechki vaqt", 'location': 'Paris'}], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Montmartre, Sacré-Cœur, Galeries Lafayette", 'description': "San'atkorlar mahallasi va premium xarid.", 'activities': [{'time': '10:00', 'activity': "Montmartre va Sacré-Cœur", 'location': 'Paris'}, {'time': '13:00', 'activity': 'Galeries Lafayette (premium xarid)', 'location': 'Paris'}], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 6, 'title': "Erkin kun — Xarid yoki Disneyland", 'description': "Erkin kun.", 'activities': [{'time': '10:00', 'activity': 'Erkin kun', 'location': 'Paris'}], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 7, 'title': "Parij → Toshkent. Xayrlashuv", 'description': "Aeroportga transfer va hazil.", 'activities': [{'time': '09:00', 'activity': 'Erkin vaqt', 'location': 'Paris'}, {'time': '13:00', 'activity': 'Aeroportga transfer', 'location': 'CDG'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 3. MALDIV ─────────────────────────────────────────────────
            {
                'title': "Maldiv — Okean Jannatida Ultra-All-Inclusive (6 kun / 5 tun)",
                'category': "Dengiz va VIP Ta'til",
                'country': 'Maldives',
                'city': 'Malé',
                'destination_name': "Maldiv — Hind Okeani Jannat Orollari",
                'dest_description': "Ko'k suv, oq qumloq va dengiz osti dunyosi — dunyoning eng ekzotik kurort joyi.",
                'climate_info': "Noyabr-Aprel — quruq mavsim, eng yaxshi vaqt. May-Oktyabr — yomg'irli.",
                'visa_info': "Maldivga O'zbekiston fuqarolari vizasiz kiradi (30 kungacha). Pasport va hotel bron kerak.",
                'best_months': ['November', 'December', 'January', 'February', 'March'],
                'is_popular': True,
                'short_description': "Maldivdagi shaffof suv villa (water bungalow), diving va sunset kruiz bilan tushib bo'lmas taassurot.",
                'description': (
                    "Maldiv — dengiz ustidagi villa (overwater bungalow), coral reef diving, "
                    "sunset kruiz va ultra all-inclusive xizmat. "
                    "Silk Road Premium orqali maxsus narx va VIP transferlar."
                ),
                'duration_days': 6,
                'duration_nights': 5,
                'base_price': 52_000_000,
                'max_group_size': 8,
                'min_group_size': 2,
                'is_featured': True,
                'difficulty': 'easy',
                'tags': ['beach', 'luxury', 'honeymoon', 'diving', 'vip', 'maldives'],
                'languages': ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Malé, iqtisodiy)',
                    "Qo'nalji uchun speedboat transfer (Malé ↔ resort)",
                    'Overwater Bungalow (5★ resort, 5 tun)',
                    'Ultra All-Inclusive (3 mahal ovqat + ichimliklar)',
                    '2 ta Snorkeling ekskursiyasi',
                    'Sunset dhoni kruizi',
                    "Dengiz ostini ko'rish (semi-submarine)",
                    "Sug'urta",
                ],
                'exclusions': [
                    'Scuba diving (alohida to\'lov)',
                    'Spa va massaj xizmatlari',
                    'Shaxsiy xarajatlar',
                    'Viza (talab qilinmaydi)',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'Hotel confirmation (chegara nazoratida ko\'rsatiladi)',
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Malé → Resort. Joylashish", 'description': "Parvoz, Malé, speedboat transfer, resort.", 'activities': [{'time': '07:00', 'activity': 'Toshkentdan parvoz', 'location': 'TAS'}, {'time': '17:00', 'activity': "Malé aeroportiga qo'nish", 'location': 'Malé'}, {'time': '18:30', 'activity': 'Speedboat transfer (resort)', 'location': 'Ocean'}, {'time': '20:00', 'activity': 'Joylashish, xush kelibsiz kokteil', 'location': 'Resort'}], 'accommodation': 'Overwater Bungalow (5★)', 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Plyaj va Snorkeling — Coral Reef", 'description': "Ertalab plyaj, kunduzi snorkeling, kechki kruiz.", 'activities': [{'time': '09:00', 'activity': 'Plyajda erkin vaqt', 'location': 'Resort'}, {'time': '11:00', 'activity': 'Snorkeling (coral reef, gid bilan)', 'location': 'Ocean'}, {'time': '18:00', 'activity': 'Sunset dhoni kruizi', 'location': 'Ocean'}], 'accommodation': 'Overwater Bungalow (5★)', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 3, 'title': "Dengiz osti safari — Semi-submarine", 'description': "Dengiz ostini ko'rish, erkin plyaj.", 'activities': [{'time': '10:00', 'activity': 'Semi-submarine ekskursiyasi', 'location': 'Ocean'}, {'time': '14:00', 'activity': 'Erkin plyaj va basseyn', 'location': 'Resort'}], 'accommodation': 'Overwater Bungalow (5★)', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 4, 'title': "Malé shahar ziyorati (ixtiyoriy)", 'description': "Malé shahri — Maldiv poytaxti.", 'activities': [{'time': '10:00', 'activity': "Malé shahri (ixtiyoriy speedboat)", 'location': 'Malé'}, {'time': '15:00', 'activity': 'Qaytish va erkin kechki', 'location': 'Resort'}], 'accommodation': 'Overwater Bungalow (5★)', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 5, 'title': "Erkin kun — Plyaj, Spa va So'nggi Tungi Kruiz", 'description': "Erkin va yengil kun.", 'activities': [{'time': '10:00', 'activity': 'Erkin plyaj va basseyn', 'location': 'Resort'}, {'time': '19:00', 'activity': "So'nggi kechki kruiz va sunset", 'location': 'Ocean'}], 'accommodation': 'Overwater Bungalow (5★)', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 6, 'title': "Resort → Malé → Toshkent. Xayrlashuv", 'description': "Check-out, speedboat, parvoz.", 'activities': [{'time': '08:00', 'activity': 'Check-out va speedboat Maléga', 'location': 'Resort → Malé'}, {'time': '14:00', 'activity': 'Toshkentga parvoz', 'location': 'Malé'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 4. LONDON ─────────────────────────────────────────────────
            {
                'title': "London — Buyuk Britaniya Klassikasi (6 kun / 5 tun)",
                'category': "Yevropa & Madaniyat",
                'country': 'United Kingdom',
                'city': 'London',
                'destination_name': "London — Buyuk Britaniya Poytaxti",
                'dest_description': "Temza daryosi bo'yidagi tarixi, muzeylar va zamonaviy madaniyat markazi.",
                'climate_info': "May-Sentabr — eng yaxshi ob-havo. Yomg'irga tayyor bo'ling.",
                'visa_info': "Britaniya vizasi kerak (UK Standard Visitor Visa, online ariza). 3-4 hafta.",
                'best_months': ['May', 'June', 'July', 'August', 'September'],
                'is_popular': False,
                'short_description': "Big Ben, Tower of London, Buckingham saroyi va zamonaviy London — VIP darajada sayohat.",
                'description': (
                    "London — tarix va zamonaviylikning uyg'unligi. "
                    "Big Ben, Tower Bridge, Buckingham saroyi, British Museum va West End teatrlari — "
                    "bularni shaxsiy gid bilan kashf eting."
                ),
                'duration_days': 6,
                'duration_nights': 5,
                'base_price': 42_000_000,
                'max_group_size': 12,
                'min_group_size': 2,
                'is_featured': False,
                'difficulty': 'easy',
                'tags': ['europe', 'culture', 'history', 'uk', 'vip'],
                'languages': ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ London, economy)',
                    'Mehmonxona (4★, markazda, 5 tun)',
                    'Barcha transferlar (Heathrow ↔ mehmonxona)',
                    "Oyster Card (metro va avtobus, 5 kun)",
                    'British Museum, Tower of London, Tate Modern kirish',
                    "Shaxsiy o'zbekistonlik gid (3 kun)",
                    'Kundalik nonushta',
                    "Sug'urta",
                ],
                'exclusions': [
                    'Britaniya vizasi',
                    'Tushlik va kechki ovqat',
                    'Shaxsiy xaridlar',
                    'West End teatr (ixtiyoriy)',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'UK Standard Visitor Visa',
                    "Bank hisobi ko'chirmasi",
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → London. Joylashish", 'description': "Parvoz va joylashish.", 'activities': [{'time': '08:00', 'activity': 'Parvoz', 'location': 'TAS'}, {'time': '14:00', 'activity': 'Heathrow, transfer, joylashish', 'location': 'London'}], 'accommodation': '4★ London Markaziy', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Westminster — Big Ben, Parlament, Buckingham", 'description': "London ikonlari.", 'activities': [{'time': '09:30', 'activity': "Westminster ko'prigi, Big Ben", 'location': 'London'}, {'time': '11:00', 'activity': "Parlament binosi", 'location': 'London'}, {'time': '14:00', 'activity': "Buckingham saroyi (Changing of the Guard)", 'location': 'London'}, {'time': '16:00', 'activity': "St. James's Park sayri", 'location': 'London'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Tower of London, Tower Bridge, Temza", 'description': "Sharqiy London tarixi.", 'activities': [{'time': '10:00', 'activity': 'Tower of London', 'location': 'London'}, {'time': '13:00', 'activity': 'Tower Bridge', 'location': 'London'}, {'time': '15:00', 'activity': "Temza bo'ylab piyoda sayri", 'location': 'London'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "British Museum & Covent Garden", 'description': "Muzey va teatr tumani.", 'activities': [{'time': '09:30', 'activity': 'British Museum', 'location': 'London'}, {'time': '14:00', 'activity': 'Covent Garden', 'location': 'London'}, {'time': '16:00', 'activity': 'Oxford Street (xarid)', 'location': 'London'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Erkin kun — Notting Hill, Camden yoki Portobello", 'description': "Erkin kun.", 'activities': [{'time': '10:00', 'activity': "Notting Hill / Portobello bozori", 'location': 'London'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 6, 'title': "London → Toshkent", 'description': "Xayrlashuv.", 'activities': [{'time': '09:00', 'activity': 'Erkin vaqt', 'location': 'London'}, {'time': '13:00', 'activity': 'Aeroportga transfer', 'location': 'London'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 5. BALI ───────────────────────────────────────────────────
            {
                'title': "Bali — Xudolar Oroli Ekzotik Safari (8 kun / 7 tun)",
                'category': "Ekzotika & Osiyo",
                'country': 'Indonesia',
                'city': 'Bali',
                'destination_name': "Bali — Indoneziya Ekzotikasi",
                'dest_description': "Guruch dalalaari, ibodatxonalar, tropik plyajlar va uniqal Bali madaniyati.",
                'climate_info': "Aprel-Oktyabr — quruq mavsim, eng yaxshi. Noyabr-Mart — yomg'irli.",
                'visa_info': "Visa on Arrival (VOA) — $35, chegara nazoratida. 30 kun.",
                'best_months': ['April', 'May', 'June', 'July', 'August', 'September'],
                'is_popular': True,
                'short_description': "Ubud guruch dalalaari, Tanah Lot ibodatxonasi, Seminyak plyaji va Bali kung-fu shoulari.",
                'description': (
                    "Bali — tabiat, ma'naviyat va hashamatning uyg'unligi. "
                    "Ubud ko'k guruch dalalaari, Tegallalang, Tanah Lot ibodatxonasi, "
                    "Kuta va Seminyak premium plyajlari — hammasi bir sayohatda."
                ),
                'duration_days': 8,
                'duration_nights': 7,
                'base_price': 26_000_000,
                'max_group_size': 14,
                'min_group_size': 2,
                'is_featured': False,
                'difficulty': 'easy',
                'tags': ['beach', 'exotic', 'asia', 'culture', 'nature', 'bali'],
                'languages': ['uz', 'ru'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Denpasar, economy)',
                    'Villa / mehmonxona (4★, 7 tun, basseynli)',
                    'Barcha transferlar (aeroport ↔ hotel)',
                    '4 ta ekskursiya (Ubud, Tanah Lot, Kintamani, Uluwatu)',
                    "Guruch dalalaari sayri (Tegallalang)",
                    "Kechki Kecak raqs shoulari",
                    'Kundalik nonushta',
                    "Sug'urta",
                ],
                'exclusions': [
                    'VOA viza ($35)',
                    'Diving va surfing darslari',
                    'Tushlik va kechki ovqat',
                    'Shaxsiy xaridlar',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'Chegara nazoratida VOA (pul tayyorlab boring)',
                    'Ixtiyoriy: tibbiy sug\'urta',
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Bali. Joylashish", 'description': "Parvoz va transfer.", 'activities': [{'time': '08:00', 'activity': 'Parvoz (Toshkent → Bali)', 'location': 'TAS'}, {'time': '20:00', 'activity': "Denpasar qo'nish, VOA, transfer", 'location': 'Bali'}], 'accommodation': '4★ Villa Seminyak', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Ubud — Guruch Dalalaari va Maymunlar O'rmoni", 'description': "Ubud sayohati.", 'activities': [{'time': '09:00', 'activity': "Tegallalang guruch dalalaari", 'location': 'Ubud'}, {'time': '11:00', 'activity': "Maymunlar o'rmoni (Ubud)", 'location': 'Ubud'}, {'time': '14:00', 'activity': "Ubud bozori va san'at galereyalari", 'location': 'Ubud'}], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Tanah Lot & Uluwatu Ibodatxonalari", 'description': "Muqaddas joylar.", 'activities': [{'time': '09:00', 'activity': 'Tanah Lot ibodatxonasi (dengiz ustida)', 'location': 'Bali'}, {'time': '16:00', 'activity': 'Uluwatu cliff ibodatxonasi', 'location': 'Bali'}, {'time': '18:30', 'activity': "Kecak va olov raqs shousi (sunset)", 'location': 'Uluwatu'}], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Kintamani Vulqoni va Ko'li", 'description': "Tog' va vulqon manzaralari.", 'activities': [{'time': '08:00', 'activity': "Batur vulqoni va ko'li panoramasi", 'location': 'Kintamani'}, {'time': '13:00', 'activity': "Tirta Empul muqaddas buloq ibodatxonasi", 'location': 'Bali'}], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': True, 'dinner': False}},
                    {'day': 5, 'title': "Seminyak Plyaji va Sunset", 'description': "Plyaj kuni.", 'activities': [{'time': '10:00', 'activity': "Seminyak plyajida erkin vaqt", 'location': 'Seminyak'}, {'time': '18:00', 'activity': "Kuta sunset va kechki sayr", 'location': 'Kuta'}], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 6, 'title': "Nusa Penida sayohati (ixtiyoriy)", 'description': "Orol sayohati.", 'activities': [{'time': '07:00', 'activity': "Nusa Penida speedboat", 'location': 'Nusa Penida'}, {'time': '10:00', 'activity': "Kelingking Beach (cliff manzara)", 'location': 'Nusa Penida'}], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 7, 'title': "Erkin kun — Spa yoki Xarid", 'description': "Erkin kun.", 'activities': [{'time': '10:00', 'activity': 'Balinese spa massaj (ixtiyoriy)', 'location': 'Seminyak'}, {'time': '14:00', 'activity': "Seminyak xarid", 'location': 'Seminyak'}], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 8, 'title': "Bali → Toshkent. Xayrlashuv", 'description': "Check-out va parvoz.", 'activities': [{'time': '09:00', 'activity': 'Erkin vaqt', 'location': 'Bali'}, {'time': '13:00', 'activity': "Aeroportga transfer va parvoz", 'location': 'Denpasar'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 6. QOHIRA & MISR ──────────────────────────────────────────
            {
                'title': "Misr — Fir'avnlar Yurti & Qizil Dengiz (8 kun / 7 tun)",
                'category': "Madaniy-Tarixiy",
                'country': 'Egypt',
                'city': 'Cairo',
                'destination_name': "Misr — Qadimiy Sivilizatsiya Yurti",
                'dest_description': "Piramidalar, Nil daryosi, Luxor ibodatxonalari va Qizil dengiz kurortlari.",
                'climate_info': "Oktyabr-Aprel — eng yaxshi ob-havo. May-Sentabr — juda issiq (+40°C).",
                'visa_info': "E-viza online ($25). Yoki Visa on Arrival aeroportda.",
                'best_months': ['October', 'November', 'December', 'January', 'February', 'March'],
                'is_popular': False,
                'short_description': "Giza piramidalari, Sfinks, Qohira muzeyi va Sharm el-Sheikh plyajlari — o'n asrlik tarix va tropik ta'til.",
                'description': (
                    "Misr — inson sivilizatsiyasining beshigi. "
                    "Giza piramidalari va Sfinks, Qohira Milliy muzeyi (Tutanxamon), "
                    "Nil bo'ylab sayohat va Sharm el-Sheikh Qizil dengiz plyajlari — "
                    "bularni bir sayohatda birlashtirgan maxsus premium paket."
                ),
                'duration_days': 8,
                'duration_nights': 7,
                'base_price': 22_000_000,
                'max_group_size': 14,
                'min_group_size': 2,
                'is_featured': False,
                'difficulty': 'easy',
                'tags': ['history', 'culture', 'beach', 'egypt', 'pyramids'],
                'languages': ['uz', 'ru'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Qohira, economy)',
                    '4★ mehmonxona Qohirada (3 tun)',
                    '4★ resort Sharm el-Sheyhda (4 tun, all-inclusive)',
                    'Barcha transferlar',
                    'Giza piramidalari va Sfinks kirish',
                    "Qohira Milliy muzeyi (Tutanxamon xazinasi)",
                    'Nil bo\'ylab felucca qayiq safari',
                    "Sug'urta",
                ],
                'exclusions': [
                    'E-viza ($25)',
                    'Tushlik va kechki ovqat (Qohirada)',
                    'Shaxsiy xarajatlar',
                    "Diving (Qizil dengiz, ixtiyoriy)",
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'E-viza yoki VOA',
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Qohira. Joylashish", 'description': "Parvoz.", 'activities': [{'time': '08:00', 'activity': 'Parvoz', 'location': 'TAS'}, {'time': '14:00', 'activity': "Qohira aeroporti, transfer", 'location': 'Cairo'}], 'accommodation': '4★ Cairo Hotel', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Giza Piramidalari, Sfinks va Milliy Muzey", 'description': "Tarix safari.", 'activities': [{'time': '09:00', 'activity': "Giza piramidalari va Sfinks", 'location': 'Giza'}, {'time': '14:00', 'activity': "Qohira Milliy muzeyi (Tutanxamon)", 'location': 'Cairo'}], 'accommodation': '4★ Cairo Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Qohira tarixiy markazi — Xon al-Xaliliy bozori", 'description': "Eski Qohira.", 'activities': [{'time': '10:00', 'activity': "Xon al-Xaliliy bozori", 'location': 'Cairo'}, {'time': '14:00', 'activity': "Nil bo'ylab felucca qayiq", 'location': 'Cairo'}], 'accommodation': '4★ Cairo Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Qohira → Sharm el-Sheikh. Parvoz", 'description': "Ichki parvoz.", 'activities': [{'time': '10:00', 'activity': "Qohira → Sharm (ichki parvoz)", 'location': 'Cairo → Sharm'}, {'time': '13:00', 'activity': "Resort, joylashish, plyaj", 'location': 'Sharm el-Sheikh'}], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 5, 'title': "Sharm — Plyaj va Snorkeling", 'description': "Qizil dengiz.", 'activities': [{'time': '09:00', 'activity': 'Plyajda erkin', 'location': 'Sharm'}, {'time': '11:00', 'activity': 'Snorkeling (Qizil dengiz)', 'location': 'Sharm'}], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 6, 'title': "Ras Muhammad Milliy Bog'i", 'description': "Milliy park.", 'activities': [{'time': '09:00', 'activity': "Ras Muhammad milliy bog'i ekskursiyasi", 'location': 'Ras Muhammad'}], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 7, 'title': "Erkin kun — Plyaj yoki Aquapark", 'description': "Erkin.", 'activities': [{'time': '10:00', 'activity': 'Erkin plyaj', 'location': 'Sharm'}], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 8, 'title': "Sharm → Toshkent", 'description': "Xayrlashuv.", 'activities': [{'time': '09:00', 'activity': 'Check-out', 'location': 'Sharm'}, {'time': '13:00', 'activity': 'Parvoz', 'location': 'Sharm → TAS'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 7. BARCELONA ──────────────────────────────────────────────
            {
                'title': "Barcelona — Gaudi Dunyosi & Costa Brava (6 kun / 5 tun)",
                'category': "Yevropa & Madaniyat",
                'country': 'Spain',
                'city': 'Barcelona',
                'destination_name': "Barcelona — Kataloniya Durdonasi",
                'dest_description': "Sagrada Familia, Gaudi me'morchiligi, La Boqueria va Barselona dengiz qirg'og'i.",
                'climate_info': "May-Oktyabr — eng yaxshi (iliq, quruq). Yoz +28-35°C.",
                'visa_info': "Shengen viza (Ispaniya konsulxonasi orqali).",
                'best_months': ['May', 'June', 'September', 'October'],
                'is_popular': False,
                'short_description': "Sagrada Familia, Park Güell, La Boqueria bozori va Barselona qirg'og'i — 6 kunda.",
                'description': (
                    "Barcelona — Gaudi dahosi va Kataloniya madaniyatining poytaxti. "
                    "Sagrada Familia (yarim qurilgan ulkan kafedral), Park Güell, Casa Batlló, "
                    "La Boqueria oziq-ovqat bozori va Barceloneta plyaji. "
                    "Tapas va sangría bilan bezagan kechalar."
                ),
                'duration_days': 6,
                'duration_nights': 5,
                'base_price': 38_000_000,
                'max_group_size': 12,
                'min_group_size': 2,
                'is_featured': False,
                'difficulty': 'easy',
                'tags': ['europe', 'culture', 'architecture', 'beach', 'spain'],
                'languages': ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Barcelona, economy)',
                    '4★ mehmonxona (5 tun, Eixample tumanida)',
                    'Barcha aeroportdan transferlar',
                    "Sagrada Familia, Park Güell, Casa Batlló (skip-the-line)",
                    "Shaxsiy gid (3 kun, o'zbekistonlik)",
                    'Kundalik nonushta',
                    "Sug'urta",
                ],
                'exclusions': [
                    'Shengen viza',
                    'Tushlik va kechki ovqat',
                    'Shaxsiy xaridlar',
                    'Camp Nou ekskursiyasi (ixtiyoriy)',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy)",
                    'Shengen viza (Ispaniya)',
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Barcelona. Joylashish", 'description': "Parvoz.", 'activities': [{'time': '08:00', 'activity': 'Parvoz', 'location': 'TAS'}, {'time': '15:00', 'activity': "El Prat aeroporti, transfer, joylashish", 'location': 'Barcelona'}], 'accommodation': '4★ Eixample', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Sagrada Familia & Park Güell", 'description': "Gaudi dunyosi.", 'activities': [{'time': '09:30', 'activity': "Sagrada Familia (skip-the-line)", 'location': 'Barcelona'}, {'time': '13:00', 'activity': "Park Güell (bron bilan)", 'location': 'Barcelona'}, {'time': '16:00', 'activity': "Gràcia tumani sayri", 'location': 'Barcelona'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Las Ramblas, La Boqueria & Gotik tuman", 'description': "Barselona qalbi.", 'activities': [{'time': '09:30', 'activity': "La Boqueria bozori", 'location': 'Barcelona'}, {'time': '11:00', 'activity': "Las Ramblas sayri", 'location': 'Barcelona'}, {'time': '13:00', 'activity': "Barri Gòtic (Gotik tuman)", 'location': 'Barcelona'}, {'time': '16:00', 'activity': "Casa Batlló", 'location': 'Barcelona'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Barceloneta Plyaji & Montjuïc", 'description': "Plyaj va qal'a.", 'activities': [{'time': '10:00', 'activity': "Barceloneta plyajida erkin", 'location': 'Barcelona'}, {'time': '15:00', 'activity': "Montjuïc qal'asi (kabel-yoyo)", 'location': 'Barcelona'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Erkin kun — Xarid yoki Camp Nou", 'description': "Erkin.", 'activities': [{'time': '10:00', 'activity': "Passeig de Gràcia (dizayn xaridlar)", 'location': 'Barcelona'}], 'accommodation': '4★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 6, 'title': "Barcelona → Toshkent", 'description': "Xayrlashuv.", 'activities': [{'time': '09:00', 'activity': 'Erkin vaqt', 'location': 'Barcelona'}, {'time': '13:00', 'activity': 'Aeroportga transfer', 'location': 'El Prat'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 8. MUALLIFLIK — O'ZBEKISTON GRAND TOUR ───────────────────
            {
                'title': "O'zbekiston Grand Tour — Ipak Yo'li Asrorlarida (10 kun / 9 tun)",
                'category': "Mualliflik Turlari",
                'country': 'Uzbekistan',
                'city': "Toshkent - Samarqand - Buxoro - Xiva",
                'destination_name': "O'zbekiston — Buyuk Ipak Yo'li",
                'dest_description': "Toshkent, Samarqand, Buxoro, Xiva — qadimiy O'zbekistonning to'rtta buyuk shahri.",
                'climate_info': "Mart-May va Sentyabr-Noyabr — eng yaxshi. Yoz +38-40°C.",
                'visa_info': "Ko'p davlatlar fuqarolari uchun vizasiz yoki e-viza.",
                'best_months': ['March', 'April', 'May', 'September', 'October', 'November'],
                'is_popular': True,
                'short_description': "Registon, Bibi-Xonim, Kalon masjid va Ichan Qal'a — O'zbekistonning eng go'zal joylarini VIP darajada kashf eting.",
                'description': (
                    "O'zbekiston Grand Tour — mamlakatimizning 4 ta buyuk shahrini bir safarda. "
                    "Samarqandning Registon maydoni, Bibi-Xonim masjidi, "
                    "Buxoroning Kalon minorasi, Ark qal'asi, "
                    "Xivaning Ichan Qal'asi va Toshkentning zamonaviy ko'rinishi — "
                    "bularni VIP transport, premium mehmonxonalar va tajribali gid bilan o'ting."
                ),
                'duration_days': 10,
                'duration_nights': 9,
                'base_price': 9_800_000,
                'max_group_size': 16,
                'min_group_size': 4,
                'is_featured': True,
                'difficulty': 'easy',
                'tags': ['uzbekistan', 'silk-road', 'culture', 'history', 'heritage', 'vip'],
                'languages': ['uz', 'ru', 'en'],
                'inclusions': [
                    'Barcha ichki transferlar (komfort avtobus / tezyurar poyezd)',
                    'Premium boutique mehmonxonalar (4-5★, 9 tun)',
                    'Barcha kirish chiptalar (Registon, Bibi-Xonim, Kalon, Ichan Qal\'a)',
                    "Tajribali o'zbek tilida gid (10 kun)",
                    'Kundalik nonushta + 5 ta milliy ovqat kechkisi',
                    'Paxta va zarhal mahsulotlardan sovg\'a seti',
                    "Sug'urta",
                ],
                'exclusions': [
                    "Toshkentga chipta (agar xorijdan kelsa)",
                    'Ixtiyoriy masterclass va hunarmandchilik darslar',
                    'Shaxsiy xaridlar',
                ],
                'requirements': [
                    'Pasport (kamida 3 oy)',
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent. Kelish va Shahar Sayri", 'description': "Toshkentga kelish, Chorus, Yunusobod.", 'activities': [{'time': '12:00', 'activity': 'Mehmonxonaga joylashish', 'location': 'Toshkent'}, {'time': '14:00', 'activity': "Xo'ja Ahror jome masjidi", 'location': 'Toshkent'}, {'time': '16:00', 'activity': "Temur hiyoboni va davlat muzeyi", 'location': 'Toshkent'}, {'time': '19:00', 'activity': "Milliy taomlar kechkisi", 'location': 'Toshkent'}], 'accommodation': "Lotte Hotel Toshkent 5★", 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Toshkent — Eski Shahar va Chorsu", 'description': "Toshkentning tarixi.", 'activities': [{'time': '09:00', 'activity': "Xast Imom majmuasi", 'location': 'Toshkent'}, {'time': '11:00', 'activity': "Chorsu bozori", 'location': 'Toshkent'}, {'time': '14:00', 'activity': "Toshkent metro (tarixiy bekatlar)", 'location': 'Toshkent'}], 'accommodation': "Lotte Hotel 5★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Toshkent → Samarqand (Afrosiyob)", 'description': "Tezyurar poyezd bilan Samarqand.", 'activities': [{'time': '08:00', 'activity': "Afrosiyob tezyurar poyezd (2.5 soat)", 'location': 'Toshkent → Samarqand'}, {'time': '11:30', 'activity': "Registon maydoni", 'location': 'Samarqand'}, {'time': '14:00', 'activity': "Sherdor va Tillakori madrasalari", 'location': 'Samarqand'}], 'accommodation': "Registan Plaza Hotel 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 4, 'title': "Samarqand — Bibi-Xonim, Shahi-Zinda, Go'ri Amir", 'description': "Samarqand tarixi.", 'activities': [{'time': '09:00', 'activity': "Bibi-Xonim masjidi", 'location': 'Samarqand'}, {'time': '11:00', 'activity': "Shahi-Zinda yodgorlik majmuasi", 'location': 'Samarqand'}, {'time': '14:00', 'activity': "Go'ri Amir maqbarasi (Temur)", 'location': 'Samarqand'}, {'time': '16:00', 'activity': "Ulug'bek rasadxonasi", 'location': 'Samarqand'}], 'accommodation': "Registan Plaza Hotel 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Samarqand → Buxoro", 'description': "Buxoroga yo'l.", 'activities': [{'time': '09:00', 'activity': "Samarqand → Buxoro (avtobus, 3 soat)", 'location': 'Yo\'l'}, {'time': '13:00', 'activity': "Buxoro — Ark qal'asi", 'location': 'Buxoro'}, {'time': '15:00', 'activity': "Kalon masjid va minorasi", 'location': 'Buxoro'}], 'accommodation': "Malika Bukhara Hotel 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 6, 'title': "Buxoro — Naqshband, Chor-Minor, Eski Shahar", 'description': "Buxoro tarixi.", 'activities': [{'time': '09:00', 'activity': "Bahouddin Naqshband majmuasi", 'location': 'Buxoro'}, {'time': '11:00', 'activity': "Chor-Minor masjidi", 'location': 'Buxoro'}, {'time': '14:00', 'activity': "Buxoro eski shahar sayri va xarid", 'location': 'Buxoro'}], 'accommodation': "Malika Bukhara Hotel 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 7, 'title': "Buxoro → Xiva", 'description': "Xivaga yo'l.", 'activities': [{'time': '08:00', 'activity': "Buxoro → Xiva (avtobus, 5-6 soat)", 'location': 'Yo\'l'}, {'time': '15:00', 'activity': "Xiva — Ichan Qal'aga kirish", 'location': 'Xiva'}, {'time': '17:00', 'activity': "Islam Xoja minorasi", 'location': 'Xiva'}], 'accommodation': "Malika Khiva Hotel 4★", 'meals': {'breakfast': True, 'lunch': True, 'dinner': False}},
                    {'day': 8, 'title': "Xiva — Ichan Qal'a Sayri", 'description': "Xivaning qadimiy shahar.", 'activities': [{'time': '09:00', 'activity': "Kalta Minor", 'location': 'Xiva'}, {'time': '10:30', 'activity': "Pahlavon Mahmud maqbarasi", 'location': 'Xiva'}, {'time': '13:00', 'activity': "Ichan Qal'a bozori va xarid", 'location': 'Xiva'}, {'time': '15:00', 'activity': "Kuhna Ark (qirollik qasri)", 'location': 'Xiva'}], 'accommodation': "Malika Khiva Hotel 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 9, 'title': "Xiva → Toshkent (parvoz)", 'description': "Toshkentga qaytish.", 'activities': [{'time': '09:00', 'activity': "Xiva aeroportiga transfer", 'location': 'Xiva'}, {'time': '11:00', 'activity': "Xiva → Toshkent parvozi", 'location': 'Xiva → TAS'}, {'time': '13:00', 'activity': "Toshkentda joylashish", 'location': 'Toshkent'}, {'time': '19:00', 'activity': "Xayrlashuv kechkisi", 'location': 'Toshkent'}], 'accommodation': "Lotte Hotel Toshkent 5★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 10, 'title': "Toshkent. Xayrlashuv", 'description': "Ketish.", 'activities': [{'time': '10:00', 'activity': "Erkin vaqt va xarid", 'location': 'Toshkent'}, {'time': '14:00', 'activity': "Aeroportga transfer", 'location': 'Toshkent'}], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },
        ]
