# Eski Country, DestinationImage va Destination jadvallarini o'chirib,
# yangi sodda Destination jadvalini yaratish.
# SQLite va PostgreSQL bilan mos.
# code: VARCHAR(20) — ch-st-moritz kabi uzun kodlar uchun

from django.db import migrations


def rebuild_tables(apps, schema_editor):
    db = schema_editor.connection.vendor  # 'sqlite' yoki 'postgresql'

    with schema_editor.connection.cursor() as c:
        if db == 'postgresql':
            # Barcha mumkin bo'lgan FK constraint nomlarini tushirish
            for tbl, constraint in [
                ('travel_content_travelreel',  'travel_content_travelreel_destination_id_fkey'),
                ('travel_content_travelreel',  'travel_content_trave_destination_id_bec2b49e_fk_destinati'),
                ('travel_content_curatedtrip', 'travel_content_curatedtrip_destination_id_fkey'),
                ('travel_content_curatedtrip', 'travel_content_curat_destination_id_149aa9f3_fk_destinati'),
            ]:
                c.execute(
                    f'ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {constraint}'
                )

        # Eski jadvallarni CASCADE bilan o'chirish
        c.execute('DROP TABLE IF EXISTS destinations_destinationimage CASCADE')
        c.execute('DROP TABLE IF EXISTS destinations_destination CASCADE')
        c.execute('DROP TABLE IF EXISTS destinations_country CASCADE')

        if db == 'sqlite':
            c.execute("""
                CREATE TABLE destinations_destination (
                    id          TEXT         PRIMARY KEY,
                    created_at  DATETIME     NOT NULL DEFAULT (datetime('now')),
                    updated_at  DATETIME     NOT NULL DEFAULT (datetime('now')),
                    code        VARCHAR(20)  NOT NULL UNIQUE,
                    name        VARCHAR(100) NOT NULL,
                    "group"     VARCHAR(20)  NOT NULL DEFAULT 'popular',
                    flag_image  VARCHAR(255),
                    "order"     INTEGER      NOT NULL DEFAULT 0,
                    is_active   BOOL         NOT NULL DEFAULT 1
                )
            """)
        else:
            # PostgreSQL
            c.execute("""
                CREATE TABLE destinations_destination (
                    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                    code        VARCHAR(20)  NOT NULL UNIQUE,
                    name        VARCHAR(100) NOT NULL,
                    "group"     VARCHAR(20)  NOT NULL DEFAULT 'popular',
                    flag_image  VARCHAR(255),
                    "order"     INTEGER      NOT NULL DEFAULT 0,
                    is_active   BOOLEAN      NOT NULL DEFAULT TRUE
                )
            """)
            # FK larni qayta qo'shish
            c.execute("""
                ALTER TABLE travel_content_travelreel
                    ADD CONSTRAINT travel_content_travelreel_destination_id_fkey
                    FOREIGN KEY (destination_id)
                    REFERENCES destinations_destination(id)
                    ON DELETE SET NULL
                    DEFERRABLE INITIALLY DEFERRED
            """)
            c.execute("""
                ALTER TABLE travel_content_curatedtrip
                    ADD CONSTRAINT travel_content_curatedtrip_destination_id_fkey
                    FOREIGN KEY (destination_id)
                    REFERENCES destinations_destination(id)
                    ON DELETE SET NULL
                    DEFERRABLE INITIALLY DEFERRED
            """)

        # Indexlar
        c.execute('CREATE INDEX IF NOT EXISTS destinations_destination_group_idx    ON destinations_destination ("group")')
        c.execute('CREATE INDEX IF NOT EXISTS destinations_destination_is_active_idx ON destinations_destination (is_active)')
        c.execute('CREATE INDEX IF NOT EXISTS destinations_destination_code_idx      ON destinations_destination (code)')


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0001_initial_destination'),
    ]

    operations = [
        migrations.RunPython(rebuild_tables, migrations.RunPython.noop),
    ]
