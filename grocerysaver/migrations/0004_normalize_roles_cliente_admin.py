from django.db import migrations


def normalize_roles(apps, schema_editor):
    Role = apps.get_model('grocerysaver', 'Role')
    UserProfile = apps.get_model('grocerysaver', 'UserProfile')

    cliente_role, _ = Role.objects.get_or_create(
        name='cliente',
        defaults={'description': 'Cliente de la aplicacion'},
    )
    Role.objects.get_or_create(
        name='admin',
        defaults={'description': 'Administrador de la aplicacion'},
    )

    UserProfile.objects.filter(role__name='customer').update(role=cliente_role)
    Role.objects.filter(name='customer').delete()


def rollback_roles(apps, schema_editor):
    Role = apps.get_model('grocerysaver', 'Role')
    UserProfile = apps.get_model('grocerysaver', 'UserProfile')

    customer_role, _ = Role.objects.get_or_create(
        name='customer',
        defaults={'description': 'Cliente de la aplicacion'},
    )

    UserProfile.objects.filter(role__name='cliente').update(role=customer_role)
    Role.objects.filter(name='cliente').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('grocerysaver', '0003_role_userprofile_role'),
    ]

    operations = [
        migrations.RunPython(normalize_roles, rollback_roles),
    ]
