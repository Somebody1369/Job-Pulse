from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(blank=True, max_length=64)),
                ('category_label', models.CharField(max_length=128)),
                ('calculated_on', models.DateField()),
                ('active_candidates', models.PositiveIntegerField()),
                ('expected_min', models.PositiveIntegerField()),
                ('expected_max', models.PositiveIntegerField()),
                ('offers_per_candidate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('vacancies_online', models.PositiveIntegerField()),
                ('vacancies_change', models.IntegerField(blank=True, null=True)),
                ('offered_min', models.PositiveIntegerField()),
                ('offered_max', models.PositiveIntegerField()),
                ('applications_per_vacancy', models.DecimalField(decimal_places=1, max_digits=8)),
                ('djinni_index', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ('offers_30d', models.PositiveIntegerField(blank=True, null=True)),
                ('applications_30d', models.PositiveIntegerField(blank=True, null=True)),
                ('fetched_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-calculated_on', 'category'),
                'constraints': [models.UniqueConstraint(fields=('category', 'calculated_on'), name='market_snapshot_unique_per_day')],
            },
        ),
    ]
