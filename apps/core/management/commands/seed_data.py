"""
IMTIAZ Seed Data Management Command.
Ma'lumotlar bazasini real brendlar, tur paketlar, filiallar va xodimlar bilan to'ldiradi.

Ishga tushirish:
    python manage.py seed_data
"""

from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import User, UserRole
from apps.crm.models import Organization, Branch, BranchStaff, BranchStaffPermission
from apps.crm_restaurant.models import MenuCategory, MenuItem
from apps.tours.models import TourCategory, TourDestination, TourPackage, TourAvailability

DEFAULT_PASSWORD = "Imtiaz2026!"

class Command(BaseCommand):
    help = "Baza uchun real brendlar, turlar, xodimlar va kirish ma'lumotlarini yaratadi."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Seed data yuklanmoqda..."))

        credentials_log = []

        def _get_or_create_user(phone, full_name, role):
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': role,
                    'is_phone_verified': True,
                    'is_staff': role in [UserRole.ADMIN, UserRole.OWNER_RESTAURANT, UserRole.OWNER_TOUR, UserRole.RESTAURANT_STAFF, UserRole.TOUR_STAFF],
                }
            )
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
            return user

        # ── 1. Admin Foydalanuvchi ────────────────────────────────────────────────
        admin_user = _get_or_create_user('+998901110000', 'IMTIAZ System Admin', UserRole.ADMIN)
        credentials_log.append(('System Admin', '+998901110000', DEFAULT_PASSWORD, 'SuperAdmin Panel'))

        # ── 2. Real O'zbekiston Tur Kompaniyalari va 9 ta Yo'nalish ────────────────
        tour_companies_data = [
            {
                'name': 'Asialuxe Travel',
                'owner_phone': '+998902000001',
                'owner_name': 'Asialuxe Director',
                'staff_phone': '+998902000002',
                'staff_name': 'Asialuxe Operator',
                'desc': 'O\'zbekistondagi eng yirik milliy turoperator, turli yo\'nalishlar va charter reyslar tashkilotchisi.',
            },
            {
                'name': 'Prestige Travel',
                'owner_phone': '+998902000003',
                'owner_name': 'Prestige Director',
                'staff_phone': '+998902000004',
                'staff_name': 'Prestige Operator',
                'desc': 'Yevropa va Osiyo bo\'ylab eksklyuziv hamda mualliflik VIP turlari.',
            },
            {
                'name': 'Mystery Travel',
                'owner_phone': '+998902000005',
                'owner_name': 'Mystery Director',
                'staff_phone': '+998902000006',
                'staff_name': 'Mystery Operator',
                'desc': 'Prеmіum lifestyle va tropik mamlakatlarga qulay VIP turpaketlar.',
            },
            {
                'name': 'East Asia Point',
                'owner_phone': '+998902000007',
                'owner_name': 'EastAsia Director',
                'staff_phone': '+998902000008',
                'staff_name': 'EastAsia Operator',
                'desc': 'Xitoy, Yaponiya va Janubiy-Sharqiy Osiyo bo\'yicha ixtisoslashgan yetakchi turoperator.',
            },
        ]

        created_tour_orgs = {}
        for tc in tour_companies_data:
            t_owner = _get_or_create_user(tc['owner_phone'], tc['owner_name'], UserRole.OWNER_TOUR)
            t_staff = _get_or_create_user(tc['staff_phone'], tc['staff_name'], UserRole.TOUR_STAFF)

            t_org = Organization.objects.filter(owner=t_owner).first() or Organization.objects.filter(name=tc['name']).first()
            if not t_org:
                t_org = Organization.objects.create(
                    name=tc['name'],
                    org_type=Organization.OrgType.TOUR_COMPANY,
                    business_type='travel',
                    owner=t_owner,
                    description=tc['desc'],
                    contact_phone=tc['owner_phone'],
                )
            t_branch, _ = Branch.objects.get_or_create(
                organization=t_org,
                name='Asosiy Ofis (Toshkent)',
                defaults={'city': 'Toshkent', 'address': 'Shota Rustaveli k., 40'}
            )
            BranchStaff.objects.get_or_create(
                user=t_staff,
                defaults={
                    'branch': t_branch,
                    'role': 'Lead Manager',
                    'permissions': [BranchStaffPermission.VIEW_BOOKINGS, BranchStaffPermission.MANAGE_BOOKINGS],
                }
            )
            created_tour_orgs[tc['name']] = t_org
            credentials_log.append((f"{tc['name']} (Owner)", tc['owner_phone'], DEFAULT_PASSWORD, 'Tour CRM Owner'))
            credentials_log.append((f"{tc['name']} (Staff)", tc['staff_phone'], DEFAULT_PASSWORD, 'Tour CRM Staff (Leads)'))

        # Tur Kategoriyalari
        cat_beach, _ = TourCategory.objects.get_or_create(name='Dengiz va VIP Ta\'til', defaults={'icon': '🏖️'})
        cat_euro, _ = TourCategory.objects.get_or_create(name='Yevropa & Madaniyat', defaults={'icon': '🏰'})
        cat_asia, _ = TourCategory.objects.get_or_create(name='Ekzotika & Osiyo', defaults={'icon': '⛩️'})
        cat_author, _ = TourCategory.objects.get_or_create(name='Mualliflik Turlari', defaults={'icon': '✨'})

        # 9 ta Yo'nalish bo'yicha Paketlar
        tour_packages_data = [
            # 1. OAE
            {
                'org': created_tour_orgs['Asialuxe Travel'],
                'title': 'Dubai Atlantis The Royal & Premium Experience (5 kun)',
                'category': cat_beach,
                'country': 'UAE',
                'city': 'Dubai',
                'price': Decimal('28000000'),
                'short': "Dubaydagi afsonaviy Atlantis The Royal mehmonxonasida premium hordiq.",
                'desc': "Biznes-klass parvoz, shaxsiy yaxta sayri va Dubayning eng nufuzli restoranlarida joylar band qilish.",
                'days': 5, 'nights': 4,
                'inc': ["Biznes-klass aviachipta", "Atlantis The Royal 5*", "Yacht Tour", "VIP Transfer"],
            },
            # 2. Turkiya
            {
                'org': created_tour_orgs['Asialuxe Travel'],
                'title': 'Antalya Maxx Royal Belek VIP Ultra All-Inclusive (7 kun)',
                'category': cat_beach,
                'country': 'Turkey',
                'city': 'Antalya',
                'price': Decimal('32000000'),
                'short': "O'rta yer dengizi bo'yidagi eng nufuzli Maxx Royal resortida unutilmas ta'til.",
                'desc': "Shaxsiy plyaj, golf-klub, mualliflik restoranlari va bolalar uchun premium park xizmatlari.",
                'days': 7, 'nights': 6,
                'inc': ["To'g'ridan-to'g'ri charter parvoz", "Maxx Royal 5*", "Ultra All Inclusive", "CIP Lounge"],
            },
            # 3. Yevropa
            {
                'org': created_tour_orgs['Prestige Travel'],
                'title': 'Parij & Nitssa Fransuz Rivieryasi VIP Tur (8 kun)',
                'category': cat_euro,
                'country': 'France',
                'city': 'Paris',
                'price': Decimal('45000000'),
                'short': "Eyfel minorasi ko'rinishidagi suite va Kot-d'Azur bo'ylab yaxtada sayohat.",
                'desc': "Luvrga VIP navbatsiz kirish, Michelin yulduzli restoranlarda kechki ovqat va Nitssadagi premium mehmonxona.",
                'days': 8, 'nights': 7,
                'inc': ["Schengen viza ko'magi", "Ritz Paris 5*", "Michelin Dinner", "Shaxsiy gid va transfer"],
            },
            # 4. Shtatlar (USA)
            {
                'org': created_tour_orgs['Prestige Travel'],
                'title': 'Nyu-York & Mayami Grand American Tour (10 kun)',
                'category': cat_euro,
                'country': 'USA',
                'city': 'New York',
                'price': Decimal('65000000'),
                'short': "Tayms-skver markazidagi premium mehmonxona va Mayami South Beach bo'yida hordiq.",
                'desc': "Manxetten ustida vertolyot sayri, Brodvey shousiga VIP chiptalar va Mayamida Okean drayv bo'yida dam olish.",
                'days': 10, 'nights': 9,
                'inc': ["AQSh viza yordami", "Manhattan 5* Hotel", "Vertolyot ekskursiyasi", "Brodvey VIP chipta"],
            },
            # 5. Xitoy
            {
                'org': created_tour_orgs['East Asia Point'],
                'title': 'Pekin & Shanxay Zamonaviy va Tarixiy Xitoy (7 kun)',
                'category': cat_asia,
                'country': 'China',
                'city': 'Shanghai',
                'price': Decimal('22000000'),
                'short': "Xitoy Buyuk Devori, tezyurar poyezdlar va Shanxayning osmon o'par binolari.",
                'desc': "Pekindagi Imperator saroyi, Xaynan orolidagi tropik kurort va Shanxay moliya markazida ekskursiya.",
                'days': 7, 'nights': 6,
                'inc': ["Guruh vizasi", "5* Mehmonxonalar", "Bullet Train VIP", "Barcha ekskursiyalar"],
            },
            # 6. Tailand
            {
                'org': created_tour_orgs['Mystery Travel'],
                'title': 'Pxuket & Phi Phi Island Paradise Escape (8 kun)',
                'category': cat_beach,
                'country': 'Thailand',
                'city': 'Phuket',
                'price': Decimal('19500000'),
                'short': "Andaman dengizining firuza suvlarida va shaxsiy villyada tropik hordiq.",
                'desc': "Phi Phi orollariga spidbotda sayohat, Tailand SPA va masaj seanslari, dengiz mahsulotlari kechki ovqati.",
                'days': 8, 'nights': 7,
                'inc': ["Aviachipta", "Private Pool Villa 5*", "Island Speedboat Tour", "SPA package"],
            },
            # 7. Malayziya
            {
                'org': created_tour_orgs['Mystery Travel'],
                'title': 'Kuala-Lumpur & Langkawi Oroli VIP Mix (7 kun)',
                'category': cat_asia,
                'country': 'Malaysia',
                'city': 'Kuala Lumpur',
                'price': Decimal('21000000'),
                'short': "Petronas egizak minoralaridan Langkawi tropik plyajlarigacha.",
                'desc': "Kuala-Lumpur shahridagi shoping va Langkawi orolidagi arxipelaglar bo'ylab yaxta kruizi.",
                'days': 7, 'nights': 6,
                'inc': ["Ichki va tashqi aviachiptalar", "The Ritz-Carlton KL 5*", "Langkawi Sunset Cruise"],
            },
            # 8. Yaponiya
            {
                'org': created_tour_orgs['East Asia Point'],
                'title': 'Tokio & Kioto Sakula va Texnologiya Mo''jizasi (8 kun)',
                'category': cat_asia,
                'country': 'Japan',
                'city': 'Tokyo',
                'price': Decimal('42000000'),
                'short': "Fudzi tog'i ko'rinishi, Shinkansen tezyurar poyezdi va zamonaviy Tokio.",
                'desc': "Yaponiya an'anaviy Ryokan mehmondo'stligi, Ginza tumanida shoping va Kioto ibodatxonalari bo'ylab sayr.",
                'days': 8, 'nights': 7,
                'inc': ["JR Shinkansen Pass", "Tokyo 5* & Traditional Ryokan", "Fuji Mountain Tour", "Tea Ceremony"],
            },
            # 9. Mualliflik Turlari (Author Tours)
            {
                'org': created_tour_orgs['Prestige Travel'],
                'title': 'Mualliflik Turi: Islandiya Shimoliy Yog''dusi & Geyzerlar (6 kun)',
                'category': cat_author,
                'country': 'Iceland',
                'city': 'Reykjavik',
                'price': Decimal('38000000'),
                'short': "Professional fotograf va gid hamrohligida Shimoliy yog'du ovlaymiz.",
                'desc': "Moviy Laguna issiq bulaqlari, muzliklar ustida jip-sayohat va fotosessiyalar bilan boyitilgan mualliflik dasturi.",
                'days': 6, 'nights': 5,
                'inc': ["SuperJeep 4x4 Tour", "Blue Lagoon Comfort Pass", "Foto-gid hamrohligi", "Thermal Hotel"],
            },
        ]

        for pdata in tour_packages_data:
            dest, _ = TourDestination.objects.get_or_create(
                country=pdata['country'],
                city=pdata['city'],
                defaults={'name': f"{pdata['city']} ({pdata['country']})", 'organization': pdata['org']}
            )
            pkg, _ = TourPackage.objects.get_or_create(
                organization=pdata['org'],
                title=pdata['title'],
                defaults={
                    'category': pdata['category'],
                    'destination': dest,
                    'short_description': pdata['short'],
                    'description': pdata['desc'],
                    'duration_days': pdata['days'],
                    'duration_nights': pdata['nights'],
                    'base_price': pdata['price'],
                    'currency': 'UZS',
                    'inclusions': pdata['inc'],
                }
            )
            TourAvailability.objects.get_or_create(
                package=pkg,
                departure_date=date.today() + timedelta(days=7),
                defaults={'total_seats': 8, 'booked_seats': 0}
            )

        # ── 3. 15 ta Brend (Restoran, Wellness, Fashion, Fitness, Tech) ─────────
        brands_data = [
            {
                'name': 'Bika Bakery',
                'type': Organization.OrgType.BAKERY,
                'desc': 'Fransuzcha kofe va yangi yopilgan kruassan va pishiriqlar uyi.',
                'phone': '+998903000001',
                'branches': [
                    {'name': 'Shota Rustaveli filiali', 'city': 'Toshkent', 'address': 'Shota Rustaveli k., 12'},
                    {'name': 'Samarqand Darvoza filiali', 'city': 'Toshkent', 'address': 'Qoratosh k., 5A'},
                ],
                'menu': [('Kruassan klassik', 28000), ('Cappuccino Special', 32000), ('Almond Pain au Chocolat', 35000)],
            },
            {
                'name': 'Doyoga',
                'type': Organization.OrgType.WELLNESS,
                'desc': 'Tana va ruhiyat muvozanati uchun premium yoga va wellness studiyasi.',
                'phone': '+998903000002',
                'branches': [
                    {'name': 'Eco Park Studio', 'city': 'Toshkent', 'address': 'Maxtumquli k., 79'},
                ],
            },
            {
                'name': 'Doyoga Padel',
                'type': Organization.OrgType.SPORT,
                'desc': 'Zamonaviy padel-tennis kortlari va sport klubi.',
                'phone': '+998903000003',
                'branches': [
                    {'name': 'Padel Arena Chilanzar', 'city': 'Toshkent', 'address': 'Chilonzor 2-mavze'},
                ],
            },
            {
                'name': 'Muzakitchen',
                'type': Organization.OrgType.RESTAURANT,
                'desc': 'Osiyo pan-aziyat oshxonasi va mualliflik kokteyllari bar restoran.',
                'phone': '+998903000004',
                'branches': [
                    {'name': 'Muzakitchen Center', 'city': 'Toshkent', 'address': 'Taras Shevchenko k., 21'},
                ],
                'menu': [('Tom Yum Goong', 95000), ('Salmon Teriyaki', 145000), ('Black Cod Miso', 280000)],
            },
            {
                'name': 'Hori',
                'type': Organization.OrgType.RESTAURANT,
                'desc': 'Lifestyle & Fine Dining restoran va kechki shinam maskan.',
                'phone': '+998903000005',
                'branches': [
                    {'name': 'Hori City', 'city': 'Toshkent', 'address': 'Shaxrisabz k., 10'},
                ],
                'menu': [('Wagyu Ribeye Steak', 450000), ('Truffle Pasta', 160000)],
            },
            {
                'name': 'Baselic',
                'type': Organization.OrgType.RESTAURANT,
                'desc': 'Haqiqiy Italiya pitsasi va pasta tayyorlanadigan qahvaxona-restoran.',
                'phone': '+998903000006',
                'branches': [
                    {'name': 'Baselic Grand', 'city': 'Toshkent', 'address': 'Nukus k., 88'},
                ],
                'menu': [('Pizza Margherita Napoletana', 85000), ('Pasta Carbonara Originale', 92000)],
            },
            {
                'name': 'Saadi',
                'type': Organization.OrgType.FASHION,
                'desc': 'Nufuzli Sharqona va zamonaviy premium ayollar liboslari brendi.',
                'phone': '+998903000007',
                'branches': [
                    {'name': 'Saadi Boutique', 'city': 'Toshkent', 'address': 'Mirabad k., 40'},
                ],
            },
            {
                'name': 'Bibiona',
                'type': Organization.OrgType.KIDS,
                'desc': 'Bolalar uchun Yevropa sifatidagi premium kiyimlar va aksessuarlar.',
                'phone': '+998903000008',
                'branches': [
                    {'name': 'Bibiona Kids City Mall', 'city': 'Toshkent', 'address': 'Tashkent City Mall, 3-qavat'},
                ],
            },
            {
                'name': 'Maktoob',
                'type': Organization.OrgType.LIFESTYLE,
                'desc': 'Concept store, estetika va eksklyuziv lifestyle buyumlari brendi.',
                'phone': '+998903000009',
                'branches': [
                    {'name': 'Maktoob Gallery', 'city': 'Toshkent', 'address': 'Sodiq Azimov k., 65'},
                ],
            },
            {
                'name': 'Befit',
                'type': Organization.OrgType.FITNESS,
                'desc': 'Eng ilg\'or uskunalar va basseynli premium fitness va spa kompleksi.',
                'phone': '+998903000010',
                'branches': [
                    {'name': 'Befit Premium Hub', 'city': 'Toshkent', 'address': 'Movarounnahr k., 1'},
                ],
            },
            {
                'name': 'Befit Pro',
                'type': Organization.OrgType.FITNESS,
                'desc': 'Professional sportchilar va og\'ir atletika uchun maxsus zal.',
                'phone': '+998903000011',
                'branches': [
                    {'name': 'Befit Pro Arena', 'city': 'Toshkent', 'address': 'Farg\'ona yo\'li k., 10'},
                ],
            },
            {
                'name': 'Befit Box',
                'type': Organization.OrgType.RESTAURANT,
                'desc': 'Fitnes ixlosmandlari uchun balanslashtirilgan oqsil va fitobar oziq-ovqatlari.',
                'phone': '+998903000012',
                'branches': [
                    {'name': 'Befit Box Cafe', 'city': 'Toshkent', 'address': 'Movarounnahr k., 1'},
                ],
                'menu': [('Protein Bowl Salmon', 78000), ('Detox Smoothie Green', 38000)],
            },
            {
                'name': 'Saber Tech',
                'type': Organization.OrgType.TECH,
                'desc': 'Aqlli uy texnologiyalari va eng so\'nggi premium gadjetlar do\'koni.',
                'phone': '+998903000013',
                'branches': [
                    {'name': 'Saber Tech Showroom', 'city': 'Toshkent', 'address': 'Navoiy k., 25'},
                ],
            },
            {
                'name': 'Saber Parfum',
                'type': Organization.OrgType.PARFUM,
                'desc': 'Nish va mualliflik parfyumeriya kolleksiyalari boutiquesi.',
                'phone': '+998903000014',
                'branches': [
                    {'name': 'Saber Parfum Boutique', 'city': 'Toshkent', 'address': 'Zarafshon k., 4'},
                ],
            },
            {
                'name': 'Quadro Restaurant',
                'type': Organization.OrgType.RESTAURANT,
                'desc': 'Yevropa, grill va klassik go\'sht taomlari bo\'yicha elit restoran.',
                'phone': '+998903000015',
                'branches': [
                    {'name': 'Quadro Grill & Bar', 'city': 'Toshkent', 'address': 'Zuliyaxonim k., 14'},
                ],
                'menu': [('Tomahawk Steak', 520000), ('Grilled Octopus', 210000), ('Classic Caesar Salad', 75000)],
            },
        ]

        for i, bdata in enumerate(brands_data, 1):
            owner_phone = f'+9989030010{i:02d}'
            staff_phone = f'+9989030020{i:02d}'
            owner_name = f"{bdata['name']} Owner"
            staff_name = f"{bdata['name']} Manager"

            role_owner = UserRole.OWNER_RESTAURANT if bdata['type'] == Organization.OrgType.RESTAURANT else UserRole.OWNER
            role_staff = UserRole.RESTAURANT_STAFF if bdata['type'] == Organization.OrgType.RESTAURANT else UserRole.BRANCH_STAFF

            u_owner = _get_or_create_user(owner_phone, owner_name, role_owner)
            u_staff = _get_or_create_user(staff_phone, staff_name, role_staff)

            org, _ = Organization.objects.get_or_create(
                name=bdata['name'],
                defaults={
                    'org_type': bdata['type'],
                    'business_type': 'restaurant' if bdata['type'] == Organization.OrgType.RESTAURANT else 'other',
                    'owner': u_owner,
                    'description': bdata['desc'],
                    'contact_phone': bdata['phone'],
                }
            )

            credentials_log.append((f"{bdata['name']} (Owner)", owner_phone, DEFAULT_PASSWORD, f"CRM Owner ({bdata['name']})"))
            credentials_log.append((f"{bdata['name']} (Staff)", staff_phone, DEFAULT_PASSWORD, f"CRM Staff ({bdata['name']})"))

            # Filiallar yaratish
            for br_info in bdata['branches']:
                branch, _ = Branch.objects.get_or_create(
                    organization=org,
                    name=br_info['name'],
                    defaults={
                        'city': br_info['city'],
                        'address': br_info['address'],
                        'phone': bdata['phone'],
                    }
                )
                BranchStaff.objects.get_or_create(
                    user=u_staff,
                    defaults={
                        'branch': branch,
                        'role': 'Manager',
                        'permissions': [BranchStaffPermission.VIEW_BOOKINGS, BranchStaffPermission.MANAGE_BOOKINGS],
                    }
                )

                # Restoran uchun Stollarni va Vaqt Slotlarini Yaratish
                if bdata['type'] == Organization.OrgType.RESTAURANT:
                    from apps.crm.models import RestaurantTable, TableTimeSlot, TableStatus

                    # 1. Stollarni yaratish (Main Hall, Terrace, VIP Rooms)
                    tables_config = [
                        ('T-01', 2, 'Main Hall', False, ['window_view']),
                        ('T-02', 2, 'Main Hall', False, ['cozy']),
                        ('T-03', 4, 'Main Hall', False, ['family_sofa']),
                        ('T-04', 4, 'Main Hall', False, ['central']),
                        ('T-05', 6, 'Main Hall', False, ['large_table']),
                        ('TR-01', 2, 'Terrace (Teras)', False, ['outdoor', 'fresh_air']),
                        ('TR-02', 4, 'Terrace (Teras)', False, ['outdoor', 'city_view']),
                        ('VIP-1', 8, 'VIP Room', True, ['private', 'projector', 'sound_system']),
                        ('VIP-2', 12, 'VIP Room', True, ['private', 'panoramic_view', 'karaoke']),
                    ]

                    created_tables = []
                    for t_num, cap, sec, is_vip, feats in tables_config:
                        tbl, _ = RestaurantTable.objects.get_or_create(
                            branch=branch,
                            table_number=t_num,
                            defaults={
                                'capacity': cap,
                                'min_capacity': 1,
                                'section': sec,
                                'is_vip': is_vip,
                                'features': feats,
                                'current_status': TableStatus.AVAILABLE,
                            }
                        )
                        created_tables.append(tbl)

                    # 2. Keyingi 3 kun uchun Vaqt Slotlarini Yaratish (12:00, 14:00, 18:00, 20:00)
                    time_slots_list = [
                        ('12:00:00', '14:00:00'),
                        ('14:00:00', '16:00:00'),
                        ('18:00:00', '20:00:00'),
                        ('20:00:00', '22:00:00'),
                    ]
                    for day_offset in range(3):
                        slot_date = date.today() + timedelta(days=day_offset)
                        for tbl in created_tables:
                            for s_time, e_time in time_slots_list:
                                TableTimeSlot.objects.get_or_create(
                                    table=tbl,
                                    date=slot_date,
                                    start_time=s_time,
                                    end_time=e_time,
                                    defaults={'is_available': True}
                                )

                # Restoran menyusini va Featured Items to'ldirish
                if bdata['type'] == Organization.OrgType.RESTAURANT and 'menu' in bdata:
                    from apps.crm_restaurant.models import FeaturedItem
                    cat, _ = MenuCategory.objects.get_or_create(branch=branch, name='Asosiy Menyu')
                    for idx, (m_name, m_price) in enumerate(bdata['menu']):
                        item, _ = MenuItem.objects.get_or_create(
                            category=cat,
                            name=m_name,
                            defaults={'price': Decimal(str(m_price)), 'is_available': True}
                        )
                        # Birinchi taomni "Tavsiya etilgan taklif" (FeaturedItem) qilish
                        if idx == 0:
                            FeaturedItem.objects.get_or_create(
                                branch=branch,
                                menu_item=item,
                                defaults={'custom_title': f"Chef Special: {m_name}", 'order': 1}
                            )

        # ── Natijalarni Konsolga Chiroyli Qilib Chiqarish ───────────────────────────
        self.stdout.write(self.style.SUCCESS("\nBaza muvaffaqiyatli ma'lumotlar bilan to'ldirildi!"))
        self.stdout.write(self.style.SUCCESS("=" * 85))
        self.stdout.write(self.style.SUCCESS(f"{'TIZIM VA CRM USERS LOGIN PAROLLARI (SMS / PHONE AUTH)':^85}"))
        self.stdout.write(self.style.SUCCESS("=" * 85))
        self.stdout.write(f"{'Roli / Brend':<30} | {'Telefon (Login)':<16} | {'Parol':<12} | {'Panel'}")
        self.stdout.write("-" * 85)
        for name, phone, pwd, panel in credentials_log:
            self.stdout.write(f"{name:<30} | {phone:<16} | {pwd:<12} | {panel}")
        self.stdout.write("=" * 85 + "\n")
