import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0007_merge_companies_and_fingerprint_vacancies'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='search_vector',
            field=models.GeneratedField(db_persist=True, expression=django.contrib.postgres.search.CombinedSearchVector(django.contrib.postgres.search.SearchVector('title', config='english', weight='A'), '||', django.contrib.postgres.search.SearchVector('description', config='english', weight='B'), django.contrib.postgres.search.SearchConfig('english')), output_field=django.contrib.postgres.search.SearchVectorField()),
        ),
        migrations.AddIndex(
            model_name='vacancy',
            index=django.contrib.postgres.indexes.GinIndex(fields=['search_vector'], name='vacancy_search_gin'),
        ),
    ]
