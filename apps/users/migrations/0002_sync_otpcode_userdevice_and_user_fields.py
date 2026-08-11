"""
VPS uchun xavfsiz migratsiya.

Muammo: users.0001_initial.py tahrirlangan (UserDevice, OTPCode qo'shilgan),
lekin VPS da eski 0001 allaqachon qo'llangan — jadval yaratilmagan.

Bu migratsiya jadval/maydon mavjud bo'lmasa yaratadi (idempotent).
Local dev da ham xavfsiz: mavjud jadvallarni o'tkazib yuboradi.
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid


def _table_exists(schema_editor, table_name: str) -> bool:
    return table_name in schema_editor.connection.introspection.table_names()


def _column_exists(schema_editor, table_name: str, column_name: str) -> bool:
    with schema_editor.connection.cursor() as cursor:
        columns = [
            col.name
            for col in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        ]
    return column_name in columns


def _add_field(schema_editor, model, field_name: str, field: models.Field) -> None:
    field.set_attributes_from_name(field_name)
    schema_editor.add_field(model, field)


def forwards(apps, schema_editor):
    User = apps.get_model('users', 'User')

    # ── User maydonlari (eski VPS schema → yangi) ─────────────────────────
    if not _column_exists(schema_editor, 'users_user', 'role'):
        _add_field(
            schema_editor,
            User,
            'role',
            models.CharField(
                max_length=20,
                choices=[
                    ('customer', 'Mijoz'),
                    ('owner', 'Tashkilot egasi'),
                    ('branch_staff', 'Filial xodimi'),
                    ('admin', 'Admin'),
                ],
                default='customer',
                db_index=True,
            ),
        )

    if not _column_exists(schema_editor, 'users_user', 'is_phone_verified'):
        _add_field(
            schema_editor,
            User,
            'is_phone_verified',
            models.BooleanField(
                default=False,
                help_text="SMS OTP orqali tasdiqlangan (register 2-qadamida True bo'ladi)",
            ),
        )

    # ── OTPCode jadvali ────────────────────────────────────────────────────
    if not _table_exists(schema_editor, 'users_otpcode'):
        OTPCode = apps.get_model('users', 'OTPCode')
        schema_editor.create_model(OTPCode)

    # ── UserDevice jadvali ─────────────────────────────────────────────────
    if not _table_exists(schema_editor, 'users_userdevice'):
        UserDevice = apps.get_model('users', 'UserDevice')
        schema_editor.create_model(UserDevice)


def backwards(apps, schema_editor):
    # Production rollback kerak emas — bo'sh qoldiramiz
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        # State ni Django model bilan sinxronlashtirish (makemigrations --check uchun)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='OTPCode',
                    fields=[
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('phone', models.CharField(db_index=True, max_length=20)),
                        ('code', models.CharField(max_length=10)),
                        ('purpose', models.CharField(
                            choices=[('register', "Ro'yxatdan o'tish"), ('password_reset', 'Parolni tiklash')],
                            default='register', max_length=20,
                        )),
                        ('is_used', models.BooleanField(default=False)),
                        ('expires_at', models.DateTimeField()),
                        ('attempts', models.PositiveSmallIntegerField(default=0)),
                    ],
                    options={
                        'verbose_name': 'OTP Kod',
                        'verbose_name_plural': 'OTP Kodlar',
                        'ordering': ['-created_at'],
                    },
                ),
                migrations.CreateModel(
                    name='UserDevice',
                    fields=[
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('device_type', models.CharField(max_length=20, choices=[
                            ('mobile', 'Mobile (Flutter)'),
                            ('telegram', 'Telegram Mini App'),
                            ('web_crm', 'Web CRM'),
                            ('web_admin', 'Web Admin'),
                        ])),
                        ('refresh_token_jti', models.CharField(
                            max_length=255, unique=True,
                            help_text='JWT refresh tokenning JTI claim qiymati',
                        )),
                        ('fcm_token', models.CharField(blank=True, max_length=255, null=True)),
                        ('device_name', models.CharField(blank=True, max_length=100)),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                        ('last_active', models.DateTimeField(auto_now=True)),
                        ('is_active', models.BooleanField(default=True)),
                        ('user', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='devices', to='users.user',
                        )),
                    ],
                    options={
                        'verbose_name': 'Foydalanuvchi qurilmasi',
                        'verbose_name_plural': 'Foydalanuvchi qurilmalari',
                        'ordering': ['-last_active'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
