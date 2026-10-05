from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriber',
            name='weekly_report',
            field=models.BooleanField(default=False),
        ),
    ]
