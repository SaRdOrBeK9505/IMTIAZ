#!/bin/bash
# VPS da destinations migratsiyasini tuzatish va yangilash
# Faqat BIR MARTA ishlatiladi — keyingi deploylar uchun oddiy migrate yetarli
#
# Ishlatish: bash scripts/deploy_destinations.sh

set -e  # birorta xato bo'lsa to'xta

echo "=== Destinations migration fix ==="

# 1. Migration tarixini tozalash (eski Country/Destination jadvallar bor DB da)
python manage.py shell << 'EOF'
from django.db import connection
with connection.cursor() as c:
    c.execute("DELETE FROM django_migrations WHERE app='destinations'")
    print("[1] destinations migration records cleared")
    c.execute("DELETE FROM django_migrations WHERE app='travel_content'")
    print("[1] travel_content migration records cleared")
EOF

# 2. destinations 0001 ni fake apply (jadvalni yaratmaydi, faqat rekord)
python manage.py migrate destinations 0001_initial_destination --fake
echo "[2] destinations 0001 faked"

# 3. travel_content ni fake apply
python manage.py migrate travel_content --fake
echo "[3] travel_content faked"

# 4. 0002 ni haqiqiy ishlatish — eski jadvallarni o'chirib yangi Destination jadvalini yaratadi
python manage.py migrate destinations
echo "[4] destinations 0002 applied (table rebuilt)"

# 5. Seed data
python manage.py seed_destinations
echo "[5] Seed data done"

echo ""
echo "=== Done! ==="
