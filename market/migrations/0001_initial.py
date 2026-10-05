from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ExchangeRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency', models.CharField(max_length=3)),
                ('rate_date', models.DateField()),
                ('uah_per_unit', models.DecimalField(decimal_places=6, max_digits=16)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-rate_date', 'currency'),
                'constraints': [models.UniqueConstraint(fields=('currency', 'rate_date'), name='exchange_rate_unique_per_day'), models.CheckConstraint(condition=models.Q(('uah_per_unit__gt', 0)), name='exchange_rate_positive')],
            },
        ),
    ]
