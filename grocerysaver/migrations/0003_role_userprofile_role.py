from django.db import migrations, models
import django.db.models.deletion


def seed_roles(apps, schema_editor):
    Role = apps.get_model('grocerysaver', 'Role')
    UserProfile = apps.get_model('grocerysaver', 'UserProfile')

    customer_role, _ = Role.objects.get_or_create(
        name='customer',
        defaults={'description': 'Cliente de la aplicacion'},
    )
    Role.objects.get_or_create(
        name='admin',
        defaults={'description': 'Administrador de la aplicacion'},
    )

    UserProfile.objects.filter(role__isnull=True).update(role=customer_role)


def unseed_roles(apps, schema_editor):
    Role = apps.get_model('grocerysaver', 'Role')
    Role.objects.filter(name__in=['customer', 'admin']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('grocerysaver', '0002_userprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='userprofile',
            name='role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='profiles',
                to='grocerysaver.role',
            ),
        ),
        migrations.RunPython(seed_roles, unseed_roles),
    ]
