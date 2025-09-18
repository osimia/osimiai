# Generated migration for uploaded_by field

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge', '0002_knowledgedocument_delete_document'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgedocument',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Загружен пользователем'),
        ),
    ]
