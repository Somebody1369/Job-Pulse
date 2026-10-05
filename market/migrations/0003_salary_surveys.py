import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0002_market_snapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalarySurvey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(max_length=32, unique=True)),
                ('period', models.DateField(unique=True)),
                ('source_url', models.URLField()),
                ('response_count', models.PositiveIntegerField(default=0)),
                ('imported_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-period',),
            },
        ),
        migrations.CreateModel(
            name='SalaryResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('salary_usd', models.PositiveIntegerField()),
                ('experience_years', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('programming_language', models.CharField(blank=True, max_length=64)),
                ('position', models.CharField(blank=True, max_length=128)),
                ('seniority', models.CharField(blank=True, max_length=64)),
                ('english_level', models.CharField(blank=True, max_length=32)),
                ('survey', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='market.salarysurvey')),
            ],
            options={
                'indexes': [models.Index(fields=['survey', 'programming_language'], name='salary_survey_language_idx')],
            },
        ),
    ]
