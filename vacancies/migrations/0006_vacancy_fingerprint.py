from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0005_vacancy_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='fingerprint',
            field=models.CharField(db_index=True, default='', editable=False, max_length=64),
        ),
    ]
