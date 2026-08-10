"""Data migration: convert legacy ADMIN role rows to SUPER_ADMIN."""

from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="ADMIN").update(role="SUPER_ADMIN")


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="SUPER_ADMIN").update(role="ADMIN")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_role_departmentadmin"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
