"""Seed destinations — 10 Популярные + 10 IMTIAZ Signature."""

from django.core.management.base import BaseCommand
from apps.destinations.models import Destination


class Command(BaseCommand):
    help = 'Seed 20 destinations: 10 Популярные + 10 IMTIAZ Signature'

    DATA = [
        # ── Популярные — 10 ──────────────────────────────────────────────────
        {'code': 'tr',  'name': 'Турция',              'group': 'popular',   'order': 1},
        {'code': 'ae',  'name': 'Дубай / ОАЭ',         'group': 'popular',   'order': 2},
        {'code': 'eg',  'name': 'Египет',               'group': 'popular',   'order': 3},
        {'code': 'cn',  'name': 'Китай',                'group': 'popular',   'order': 4},
        {'code': 'th',  'name': 'Таиланд',              'group': 'popular',   'order': 5},
        {'code': 'vn',  'name': 'Вьетнам',              'group': 'popular',   'order': 6},
        {'code': 'sa',  'name': 'Саудовская Аравия',    'group': 'popular',   'order': 7},
        {'code': 'kr',  'name': 'Южная Корея',          'group': 'popular',   'order': 8},
        {'code': 'in',  'name': 'Индия',                'group': 'popular',   'order': 9},
        {'code': 'ge',  'name': 'Грузия',               'group': 'popular',   'order': 10},

        # ── IMTIAZ Signature — 10 ─────────────────────────────────────────────
        {'code': 'ch-st-moritz',  'name': 'St. Moritz + Glacier Express', 'group': 'signature', 'order': 11},
        {'code': 'aq',            'name': 'Антарктида — Expedition',       'group': 'signature', 'order': 12},
        {'code': 'ch-gstaad',     'name': 'Gstaad + Montreux',             'group': 'signature', 'order': 13},
        {'code': 'it-como',       'name': 'Lake Como + Milan',             'group': 'signature', 'order': 14},
        {'code': 'it-amalfi',     'name': 'Amalfi Coast + Capri',          'group': 'signature', 'order': 15},
        {'code': 'mc',            'name': "Monaco + Cote d'Azur",          'group': 'signature', 'order': 16},
        {'code': 'mv',            'name': 'Maldives — Private Island',     'group': 'signature', 'order': 17},
        {'code': 'sc',            'name': 'Seychelles',                    'group': 'signature', 'order': 18},
        {'code': 'pf',            'name': 'Bora Bora',                     'group': 'signature', 'order': 19},
        {'code': 'jp',            'name': 'Japan — Tokyo + Kyoto',         'group': 'signature', 'order': 20},
    ]

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Seed Destinations ==='))
        created_count = 0
        updated_count = 0

        for item in self.DATA:
            obj, created = Destination.objects.update_or_create(
                code=item['code'],
                defaults={
                    'name':     item['name'],
                    'group':    item['group'],
                    'order':    item['order'],
                    'is_active': True,
                },
            )
            label = '[+] Yaratildi' if created else '[~] Yangilandi'
            group_label = 'POPULAR  ' if item['group'] == 'popular' else 'SIGNATURE'
            self.stdout.write(f'  [{group_label}] {label}: {item["code"]:15} {item["name"]}')
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nJami: {created_count} ta yaratildi, {updated_count} ta yangilandi.'
            )
        )
