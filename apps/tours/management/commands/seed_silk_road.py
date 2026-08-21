"""
Management command: seed_silk_road

Silk Road Premium Tours organizatsiyasini yaratadi (agar yo'q bo'lsa)
va barcha premium tur paketlarini qo'shadi.

Ishlatish:
    python manage.py seed_silk_road
    python manage.py seed_silk_road --dry-run
    python manage.py seed_silk_road --reset-packages   (mavjud paketlarni o'chirib qayta yaratadi)
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

SILK_ROAD_NAME = 'Silk Road Premium Tours'


class Command(BaseCommand):
    help = "Silk Road Premium Tours organizatsiyasi va tur paketlarini yaratadi"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="O'zgartirmasdan faqat ko'rsatadi")
        parser.add_argument('--reset-packages', action='store_true',
                            help="Mavjud paketlarni o'chirib qayta yaratadi")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reset   = options['reset_packages']

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Hech narsa o\'zgarmaydi\n'))

        self.stdout.write(self.style.HTTP_INFO('\n[*] Silk Road Premium Tours — seed\n'))

        if not dry_run:
            with transaction.atomic():
                silk, categories = self._ensure_org_and_categories(reset)
                self._seed_packages(silk, categories, dry_run)
        else:
            self.stdout.write('[DRY-RUN] Organizatsiya va paketlar yaratilardi')
            self._seed_packages(None, None, dry_run)

        self.stdout.write(self.style.SUCCESS('\n[OK] Hammasi muvaffaqiyatli bajarildi!'))

    # ──────────────────────────────────────────────────────────────────────────
    def _ensure_org_and_categories(self, reset: bool):
        from django.contrib.auth import get_user_model
        from apps.crm.models import Organization, Branch
        from apps.tours.models import TourCategory

        User = get_user_model()

        # ── Organizatsiya ─────────────────────────────────────────────────────
        silk, org_created = Organization.objects.get_or_create(
            name=SILK_ROAD_NAME,
            defaults={
                'org_type':      'tour_company',
                'business_type': 'travel',
                'description':   'O\'zbekistonning eng premium tur operatori. '
                                 'VIP sayohatlar, eksklyuziv paketlar va shaxsiy xizmat.',
                'is_active':     True,
            }
        )
        if org_created:
            self.stdout.write(self.style.SUCCESS(f'[+] Organization yaratildi: {silk.name}'))
        else:
            self.stdout.write(f'[=] Organization mavjud: {silk.name} ({silk.id})')

        # ── Owner user ────────────────────────────────────────────────────────
        if not silk.owner_id:
            owner, u_created = User.objects.get_or_create(
                phone='+998900000001',
                defaults={
                    'first_name':  'Silk Road',
                    'last_name':   'Director',
                    'role':        'owner_tour',
                    'is_active':   True,
                }
            )
            silk.owner = owner
            silk.save(update_fields=['owner', 'updated_at'])
            if u_created:
                self.stdout.write(f'[+] Owner user yaratildi: {owner}')

        # ── Branch ───────────────────────────────────────────────────────────
        branch, _ = Branch.objects.get_or_create(
            organization=silk,
            name='Bosh Ofis',
            defaults={
                'address': 'Toshkent, Chilonzor tumani',
                'city':    'Toshkent',
                'country': 'Uzbekistan',
                'is_active': True,
            }
        )

        # ── Kategoriyalar ─────────────────────────────────────────────────────
        cats_data = [
            ('Dengiz va VIP Ta\'til',  'beach',    '', 1),
            ('Ekzotika & Osiyo',       'exotic',   '', 2),
            ('Madaniy-Tarixiy',        'culture',  '', 3),
            ('Mualliflik Turlari',     'author',   '', 4),
            ('Yevropa & Madaniyat',    'europe',   '', 5),
        ]
        cats = {}
        for name, slug_hint, icon, order in cats_data:
            cat, created = TourCategory.objects.get_or_create(
                name=name,
                defaults={
                    'icon':       icon,
                    'is_active':  True,
                    'sort_order': order,
                }
            )
            cats[name] = cat
            if created:
                self.stdout.write(f'[+] Kategoriya yaratildi: {name}')

        # ── Reset ─────────────────────────────────────────────────────────────
        if reset:
            from apps.tours.models import TourPackage
            deleted, _ = TourPackage.objects.filter(organization=silk).delete()
            self.stdout.write(self.style.WARNING(f'[!] {deleted} ta mavjud paket o\'chirildi (--reset-packages)'))

        return silk, cats

    # ──────────────────────────────────────────────────────────────────────────
    def _seed_packages(self, silk, cats, dry_run: bool):
        from apps.tours.models import (
            TourDestination, TourPackage,
            TourItineraryDay, TourAvailability,
        )

        packages_data = self._packages_data()
        created = skipped = 0

        for data in packages_data:
            title = data['title']

            if dry_run:
                self.stdout.write(f'  [DRY-RUN] Qo\'shilar edi: {title}')
                created += 1
                continue

            if TourPackage.objects.filter(organization=silk, title=title).exists():
                self.stdout.write(f'  [SKIP] Mavjud: {title}')
                skipped += 1
                continue

            cat_name = data['category']
            category = cats.get(cat_name)
            if not category:
                self.stdout.write(self.style.WARNING(f'  [WARN] Kategoriya topilmadi: {cat_name}'))
                skipped += 1
                continue

            with transaction.atomic():
                # TourDestination
                dest, _ = TourDestination.objects.get_or_create(
                    organization=silk,
                    country=data['country'],
                    city=data.get('city', ''),
                    defaults={
                        'name':        data['destination_name'],
                        'description': data.get('dest_description', ''),
                        'climate_info': data.get('climate_info', ''),
                        'visa_info':   data.get('visa_info', ''),
                        'best_months': data.get('best_months', []),
                        'is_active':   True,
                        'is_popular':  data.get('is_popular', False),
                    }
                )

                # TourPackage
                pkg = TourPackage.objects.create(
                    organization     = silk,
                    title            = title,
                    category         = category,
                    destination      = dest,
                    short_description= data['short_description'],
                    description      = data['description'],
                    duration_days    = data['duration_days'],
                    duration_nights  = data.get('duration_nights', data['duration_days'] - 1),
                    base_price       = Decimal(str(data['base_price'])),
                    currency         = 'UZS',
                    price_per        = 'person',
                    max_group_size   = data.get('max_group_size', 15),
                    min_group_size   = data.get('min_group_size', 2),
                    is_active        = True,
                    is_featured      = data.get('is_featured', False),
                    inclusions       = data.get('inclusions', []),
                    exclusions       = data.get('exclusions', []),
                    requirements     = data.get('requirements', []),
                    difficulty_level = data.get('difficulty', 'easy'),
                    tags             = data.get('tags', []),
                    languages_offered= data.get('languages', ['uz', 'ru']),
                )

                # TourItineraryDay
                for day in data.get('itinerary', []):
                    TourItineraryDay.objects.create(
                        package      = pkg,
                        day_number   = day['day'],
                        title        = day['title'],
                        description  = day.get('description', ''),
                        activities   = day.get('activities', []),
                        accommodation= day.get('accommodation', ''),
                        meals        = day.get('meals', {'breakfast': True, 'lunch': False, 'dinner': True}),
                    )

                # TourAvailability — 4 ta sana (1 oydan boshlab)
                base_date = timezone.now().date().replace(day=1)
                for i in range(4):
                    dep = base_date + timedelta(days=30 * (i + 1))
                    TourAvailability.objects.create(
                        package        = pkg,
                        departure_date = dep,
                        return_date    = dep + timedelta(days=data['duration_days']),
                        total_seats    = data.get('max_group_size', 15),
                        booked_seats   = 0,
                        status         = 'open',
                    )

            self.stdout.write(self.style.SUCCESS(
                f'  [OK] {title} ({data["duration_days"]} kun | {data["base_price"]:,} UZS)'
            ))
            created += 1

        self.stdout.write(f'\n  Natija: {created} ta qoshildi, {skipped} ta o\'tkazildi')

    # ──────────────────────────────────────────────────────────────────────────
    # PAKETLAR
    # ──────────────────────────────────────────────────────────────────────────
    def _packages_data(self) -> list[dict]:
        return [
            # ─── 1. DUBAI ──────────────────────────────────────────────────
            {
                'title':            'Dubai — Atlantis The Royal & Burj Premium (5 kun / 4 tun)',
                'category':         "Dengiz va VIP Ta'til",
                'country':          'UAE',
                'city':             'Dubai',
                'destination_name': 'Dubai — Zangori Fors Ko\'rfazi',
                'dest_description': 'Burj Khalifa, Palm Jumeirah, luksus xaridlar va desert safari.',
                'climate_info':     'Noyabr-Aprel eng yaxshi mavsim. May-Oktyabr juda issiq (+42C).',
                'visa_info':        "O'zbekiston fuqarolari uchun Dubai viza talab qilinadi (30 kun, online).",
                'best_months':      ['November', 'December', 'January', 'February', 'March'],
                'is_popular':       True,
                'short_description':'Burj Khalifa, Atlantis The Royal va Desert Safari — Dubayning eng yaxshi joylarini VIP darajada kashf eting.',
                'description':      (
                    'Dubai — zamonaviylik, hashamat va arabcha mehmondo\'stlikning markazi. '
                    'Burj Khalifa (148-qavat), Dubai Mall, Palm Jumeirah, '
                    'Atlantis The Royal resort va Desert Safari — '
                    'bularni premium avtobus va shaxsiy gid bilan bitta sayohatda o\'ting.'
                ),
                'duration_days':    5,
                'duration_nights':  4,
                'base_price':       28_000_000,
                'max_group_size':   14,
                'min_group_size':   2,
                'is_featured':      True,
                'difficulty':       'easy',
                'tags':             ['vip', 'beach', 'luxury', 'uae', 'dubai'],
                'languages':        ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Dubai, economy)',
                    '5★ mehmonxona (4 tun, Jumeirah yoki ekvivalent)',
                    'Barcha transferlar (VIP avto)',
                    'Burj Khalifa (148-qavat, At the Top)',
                    'Dubai Mall + Dubai Fountain tomoshasi',
                    'Desert Safari (BBQ kechki ovqat bilan)',
                    'Palm Jumeirah monorail va mini-kruiz',
                    "Sug'urta",
                ],
                'exclusions': [
                    'Dubai viza ($45-90)',
                    'Tushlik va kechki ovqat (Desert Safaridan tashqari)',
                    'Shaxsiy xaridlar',
                    'Aquaventure park (ixtiyoriy)',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    'Dubai visa (oldindan rasmiylashtiriladi)',
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Dubai. Joylashish",
                     'description': "Parvoz, joylashish, Dubai Marina kechki sayri.",
                     'activities': [
                         {'time': '06:00', 'activity': "Toshkentdan parvoz", 'location': 'TAS'},
                         {'time': '08:30', 'activity': "Dubai aeroportiga qo'nish", 'location': 'DXB'},
                         {'time': '10:00', 'activity': "Mehmonxonaga transfer va joylashish", 'location': 'Dubai'},
                         {'time': '20:00', 'activity': "Dubai Marina kechki sayri", 'location': 'Dubai Marina'},
                     ], 'accommodation': 'JW Marriott Marina 5★', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Burj Khalifa, Dubai Mall & Fountain",
                     'description': "Dunyoning eng baland binosi va Dubai Fountain show.",
                     'activities': [
                         {'time': '10:00', 'activity': "Dubai Mall (xarid va gezmish)", 'location': 'Downtown Dubai'},
                         {'time': '14:00', 'activity': "Burj Khalifa — At the Top (148-qavat)", 'location': 'Downtown Dubai'},
                         {'time': '18:00', 'activity': "Dubai Fountain show (kechki)", 'location': 'Burj Lake'},
                     ], 'accommodation': 'JW Marriott Marina 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Palm Jumeirah & Desert Safari",
                     'description': "Palm Jumeirah va Sahara cho'l safarisi.",
                     'activities': [
                         {'time': '10:00', 'activity': "Palm Jumeirah monorail va Atlantis tomoshasi", 'location': 'Palm Jumeirah'},
                         {'time': '16:00', 'activity': "Desert Safari (dune bashing, BBQ kechki ovqat)", 'location': 'Dubai Desert'},
                     ], 'accommodation': 'JW Marriott Marina 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 4, 'title': "Gold Souk, Spice Souk va Old Dubai",
                     'description': "Eski Dubai — tarix va bozor.",
                     'activities': [
                         {'time': '09:30', 'activity': "Gold Souk (oltin bozori)", 'location': 'Deira'},
                         {'time': '11:00', 'activity': "Spice Souk (ziravorlar bozori)", 'location': 'Deira'},
                         {'time': '13:00', 'activity': "Dubai Creek — abra qayiq safari", 'location': 'Dubai Creek'},
                         {'time': '15:00', 'activity': "Al Fahidi tarixiy tumani", 'location': 'Al Fahidi'},
                     ], 'accommodation': 'JW Marriott Marina 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Dubai → Toshkent. Xayrlashuv",
                     'description': "Erkin vaqt, aeroportga transfer.",
                     'activities': [
                         {'time': '09:00', 'activity': "Erkin vaqt / so'nggi xaridlar", 'location': 'Dubai'},
                         {'time': '13:00', 'activity': "Aeroportga transfer va parvoz", 'location': 'DXB'},
                     ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 2. ANTALYA ────────────────────────────────────────────────
            {
                'title':            'Antalya — Maxx Royal Belek Ultra All-Inclusive (7 kun / 6 tun)',
                'category':         "Dengiz va VIP Ta'til",
                'country':          'Turkey',
                'city':             'Antalya',
                'destination_name': 'Antalya — Turquoise Coast Jannat',
                'dest_description': 'Toshbaqalar plyaji, qadimiy Perge, Aspendos va Toros tog\'lari.',
                'climate_info':     'May-Oktyabr — plyaj mavsumi. Iyun-Avgust eng issiq (+35C).',
                'visa_info':        "O'zbekiston fuqarolari uchun e-viza ($25, online 3-5 kun) yoki chegara vizasi.",
                'best_months':      ['May', 'June', 'July', 'August', 'September', 'October'],
                'is_popular':       True,
                'short_description':"Ko'k dengiz, qumloq plyajlar, all-inclusive 5★ resort va Türkiye gastronomiyas.",
                'description':      (
                    'Antalya — Turk Rivierasining marvaridi. '
                    'Maxx Royal Belek resortida ultra all-inclusive, '
                    'shaffof dengiz, infinity pool va VIP xizmat. '
                    'Perge va Aspendos qadimiy shaharlari, Duden sharsharasi ham shu sayohatda.'
                ),
                'duration_days':    7,
                'duration_nights':  6,
                'base_price':       32_000_000,
                'max_group_size':   16,
                'min_group_size':   2,
                'is_featured':      True,
                'difficulty':       'easy',
                'tags':             ['beach', 'all-inclusive', 'family', 'turkey', 'pool'],
                'languages':        ['uz', 'ru'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Antalya, charter/economy)',
                    '5★ resort (6 tun, Ultra All-Inclusive)',
                    'Aeroport ↔ resort transfer',
                    '3 mahal ovqat + snack + ichimliklar (24/7)',
                    'Cheksiz basseyn, aquapark, beach sport',
                    'Duden sharsharasi ekskursiyasi',
                    "Sug'urta",
                ],
                'exclusions': [
                    'E-viza yoki chegara vizasi ($25)',
                    'Spa va massaj xizmatlari',
                    'Shaxsiy xaridlar',
                    'Ixtiyoriy parasailing, jet-ski',
                ],
                'requirements': [
                    "Pasport (kamida 6 oy amal qilishi kerak)",
                    "E-viza yoki chegara vizasi",
                ],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Antalya. Joylashish", 'description': "Parvoz va resort.",
                     'activities': [{'time': '08:00', 'activity': "Toshkentdan parvoz", 'location': 'TAS'},
                                    {'time': '11:00', 'activity': "Antalya aeroporti, transfer, resort", 'location': 'Antalya'},
                                    {'time': '14:00', 'activity': "Joylashish va beach", 'location': 'Resort'}],
                     'accommodation': 'Maxx Royal Belek 5★ Ultra-AI', 'meals': {'breakfast': False, 'lunch': True, 'dinner': True}},
                    {'day': 2, 'title': "Plyaj, Basseyn, Aquapark",
                     'description': "Erkin dam olish kuni.",
                     'activities': [{'time': '09:00', 'activity': "Plyajda dam olish", 'location': 'Resort'},
                                    {'time': '14:00', 'activity': "Aquapark", 'location': 'Resort'}],
                     'accommodation': 'Maxx Royal Belek 5★', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 3, 'title': "Perge va Aspendos qadimiy shaharlari",
                     'description': "Ekskursiya kuni.",
                     'activities': [{'time': '09:00', 'activity': "Perge qadimiy shahri", 'location': 'Perge'},
                                    {'time': '12:00', 'activity': "Aspendos teatri", 'location': 'Aspendos'},
                                    {'time': '16:00', 'activity': "Qaytish, plyaj", 'location': 'Resort'}],
                     'accommodation': 'Maxx Royal Belek 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 4, 'title': "Duden Sharsharasi & Antalya Shahri",
                     'description': "Shahar sayri.",
                     'activities': [{'time': '10:00', 'activity': "Duden sharsharasi", 'location': 'Antalya'},
                                    {'time': '13:00', 'activity': "Antalya eski shahar (Kaleiçi)", 'location': 'Antalya'},
                                    {'time': '16:00', 'activity': "Lara plyaji", 'location': 'Antalya'}],
                     'accommodation': 'Maxx Royal Belek 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 5, 'title': "Erkin kun — Plyaj va Sport",
                     'description': "Erkin dam olish.",
                     'activities': [{'time': '10:00', 'activity': "Erkin plyaj va sport", 'location': 'Resort'}],
                     'accommodation': 'Maxx Royal Belek 5★', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 6, 'title': "Erkin kun — Spa yoki Bazaar",
                     'description': "So'nggi dam olish kuni.",
                     'activities': [{'time': '10:00', 'activity': "Spa yoki Belek bazaari", 'location': 'Resort/Belek'}],
                     'accommodation': 'Maxx Royal Belek 5★', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 7, 'title': "Antalya → Toshkent. Xayrlashuv",
                     'description': "Check-out va parvoz.",
                     'activities': [{'time': '09:00', 'activity': "Check-out, transfer, parvoz", 'location': 'Antalya'}],
                     'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 3. ISTANBUL ───────────────────────────────────────────────
            {
                'title':            "Istanbul — Ikki Qit'a Shahri VIP Sayohati (5 kun / 4 tun)",
                'category':         'Madaniy-Tarixiy',
                'country':          'Turkey',
                'city':             'Istanbul',
                'destination_name': "Istanbul — Ikki Qit'a Shahri",
                'dest_description': "Yevropa va Osiyo tutashgan buyuk shahar — tarix, madaniyat va zamonaviylik.",
                'climate_info':     'Iyun-Sentabr — iliq, quruq. Aprel-May — maftunkor bahor.',
                'visa_info':        "E-viza (online, $25) yoki chegara vizasi.",
                'best_months':      ['April', 'May', 'September', 'October'],
                'is_popular':       True,
                'short_description':"Ayasofiya, Bosphorus, Topkapi — Istanbul yodgorliklarini shaxsiy gid va VIP transferlar bilan kashf eting.",
                'description':      (
                    "Istanbul — dunyoning eng qadimiy va go'zal shaharlaridan biri. "
                    "Ayasofiya, Topkapi saroyi, Kapalı Çarşı va Bosphorus kechki kruizi — "
                    "bularning hammasi premium mehmonxona va shaxsiy gid bilan."
                ),
                'duration_days':    5,
                'duration_nights':  4,
                'base_price':       18_500_000,
                'max_group_size':   12,
                'min_group_size':   2,
                'is_featured':      True,
                'difficulty':       'easy',
                'tags':             ['vip', 'culture', 'history', 'europe', 'turkey'],
                'languages':        ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Istanbul, economy)',
                    '5★ mehmonxona (4 tun)',
                    "Barcha transferlar (VIP avto)",
                    "Shaxsiy o'zbek-rus tilida gid",
                    'Ayasofiya, Topkapi, Dolmabahçe ziyoratlari',
                    'Bosphorus kechki kruizi',
                    'Kundalik nonushta',
                    "Sug'urta",
                ],
                'exclusions': [
                    'Viza ($25)',
                    'Tushlik va kechki ovqat',
                    'Shaxsiy xaridlar',
                ],
                'requirements': ["Pasport (kamida 6 oy)", 'E-viza'],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Istanbul. Joylashish",
                     'activities': [
                         {'time': '06:00', 'activity': "Toshkentdan parvoz", 'location': 'TAS'},
                         {'time': '11:30', 'activity': "Istanbul aeroporti, transfer", 'location': 'Istanbul'},
                         {'time': '19:00', 'activity': "Sultanahmet maydonini ko'rish", 'location': 'Sultanahmet'},
                     ], 'accommodation': '5★ Istanbul Hotel', 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Ayasofiya, Topkapi, Ko'k Masjid",
                     'activities': [
                         {'time': '09:00', 'activity': "Ayasofiya", 'location': 'Sultanahmet'},
                         {'time': '11:00', 'activity': "Topkapi saroyi va Harem", 'location': 'Sultanahmet'},
                         {'time': '15:00', 'activity': "Ko'k Masjid", 'location': 'Sultanahmet'},
                         {'time': '17:00', 'activity': "Kapalı Çarşı (Qopqali bozor)", 'location': 'Beyazıt'},
                     ], 'accommodation': '5★ Istanbul Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Dolmabahçe & Bosphorus Kruizi",
                     'activities': [
                         {'time': '10:00', 'activity': "Dolmabahçe saroyi", 'location': 'Beşiktaş'},
                         {'time': '18:30', 'activity': "Bosphorus kechki kruizi (2 soat)", 'location': 'Eminönü'},
                     ], 'accommodation': '5★ Istanbul Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 4, 'title': "Galata, Taksim, Zamonaviy Istanbul",
                     'activities': [
                         {'time': '10:00', 'activity': "Galata minorasi panoramasi", 'location': 'Galata'},
                         {'time': '12:00', 'activity': "İstiklal ko'chasi", 'location': 'Beyoğlu'},
                         {'time': '15:00', 'activity': "Mısır Çarşısı (Ziravorlar bozori)", 'location': 'Eminönü'},
                     ], 'accommodation': '5★ Istanbul Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Istanbul → Toshkent",
                     'activities': [
                         {'time': '09:00', 'activity': "Erkin vaqt", 'location': 'Istanbul'},
                         {'time': '13:00', 'activity': "Aeroportga transfer, parvoz", 'location': 'Istanbul'},
                     ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 4. PARIJ ──────────────────────────────────────────────────
            {
                'title':            'Parij — Sevgi Shahri Premium Sayohat (7 kun / 6 tun)',
                'category':         "Yevropa & Madaniyat",
                'country':          'France',
                'city':             'Paris',
                'destination_name': "Parij — Yorug'lik Shahri",
                'dest_description': "Eyffel minorasi, Luvr, fashion va gastronomiyanin poytaxti.",
                'climate_info':     'May-Sentabr eng yaxshi. Aprel — gullagan Parij.',
                'visa_info':        "Shengen viza kerak (Fransiya konsulxonasi, 10-15 ish kuni).",
                'best_months':      ['April', 'May', 'June', 'September'],
                'is_popular':       True,
                'short_description':"Eyffel, Luvr, Seine daryosi — Parijning go'zalliklarini VIP darajada kashf eting.",
                'description':      (
                    "Parij — romantika, san'at va madaniyatning ramzi. "
                    "Eyffel minorasi, Luvr muzeyi, Versailles saroyi va Champs-Élysées — "
                    "bularni shaxsiy gid bilan chuqur kashf etish imkoniyati."
                ),
                'duration_days':    7,
                'duration_nights':  6,
                'base_price':       45_000_000,
                'max_group_size':   10,
                'min_group_size':   2,
                'is_featured':      True,
                'difficulty':       'easy',
                'tags':             ['vip', 'europe', 'romance', 'culture', 'luxury'],
                'languages':        ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Parij, business class)',
                    '5★ butik mehmonxona (6 tun, markazda)',
                    "Barcha transferlar (VIP avto)",
                    "Shaxsiy o'zbekistonlik gid",
                    'Luvr, Versailles, Eyffel (lift) kirish',
                    "Seine bo'ylab kechki kruiz",
                    'Kundalik nonushta + 2 ta premium kechki ovqat',
                    "Sug'urta (keng qamrovli)",
                ],
                'exclusions': ['Shengen viza ($80-120)', 'Ko\'pchilik tushlik va kechki ovqatlar', 'Shaxsiy xaridlar'],
                'requirements': ["Pasport (kamida 6 oy)", 'Shengen viza'],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Parij. Joylashish", 'activities': [
                        {'time': '08:00', 'activity': 'Parvoz', 'location': 'TAS'},
                        {'time': '14:00', 'activity': "Parij CDG, joylashish", 'location': 'Paris'},
                        {'time': '19:00', 'activity': "Le Marais kechki sayri", 'location': 'Paris'},
                    ], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Eyffel, Trocadéro, Invalides", 'activities': [
                        {'time': '09:30', 'activity': "Trocadéro — Eyffel panoramasi", 'location': 'Paris'},
                        {'time': '11:00', 'activity': "Eyffel (lift, top)", 'location': 'Paris'},
                        {'time': '18:30', 'activity': "Seine kechki kruizi", 'location': 'Paris'},
                    ], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 3, 'title': "Luvr va Tuileriya bog'i", 'activities': [
                        {'time': '09:00', 'activity': "Luvr (skip-the-line)", 'location': 'Paris'},
                        {'time': '14:00', 'activity': "Tuileriya bog'i", 'location': 'Paris'},
                        {'time': '16:00', 'activity': "Champs-Élysées va Arc de Triomphe", 'location': 'Paris'},
                    ], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Versailles saroyi", 'activities': [
                        {'time': '09:00', 'activity': "Versailles (VIP avto)", 'location': 'Versailles'},
                        {'time': '10:00', 'activity': "Versailles saroyi va bog'i", 'location': 'Versailles'},
                    ], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Montmartre, Sacré-Cœur", 'activities': [
                        {'time': '10:00', 'activity': "Montmartre va Sacré-Cœur", 'location': 'Paris'},
                        {'time': '13:00', 'activity': 'Galeries Lafayette', 'location': 'Paris'},
                    ], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 6, 'title': "Erkin kun", 'activities': [
                        {'time': '10:00', 'activity': "Erkin kun", 'location': 'Paris'},
                    ], 'accommodation': 'Hôtel de Crillon 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 7, 'title': "Parij → Toshkent", 'activities': [
                        {'time': '09:00', 'activity': "Erkin vaqt", 'location': 'Paris'},
                        {'time': '13:00', 'activity': "Aeroportga transfer, parvoz", 'location': 'CDG'},
                    ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 5. MALDIV ─────────────────────────────────────────────────
            {
                'title':            'Maldiv — Okean Jannatida Ultra All-Inclusive (6 kun / 5 tun)',
                'category':         "Dengiz va VIP Ta'til",
                'country':          'Maldives',
                'city':             'Male',
                'destination_name': 'Maldiv — Hind Okeani Jannat Orollari',
                'dest_description': "Ko'k suv, oq qumloq va dengiz osti dunyosi.",
                'climate_info':     "Noyabr-Aprel — quruq mavsim, eng yaxshi vaqt.",
                'visa_info':        "Vizasiz (30 kun). Pasport va hotel bron kerak.",
                'best_months':      ['November', 'December', 'January', 'February', 'March'],
                'is_popular':       True,
                'short_description':"Maldivdagi shaffof suv villa (overwater bungalow), diving va sunset kruiz.",
                'description':      (
                    "Maldiv — dengiz ustidagi villa, coral reef diving, "
                    "sunset kruiz va ultra all-inclusive xizmat."
                ),
                'duration_days':    6,
                'duration_nights':  5,
                'base_price':       52_000_000,
                'max_group_size':   8,
                'min_group_size':   2,
                'is_featured':      True,
                'difficulty':       'easy',
                'tags':             ['beach', 'luxury', 'honeymoon', 'diving', 'vip'],
                'languages':        ['uz', 'ru', 'en'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Malé)',
                    "Speedboat transfer (Malé ↔ resort)",
                    'Overwater Bungalow (5★ resort, 5 tun)',
                    'Ultra All-Inclusive (3 mahal ovqat + ichimliklar)',
                    '2 ta Snorkeling ekskursiyasi',
                    'Sunset dhoni kruizi',
                    "Sug'urta",
                ],
                'exclusions': ['Scuba diving', 'Spa xizmatlari', 'Shaxsiy xarajatlar'],
                'requirements': ["Pasport (kamida 6 oy)", 'Hotel confirmation'],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Malé → Resort", 'activities': [
                        {'time': '07:00', 'activity': 'Parvoz', 'location': 'TAS'},
                        {'time': '17:00', 'activity': "Malé aeroporti", 'location': 'Malé'},
                        {'time': '18:30', 'activity': 'Speedboat resort', 'location': 'Ocean'},
                        {'time': '20:00', 'activity': 'Joylashish, xush kelibsiz kokteil', 'location': 'Resort'},
                    ], 'accommodation': 'Overwater Bungalow 5★', 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Plyaj va Snorkeling — Coral Reef", 'activities': [
                        {'time': '09:00', 'activity': 'Plyajda erkin vaqt', 'location': 'Resort'},
                        {'time': '11:00', 'activity': 'Snorkeling (coral reef)', 'location': 'Ocean'},
                        {'time': '18:00', 'activity': 'Sunset dhoni kruizi', 'location': 'Ocean'},
                    ], 'accommodation': 'Overwater Bungalow 5★', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 3, 'title': "Dengiz osti safari", 'activities': [
                        {'time': '10:00', 'activity': 'Semi-submarine ekskursiyasi', 'location': 'Ocean'},
                        {'time': '14:00', 'activity': 'Erkin plyaj va basseyn', 'location': 'Resort'},
                    ], 'accommodation': 'Overwater Bungalow 5★', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 4, 'title': "Malé shahar (ixtiyoriy)", 'activities': [
                        {'time': '10:00', 'activity': "Malé shahri speedboat", 'location': 'Malé'},
                        {'time': '15:00', 'activity': 'Qaytish va erkin kechki', 'location': 'Resort'},
                    ], 'accommodation': 'Overwater Bungalow 5★', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 5, 'title': "Erkin kun — Plyaj va Sunset Kruiz", 'activities': [
                        {'time': '10:00', 'activity': 'Erkin plyaj', 'location': 'Resort'},
                        {'time': '19:00', 'activity': "So'nggi kechki kruiz", 'location': 'Ocean'},
                    ], 'accommodation': 'Overwater Bungalow 5★', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 6, 'title': "Resort → Malé → Toshkent", 'activities': [
                        {'time': '08:00', 'activity': 'Check-out, speedboat, parvoz', 'location': 'Resort → TAS'},
                    ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 6. BALI ───────────────────────────────────────────────────
            {
                'title':            'Bali — Xudolar Oroli Ekzotik Safari (8 kun / 7 tun)',
                'category':         'Ekzotika & Osiyo',
                'country':          'Indonesia',
                'city':             'Bali',
                'destination_name': 'Bali — Indoneziya Ekzotikasi',
                'dest_description': "Guruch dalalaari, ibodatxonalar, tropik plyajlar va Bali madaniyati.",
                'climate_info':     "Aprel-Oktyabr — quruq mavsim, eng yaxshi.",
                'visa_info':        "Visa on Arrival (VOA) — $35, chegara nazoratida. 30 kun.",
                'best_months':      ['April', 'May', 'June', 'July', 'August', 'September'],
                'is_popular':       True,
                'short_description':"Ubud guruch dalalaari, Tanah Lot ibodatxonasi, Seminyak plyaji.",
                'description':      "Bali — tabiat, ma'naviyat va hashamatning uyg'unligi.",
                'duration_days':    8,
                'duration_nights':  7,
                'base_price':       26_000_000,
                'max_group_size':   14,
                'min_group_size':   2,
                'is_featured':      False,
                'difficulty':       'easy',
                'tags':             ['beach', 'exotic', 'asia', 'culture', 'nature'],
                'languages':        ['uz', 'ru'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Denpasar)',
                    'Villa/mehmonxona (4★, 7 tun, basseynli)',
                    'Barcha transferlar',
                    '4 ta ekskursiya (Ubud, Tanah Lot, Kintamani, Uluwatu)',
                    "Kecak raqs shousi",
                    'Kundalik nonushta',
                    "Sug'urta",
                ],
                'exclusions': ['VOA viza ($35)', 'Diving va surfing', 'Tushlik va kechki ovqat'],
                'requirements': ["Pasport (kamida 6 oy)", 'VOA chegara nazoratida'],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Bali. Joylashish", 'activities': [
                        {'time': '08:00', 'activity': 'Parvoz', 'location': 'TAS'},
                        {'time': '20:00', 'activity': "Denpasar, VOA, transfer, joylashish", 'location': 'Bali'},
                    ], 'accommodation': '4★ Villa Seminyak', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Ubud — Guruch Dalalaari va Maymunlar O'rmoni", 'activities': [
                        {'time': '09:00', 'activity': "Tegallalang guruch dalalaari", 'location': 'Ubud'},
                        {'time': '11:00', 'activity': "Maymunlar o'rmoni", 'location': 'Ubud'},
                    ], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Tanah Lot & Uluwatu Ibodatxonalari", 'activities': [
                        {'time': '09:00', 'activity': 'Tanah Lot ibodatxonasi', 'location': 'Bali'},
                        {'time': '16:00', 'activity': 'Uluwatu cliff ibodatxonasi', 'location': 'Bali'},
                        {'time': '18:30', 'activity': "Kecak va olov raqs shousi", 'location': 'Uluwatu'},
                    ], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Kintamani Vulqoni", 'activities': [
                        {'time': '08:00', 'activity': "Batur vulqoni panoramasi", 'location': 'Kintamani'},
                        {'time': '13:00', 'activity': "Tirta Empul ibodatxonasi", 'location': 'Bali'},
                    ], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': True, 'dinner': False}},
                    {'day': 5, 'title': "Seminyak Plyaji", 'activities': [
                        {'time': '10:00', 'activity': "Seminyak plyajida erkin", 'location': 'Seminyak'},
                        {'time': '18:00', 'activity': "Kuta sunset", 'location': 'Kuta'},
                    ], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 6, 'title': "Nusa Penida (ixtiyoriy)", 'activities': [
                        {'time': '07:00', 'activity': "Nusa Penida speedboat", 'location': 'Nusa Penida'},
                        {'time': '10:00', 'activity': "Kelingking Beach panoramasi", 'location': 'Nusa Penida'},
                    ], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 7, 'title': "Erkin kun — Spa yoki Xarid", 'activities': [
                        {'time': '10:00', 'activity': 'Balinese spa massaj', 'location': 'Seminyak'},
                    ], 'accommodation': '4★ Villa', 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 8, 'title': "Bali → Toshkent", 'activities': [
                        {'time': '13:00', 'activity': "Aeroportga transfer, parvoz", 'location': 'Denpasar'},
                    ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 7. MISR ───────────────────────────────────────────────────
            {
                'title':            "Misr — Fir'avnlar Yurti & Qizil Dengiz (8 kun / 7 tun)",
                'category':         'Madaniy-Tarixiy',
                'country':          'Egypt',
                'city':             'Cairo',
                'destination_name': 'Misr — Qadimiy Sivilizatsiya Yurti',
                'dest_description': "Piramidalar, Nil daryosi, Luxor ibodatxonalari va Qizil dengiz.",
                'climate_info':     "Oktyabr-Aprel — eng yaxshi. May-Sentabr juda issiq.",
                'visa_info':        "E-viza online ($25) yoki Visa on Arrival.",
                'best_months':      ['October', 'November', 'December', 'January', 'February', 'March'],
                'is_popular':       False,
                'short_description':"Giza piramidalari, Sfinks va Sharm el-Sheikh plyajlari — tarix va dam olish bitta safarda.",
                'description':      (
                    "Misr — inson sivilizatsiyasining beshigi. "
                    "Giza piramidalari, Qohira Milliy muzeyi va Sharm el-Sheikh Qizil dengiz plyajlari."
                ),
                'duration_days':    8,
                'duration_nights':  7,
                'base_price':       22_000_000,
                'max_group_size':   14,
                'min_group_size':   2,
                'is_featured':      False,
                'difficulty':       'easy',
                'tags':             ['history', 'culture', 'beach', 'egypt', 'pyramids'],
                'languages':        ['uz', 'ru'],
                'inclusions': [
                    'Avia chipta (Toshkent ↔ Qohira)',
                    '4★ Qohira mehmonxona (3 tun)',
                    '4★ Sharm el-Sheikh resort (4 tun, all-inclusive)',
                    'Barcha transferlar',
                    'Giza piramidalari va Sfinks kirish',
                    "Qohira Milliy muzeyi",
                    "Nil bo'ylab felucca qayiq safari",
                    "Sug'urta",
                ],
                'exclusions': ['E-viza ($25)', 'Tushlik (Qohirada)', 'Diving', 'Shaxsiy xarajatlar'],
                'requirements': ["Pasport (kamida 6 oy)", 'E-viza yoki VOA'],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Qohira", 'activities': [
                        {'time': '08:00', 'activity': 'Parvoz', 'location': 'TAS'},
                        {'time': '14:00', 'activity': "Qohira, transfer, joylashish", 'location': 'Cairo'},
                    ], 'accommodation': '4★ Cairo Hotel', 'meals': {'breakfast': False, 'lunch': False, 'dinner': False}},
                    {'day': 2, 'title': "Giza Piramidalari va Milliy Muzey", 'activities': [
                        {'time': '09:00', 'activity': "Giza piramidalari va Sfinks", 'location': 'Giza'},
                        {'time': '14:00', 'activity': "Qohira Milliy muzeyi (Tutanxamon)", 'location': 'Cairo'},
                    ], 'accommodation': '4★ Cairo Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Xon al-Xaliliy bozori va Nil safari", 'activities': [
                        {'time': '10:00', 'activity': "Xon al-Xaliliy bozori", 'location': 'Cairo'},
                        {'time': '14:00', 'activity': "Nil bo'ylab felucca qayiq", 'location': 'Cairo'},
                    ], 'accommodation': '4★ Cairo Hotel', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 4, 'title': "Qohira → Sharm el-Sheikh", 'activities': [
                        {'time': '10:00', 'activity': "Ichki parvoz Sharmga", 'location': 'Cairo → Sharm'},
                        {'time': '13:00', 'activity': "Resort, joylashish, plyaj", 'location': 'Sharm'},
                    ], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 5, 'title': "Sharm — Plyaj va Snorkeling", 'activities': [
                        {'time': '09:00', 'activity': 'Plyaj va snorkeling', 'location': 'Sharm'},
                    ], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 6, 'title': "Ras Muhammad Milliy Bog'i", 'activities': [
                        {'time': '09:00', 'activity': "Ras Muhammad ekskursiyasi", 'location': 'Ras Muhammad'},
                    ], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 7, 'title': "Erkin kun", 'activities': [
                        {'time': '10:00', 'activity': 'Erkin plyaj', 'location': 'Sharm'},
                    ], 'accommodation': '4★ All-Inclusive Resort', 'meals': {'breakfast': True, 'lunch': True, 'dinner': True}},
                    {'day': 8, 'title': "Sharm → Toshkent", 'activities': [
                        {'time': '09:00', 'activity': 'Check-out, parvoz', 'location': 'Sharm → TAS'},
                    ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 8. O'ZBEKISTON GRAND TOUR ─────────────────────────────────
            {
                'title':            "O'zbekiston Grand Tour — Ipak Yo'li Asrorlarida (10 kun / 9 tun)",
                'category':         'Mualliflik Turlari',
                'country':          'Uzbekistan',
                'city':             "Toshkent-Samarqand-Buxoro-Xiva",
                'destination_name': "O'zbekiston — Buyuk Ipak Yo'li",
                'dest_description': "Toshkent, Samarqand, Buxoro, Xiva — O'zbekistonning to'rtta buyuk shahri.",
                'climate_info':     "Mart-May va Sentabr-Noyabr — eng yaxshi.",
                'visa_info':        "Ko'p davlatlar fuqarolari vizasiz yoki e-viza.",
                'best_months':      ['March', 'April', 'May', 'September', 'October', 'November'],
                'is_popular':       True,
                'short_description':"Registon, Bibi-Xonim, Kalon masjid va Ichan Qal'a — VIP darajada O'zbekiston.",
                'description':      (
                    "O'zbekiston Grand Tour — 4 buyuk shaharni bir safarda. "
                    "Samarqandning Registon maydoni, Buxoroning Kalon minorasi, "
                    "Xivaning Ichan Qal'asi va Toshkentning zamonaviy ko'rinishi."
                ),
                'duration_days':    10,
                'duration_nights':  9,
                'base_price':       9_800_000,
                'max_group_size':   16,
                'min_group_size':   4,
                'is_featured':      True,
                'difficulty':       'easy',
                'tags':             ['uzbekistan', 'silk-road', 'culture', 'history', 'heritage'],
                'languages':        ['uz', 'ru', 'en'],
                'inclusions': [
                    'Barcha ichki transferlar (komfort avtobus / Afrosiyob)',
                    '4-5★ boutique mehmonxonalar (9 tun)',
                    'Barcha kirish chiptalar (Registon, Bibi-Xonim, Kalon, Ichan Qal\'a)',
                    "Tajribali gid (10 kun)",
                    'Kundalik nonushta + 5 ta milliy ovqat kechkisi',
                    'Sovg\'a seti',
                    "Sug'urta",
                ],
                'exclusions': ["Toshkentga chipta (agar xorijdan kelsa)", 'Shaxsiy xaridlar'],
                'requirements': ["Pasport (kamida 3 oy)"],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent. Kelish va Shahar Sayri", 'activities': [
                        {'time': '12:00', 'activity': 'Joylashish', 'location': 'Toshkent'},
                        {'time': '14:00', 'activity': "Xo'ja Ahror jome masjidi", 'location': 'Toshkent'},
                        {'time': '16:00', 'activity': "Temur hiyoboni va davlat muzeyi", 'location': 'Toshkent'},
                        {'time': '19:00', 'activity': "Milliy taomlar kechkisi", 'location': 'Toshkent'},
                    ], 'accommodation': "Lotte Hotel 5★", 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Toshkent — Xast Imom va Chorsu", 'activities': [
                        {'time': '09:00', 'activity': "Xast Imom majmuasi", 'location': 'Toshkent'},
                        {'time': '11:00', 'activity': "Chorsu bozori", 'location': 'Toshkent'},
                        {'time': '14:00', 'activity': "Toshkent metro tarixi", 'location': 'Toshkent'},
                    ], 'accommodation': "Lotte Hotel 5★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Toshkent → Samarqand (Afrosiyob)", 'activities': [
                        {'time': '08:00', 'activity': "Afrosiyob tezyurar poyezd", 'location': 'TAS → SQD'},
                        {'time': '11:30', 'activity': "Registon maydoni", 'location': 'Samarqand'},
                        {'time': '14:00', 'activity': "Sherdor va Tillakori madrasalari", 'location': 'Samarqand'},
                    ], 'accommodation': "Registan Plaza 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 4, 'title': "Samarqand — Bibi-Xonim, Shahi-Zinda, Go'ri Amir", 'activities': [
                        {'time': '09:00', 'activity': "Bibi-Xonim masjidi", 'location': 'Samarqand'},
                        {'time': '11:00', 'activity': "Shahi-Zinda yodgorlik majmuasi", 'location': 'Samarqand'},
                        {'time': '14:00', 'activity': "Go'ri Amir maqbarasi", 'location': 'Samarqand'},
                        {'time': '16:00', 'activity': "Ulug'bek rasadxonasi", 'location': 'Samarqand'},
                    ], 'accommodation': "Registan Plaza 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 5, 'title': "Samarqand → Buxoro", 'activities': [
                        {'time': '09:00', 'activity': "Samarqand → Buxoro (3 soat)", 'location': 'Yo\'l'},
                        {'time': '13:00', 'activity': "Buxoro — Ark qal'asi", 'location': 'Buxoro'},
                        {'time': '15:00', 'activity': "Kalon masjid va minorasi", 'location': 'Buxoro'},
                    ], 'accommodation': "Malika Bukhara 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 6, 'title': "Buxoro — Naqshband, Chor-Minor", 'activities': [
                        {'time': '09:00', 'activity': "Bahouddin Naqshband majmuasi", 'location': 'Buxoro'},
                        {'time': '11:00', 'activity': "Chor-Minor masjidi", 'location': 'Buxoro'},
                        {'time': '14:00', 'activity': "Buxoro eski shahar sayri", 'location': 'Buxoro'},
                    ], 'accommodation': "Malika Bukhara 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 7, 'title': "Buxoro → Xiva", 'activities': [
                        {'time': '08:00', 'activity': "Buxoro → Xiva (avtobus 5-6 soat)", 'location': 'Yo\'l'},
                        {'time': '15:00', 'activity': "Xiva — Ichan Qal'aga kirish", 'location': 'Xiva'},
                        {'time': '17:00', 'activity': "Islam Xoja minorasi", 'location': 'Xiva'},
                    ], 'accommodation': "Malika Khiva 4★", 'meals': {'breakfast': True, 'lunch': True, 'dinner': False}},
                    {'day': 8, 'title': "Xiva — Ichan Qal'a Sayri", 'activities': [
                        {'time': '09:00', 'activity': "Kalta Minor", 'location': 'Xiva'},
                        {'time': '10:30', 'activity': "Pahlavon Mahmud maqbarasi", 'location': 'Xiva'},
                        {'time': '13:00', 'activity': "Ichan Qal'a bozori", 'location': 'Xiva'},
                        {'time': '15:00', 'activity': "Kuhna Ark saroyi", 'location': 'Xiva'},
                    ], 'accommodation': "Malika Khiva 4★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 9, 'title': "Xiva → Toshkent (parvoz)", 'activities': [
                        {'time': '09:00', 'activity': "Xiva aeroporti, parvoz", 'location': 'Xiva → TAS'},
                        {'time': '13:00', 'activity': "Toshkentga joylashish", 'location': 'Toshkent'},
                        {'time': '19:00', 'activity': "Xayrlashuv kechkisi", 'location': 'Toshkent'},
                    ], 'accommodation': "Lotte Hotel 5★", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 10, 'title': "Toshkent. Xayrlashuv", 'activities': [
                        {'time': '10:00', 'activity': "Erkin vaqt va xarid", 'location': 'Toshkent'},
                        {'time': '14:00', 'activity': "Aeroportga transfer", 'location': 'Toshkent'},
                    ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },

            # ─── 9. SAMARQAND VIP (mavjud paket kichkina narx bilan yangilangan) ─
            {
                'title':            "Samarqand & Buxoro — Premium Sharq Afsonasi (4 kun / 3 tun)",
                'category':         'Mualliflik Turlari',
                'country':          'Uzbekistan',
                'city':             "Samarqand-Buxoro",
                'destination_name': "Samarqand & Buxoro — Ipak Yo'li Durdonalari",
                'dest_description': "Registon, Bibi-Xonim, Kalon masjid — O'zbekiston tarixi.",
                'climate_info':     "Mart-May va Sentabr-Noyabr — eng yaxshi.",
                'visa_info':        "Ko'p davlatlar vizasiz yoki e-viza.",
                'best_months':      ['March', 'April', 'May', 'September', 'October'],
                'is_popular':       True,
                'short_description':"Registon va Kalon masjid — O'zbekistonning eng go'zal ikki shahri.",
                'description':      "Samarqand va Buxoroni premium xizmat va shaxsiy gid bilan kashf eting.",
                'duration_days':    4,
                'duration_nights':  3,
                'base_price':       6_500_000,
                'max_group_size':   16,
                'min_group_size':   2,
                'is_featured':      False,
                'difficulty':       'easy',
                'tags':             ['uzbekistan', 'silk-road', 'culture', 'history'],
                'languages':        ['uz', 'ru', 'en'],
                'inclusions': [
                    'Afrosiyob poyezd yoki avtobus (ikkala yo\'nalish)',
                    'Boutique mehmonxona (4★, 3 tun)',
                    'Barcha kirish chiptalar',
                    "Shaxsiy gid (4 kun)",
                    'Kundalik nonushta + 2 ta milliy ovqat',
                    "Sug'urta",
                ],
                'exclusions': ["Toshkentdan/Toshkentga transfer", 'Shaxsiy xaridlar'],
                'requirements': ["Pasport"],
                'itinerary': [
                    {'day': 1, 'title': "Toshkent → Samarqand. Registon", 'activities': [
                        {'time': '08:00', 'activity': "Afrosiyob poyezd", 'location': 'TAS → SQD'},
                        {'time': '11:30', 'activity': "Registon maydoni", 'location': 'Samarqand'},
                        {'time': '15:00', 'activity': "Shahi-Zinda", 'location': 'Samarqand'},
                    ], 'accommodation': "4★ Samarqand Hotel", 'meals': {'breakfast': False, 'lunch': False, 'dinner': True}},
                    {'day': 2, 'title': "Samarqand — Bibi-Xonim, Go'ri Amir", 'activities': [
                        {'time': '09:00', 'activity': "Bibi-Xonim masjidi", 'location': 'Samarqand'},
                        {'time': '11:00', 'activity': "Go'ri Amir maqbarasi", 'location': 'Samarqand'},
                        {'time': '14:00', 'activity': "Ulug'bek rasadxonasi", 'location': 'Samarqand'},
                    ], 'accommodation': "4★ Samarqand Hotel", 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                    {'day': 3, 'title': "Samarqand → Buxoro. Ark & Kalon", 'activities': [
                        {'time': '09:00', 'activity': "Samarqand → Buxoro", 'location': 'Yo\'l'},
                        {'time': '13:00', 'activity': "Ark qal'asi", 'location': 'Buxoro'},
                        {'time': '15:00', 'activity': "Kalon masjid va minorasi", 'location': 'Buxoro'},
                    ], 'accommodation': "4★ Buxoro Hotel", 'meals': {'breakfast': True, 'lunch': False, 'dinner': True}},
                    {'day': 4, 'title': "Buxoro → Toshkent. Xayrlashuv", 'activities': [
                        {'time': '09:00', 'activity': "Chor-Minor va bozor sayri", 'location': 'Buxoro'},
                        {'time': '13:00', 'activity': "Toshkentga qaytish", 'location': 'Buxoro → TAS'},
                    ], 'accommodation': '', 'meals': {'breakfast': True, 'lunch': False, 'dinner': False}},
                ],
            },
        ]
