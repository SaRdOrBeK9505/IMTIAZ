#!/bin/bash
# VPS da destinations migratsiyasini tuzatish va yangilash
# Faqat BIR MARTA ishlatiladi
#
# Ishlatish: bash scripts/deploy_destinations.sh

set -e

echo "=== Destinations migration fix ==="

# 1. Migration tarixini tozalash
python manage.py shell << 'EOF'
from django.db import connection
with connection.cursor() as c:
    c.execute("DELETE FROM django_migrations WHERE app='destinations'")
    print("[1] destinations migration records cleared")
    c.execute("DELETE FROM django_migrations WHERE app='travel_content'")
    print("[1] travel_content migration records cleared")
EOF

# 2. destinations 0001 ni fake apply
python manage.py migrate destinations 0001_initial_destination --fake
echo "[2] destinations 0001 faked"

# 3. travel_content ni fake apply
python manage.py migrate travel_content --fake
echo "[3] travel_content faked"

# 4. 0002 ni haqiqiy ishlatish — CASCADE bilan eski jadvallarni o'chirib yangi yaratadi
python manage.py migrate destinations
echo "[4] destinations 0002 applied"

# 5. Seed data
python manage.py seed_destinations
echo "[5] Seed data done"

echo ""
echo "=== Done! ==="
