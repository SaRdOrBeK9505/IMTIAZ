from django.db import migrations, models


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


def add_email_if_missing(apps, schema_editor):
    User = apps.get_model('users', 'User')
    if not _column_exists(schema_editor, 'users_user', 'email'):
        _add_field(
            schema_editor,
            User,
            'email',
            models.EmailField(blank=True, default='', max_length=254),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_sync_otpcode_userdevice_and_user_fields'),
    ]

    operations = [
        migrations.RunPython(add_email_if_missing, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='user',
                    name='email',
                    field=models.EmailField(blank=True, default='', max_length=254),
                ),
            ],
            database_operations=[],
        ),
    ]
