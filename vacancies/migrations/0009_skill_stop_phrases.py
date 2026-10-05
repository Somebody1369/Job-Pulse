import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0008_vacancy_search_vector'),
    ]

    operations = [
        migrations.AddField(
            model_name='skill',
            name='stop_phrases',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=64), blank=True, default=list),
        ),
    ]
