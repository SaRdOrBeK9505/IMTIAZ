# Booking settlement saga — BookingSettlement + BookingTransactionLog

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_alter_payment_provider_alifpay_only'),
        ('booking', '0008_alter_booking_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingSettlement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Kutilmoqda'),
                        ('price_locked', 'Narx qulflangan (pre-flight OK)'),
                        ('payment_captured', 'Mijoz to\'lovi qabul qilindi'),
                        ('bookhara_settling', 'Bookhara settlement jarayonda'),
                        ('bookhara_confirmed', 'Bookhara tasdiqladi'),
                        ('completed', 'Yakunlandi'),
                        ('bookhara_failed', 'Bookhara settlement xato'),
                        ('refund_pending', 'Qaytarish kutilmoqda'),
                        ('refunded', 'Mijozga qaytarildi'),
                        ('failed', 'Amalga oshmadi'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=32,
                )),
                ('idempotency_key', models.CharField(
                    db_index=True,
                    help_text='Bookhara pay_booking uchun noyob kalit',
                    max_length=64,
                    unique=True,
                )),
                ('locked_price', models.DecimalField(
                    blank=True,
                    decimal_places=2,
                    help_text='Pre-flight da qulflangan Bookhara narxi (UZS)',
                    max_digits=14,
                    null=True,
                )),
                ('bookhara_deposit_at_preflight', models.DecimalField(
                    blank=True,
                    decimal_places=2,
                    help_text='Pre-flight vaqtidagi depozit balansi',
                    max_digits=14,
                    null=True,
                )),
                ('last_error_code', models.CharField(blank=True, max_length=64)),
                ('last_error_message', models.TextField(blank=True)),
                ('retry_count', models.PositiveSmallIntegerField(default=0)),
                ('refund_attempts', models.PositiveSmallIntegerField(default=0)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('booking', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='settlement',
                    to='booking.booking',
                )),
                ('payment', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='settlements',
                    to='payments.payment',
                )),
            ],
            options={
                'verbose_name': 'Bron settlement (saga)',
                'verbose_name_plural': 'Bron settlementlar (saga)',
            },
        ),
        migrations.CreateModel(
            name='BookingTransactionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('step', models.CharField(
                    choices=[
                        ('pre_flight_start', 'Pre-flight boshlandi'),
                        ('pre_flight_ok', 'Pre-flight muvaffaqiyatli'),
                        ('pre_flight_failed', 'Pre-flight rad etildi'),
                        ('payment_initiated', 'To\'lov boshlandi'),
                        ('payment_captured', 'To\'lov qabul qilindi'),
                        ('bookhara_settle_start', 'Bookhara settlement boshlandi'),
                        ('bookhara_settle_ok', 'Bookhara settlement OK'),
                        ('bookhara_settle_failed', 'Bookhara settlement xato'),
                        ('bookhara_cancel_hold', 'Bookhara hold bekor qilindi'),
                        ('refund_start', 'Qaytarish boshlandi'),
                        ('refund_ok', 'Qaytarish muvaffaqiyatli'),
                        ('refund_failed', 'Qaytarish xato'),
                        ('deposit_check', 'Depozit balans tekshiruvi'),
                    ],
                    db_index=True,
                    max_length=64,
                )),
                ('from_status', models.CharField(blank=True, max_length=32)),
                ('to_status', models.CharField(blank=True, max_length=32)),
                ('success', models.BooleanField(default=True)),
                ('message', models.TextField(blank=True)),
                ('provider_response', models.JSONField(blank=True, null=True)),
                ('error_code', models.CharField(blank=True, max_length=64)),
                ('settlement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transaction_logs',
                    to='booking.bookingsettlement',
                )),
            ],
            options={
                'verbose_name': 'Bron transaction log',
                'verbose_name_plural': 'Bron transaction loglari',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='bookingsettlement',
            index=models.Index(fields=['status', 'created_at'], name='booking_set_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingtransactionlog',
            index=models.Index(fields=['settlement', 'step'], name='booking_tx_settlement_step_idx'),
        ),
    ]
