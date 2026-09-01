"""Management command to seed popular destinations."""

from django.core.management.base import BaseCommand
from apps.destinations.models import Country, Destination


class Command(BaseCommand):
    help = 'Seed popular destinations (Turkey, Dubai, Egypt, China, Thailand, Vietnam, S.Korea, India, Georgia)'

    DESTINATIONS_DATA = [
        {
            'country': {
                'name': 'Turkey',
                'name_uz': 'Turkiya',
                'code': 'TR',
                'flag_emoji': '🇹🇷',
                'currency': 'TRY',
                'calling_code': '+90',
            },
            'destinations': [
                {
                    'name': 'Istanbul',
                    'name_uz': 'Istanbul',
                    'category': 'city',
                    'description': 'Historic city bridging Europe and Asia',
                    'description_uz': 'Yevropa va Osiyoni bog\'laydigan tarixiy shahar',
                    'latitude': 41.0082,
                    'longitude': 28.9784,
                    'is_popular': True,
                },
                {
                    'name': 'Antalya',
                    'name_uz': 'Antaliya',
                    'category': 'beach',
                    'description': 'Beautiful Mediterranean coast',
                    'description_uz': 'Go\'zal O\'rta dengiz sohili',
                    'latitude': 36.8969,
                    'longitude': 30.7133,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'United Arab Emirates',
                'name_uz': 'Birlashgan Arab Amirliklari',
                'code': 'AE',
                'flag_emoji': '🇦🇪',
                'currency': 'AED',
                'calling_code': '+971',
            },
            'destinations': [
                {
                    'name': 'Dubai',
                    'name_uz': 'Dubay',
                    'category': 'modern',
                    'description': 'Modern city with luxury shopping and architecture',
                    'description_uz': 'Lyuks savdo va arxitekturasi bilan zamonaviy shahar',
                    'latitude': 25.2048,
                    'longitude': 55.2708,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'Egypt',
                'name_uz': 'Misr',
                'code': 'EG',
                'flag_emoji': '🇪🇬',
                'currency': 'EGP',
                'calling_code': '+20',
            },
            'destinations': [
                {
                    'name': 'Cairo',
                    'name_uz': 'Qohira',
                    'category': 'historical',
                    'description': 'Home to the Pyramids and Sphinx',
                    'description_uz': 'Piramidalar va Sfenksning vatani',
                    'latitude': 30.0444,
                    'longitude': 31.2357,
                    'is_popular': True,
                },
                {
                    'name': 'Sharm El Sheikh',
                    'name_uz': 'Sharm El Shayx',
                    'category': 'beach',
                    'description': 'Red Sea resort destination',
                    'description_uz': 'Qizil dengiz kurorti',
                    'latitude': 27.9158,
                    'longitude': 34.3297,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'China',
                'name_uz': 'Xitoy',
                'code': 'CN',
                'flag_emoji': '🇨🇳',
                'currency': 'CNY',
                'calling_code': '+86',
            },
            'destinations': [
                {
                    'name': 'Beijing',
                    'name_uz': 'Pekin',
                    'category': 'historical',
                    'description': 'Capital city with Great Wall access',
                    'description_uz': 'Buyuk Devor bilan poytaxt shahar',
                    'latitude': 39.9042,
                    'longitude': 116.4074,
                    'is_popular': True,
                },
                {
                    'name': 'Shanghai',
                    'name_uz': 'Shanxay',
                    'category': 'modern',
                    'description': 'Global financial hub',
                    'description_uz': 'Global moliya markazi',
                    'latitude': 31.2304,
                    'longitude': 121.4737,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'Thailand',
                'name_uz': 'Tailand',
                'code': 'TH',
                'flag_emoji': '🇹🇭',
                'currency': 'THB',
                'calling_code': '+66',
            },
            'destinations': [
                {
                    'name': 'Bangkok',
                    'name_uz': 'Bangkok',
                    'category': 'city',
                    'description': 'Vibrant capital with temples and markets',
                    'description_uz': 'Ibodatxonalar va bozorlari bilan jonli poytaxt',
                    'latitude': 13.7563,
                    'longitude': 100.5018,
                    'is_popular': True,
                },
                {
                    'name': 'Phuket',
                    'name_uz': 'Phuket',
                    'category': 'beach',
                    'description': 'Tropical island paradise',
                    'description_uz': 'Tropik orol jannati',
                    'latitude': 7.8804,
                    'longitude': 98.3925,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'Vietnam',
                'name_uz': 'Vyetnam',
                'code': 'VN',
                'flag_emoji': '🇻🇳',
                'currency': 'VND',
                'calling_code': '+84',
            },
            'destinations': [
                {
                    'name': 'Hanoi',
                    'name_uz': 'Xanoy',
                    'category': 'historical',
                    'description': 'Ancient capital with French colonial architecture',
                    'description_uz': 'Fransuz mustamlakachi arxitekturasi bilan qadimiy poytaxt',
                    'latitude': 21.0285,
                    'longitude': 105.8542,
                    'is_popular': True,
                },
                {
                    'name': 'Ho Chi Minh City',
                    'name_uz': 'Ho Shi Min shahri',
                    'category': 'modern',
                    'description': 'Dynamic southern metropolis',
                    'description_uz': 'Dinamik janubiy metropol',
                    'latitude': 10.8231,
                    'longitude': 106.6297,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'South Korea',
                'name_uz': 'Janubiy Koreya',
                'code': 'KR',
                'flag_emoji': '🇰🇷',
                'currency': 'KRW',
                'calling_code': '+82',
            },
            'destinations': [
                {
                    'name': 'Seoul',
                    'name_uz': 'Seul',
                    'category': 'modern',
                    'description': 'High-tech capital with ancient palaces',
                    'description_uz': 'Qadimiy saroylar bilan yuqori texnologiyali poytaxt',
                    'latitude': 37.5665,
                    'longitude': 126.9780,
                    'is_popular': True,
                },
                {
                    'name': 'Busan',
                    'name_uz': 'Pusan',
                    'category': 'beach',
                    'description': 'Coastal city with beautiful beaches',
                    'description_uz': 'Go\'zal plyajlari bilan qirg\'oq shahri',
                    'latitude': 35.1796,
                    'longitude': 129.0756,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'India',
                'name_uz': 'Hindiston',
                'code': 'IN',
                'flag_emoji': '🇮🇳',
                'currency': 'INR',
                'calling_code': '+91',
            },
            'destinations': [
                {
                    'name': 'Delhi',
                    'name_uz': 'Dehli',
                    'category': 'historical',
                    'description': 'Historic capital with Mughal architecture',
                    'description_uz': 'Mo\'g\'ul arxitekturasi bilan tarixiy poytaxt',
                    'latitude': 28.6139,
                    'longitude': 77.2090,
                    'is_popular': True,
                },
                {
                    'name': 'Mumbai',
                    'name_uz': 'Mumbay',
                    'category': 'modern',
                    'description': 'Financial capital and Bollywood hub',
                    'description_uz': 'Moliya poytaxti va Bollivud markazi',
                    'latitude': 19.0760,
                    'longitude': 72.8777,
                    'is_popular': True,
                },
            ]
        },
        {
            'country': {
                'name': 'Georgia',
                'name_uz': 'Gruziya',
                'code': 'GE',
                'flag_emoji': '🇬🇪',
                'currency': 'GEL',
                'calling_code': '+995',
            },
            'destinations': [
                {
                    'name': 'Tbilisi',
                    'name_uz': 'Tbilisi',
                    'category': 'cultural',
                    'description': 'Charming capital with wine culture',
                    'description_uz': 'Vino madaniyati bilan jozibali poytaxt',
                    'latitude': 41.7151,
                    'longitude': 44.8271,
                    'is_popular': True,
                },
                {
                    'name': 'Batumi',
                    'name_uz': 'Batumi',
                    'category': 'beach',
                    'description': 'Black Sea resort city',
                    'description_uz': 'Qora dengiz kurort shahri',
                    'latitude': 41.6423,
                    'longitude': 41.6339,
                    'is_popular': True,
                },
            ]
        },
    ]

    def handle(self, *args, **options):
        self.stdout.write('Seeding popular destinations...')
        
        for country_data in self.DESTINATIONS_DATA:
            country_info = country_data['country']
            destinations_list = country_data['destinations']
            
            # Create or update country
            country, created = Country.objects.update_or_create(
                code=country_info['code'],
                defaults=country_info
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created country: {country.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Updated country: {country.name}'))
            
            # Create destinations
            for dest_data in destinations_list:
                dest, created = Destination.objects.update_or_create(
                    name=dest_data['name'],
                    country=country,
                    defaults={
                        **dest_data,
                        'country': country,
                        'total_capacity': 1000,
                        'available_tickets': 1000,
                        'ticket_price': 500000,
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  Created destination: {dest.name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'  Updated destination: {dest.name}'))
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded popular destinations!'))
