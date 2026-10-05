from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0004_vacancy_salary_range'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='website',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='scraperun',
            name='failed_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='scraperun',
            name='kind',
            field=models.CharField(choices=[('feed', 'Feed'), ('details', 'Details')], default='feed', max_length=16),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='details_fetched_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='english_level',
            field=models.CharField(blank=True, choices=[('A1', 'A1 Beginner'), ('A2', 'A2 Elementary'), ('B1', 'B1 Intermediate'), ('B2', 'B2 Upper-intermediate'), ('C1', 'C1 Advanced'), ('C2', 'C2 Proficient')], max_length=2),
        ),
        migrations.AddField(
            model_name='vacancy',
            name='experience_months',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
