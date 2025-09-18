# Generated migration for description field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0004_knowledgedocument_document_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgedocument',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Описание документа'),
        ),
    ]
