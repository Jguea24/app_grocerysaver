import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('grocerysaver', '0012_productcode'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackgroundJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('job_type', models.CharField(choices=[('export_products_csv', 'Export products CSV')], max_length=50)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='queued', max_length=20)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('error', models.TextField(blank=True)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='background_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='backgroundjob',
            index=models.Index(fields=['status', 'created_at'], name='grocerysave_status_11bbe6_idx'),
        ),
        migrations.AddIndex(
            model_name='backgroundjob',
            index=models.Index(fields=['job_type', 'created_at'], name='grocerysave_job_typ_0bd236_idx'),
        ),
    ]
