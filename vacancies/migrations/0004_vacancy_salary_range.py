from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0003_seed_skills'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='salary_currency',
            field=models.CharField(blank=True, max_length=3),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='salary_max',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='salary_max_usd',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='salary_min',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='salary_min_usd',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='vacancy',
            constraint=models.CheckConstraint(condition=models.Q(('salary_min__isnull', True), ('salary_max__isnull', True), ('salary_min__lte', models.F('salary_max')), _connector='OR'), name='vacancy_salary_range_valid'),
        ),
    ]
