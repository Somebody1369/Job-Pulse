import django.contrib.postgres.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(allow_unicode=True, max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': 'companies',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Skill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True)),
                ('slug', models.SlugField(max_length=64, unique=True)),
                ('aliases', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=64), blank=True, default=list)),
                ('is_case_sensitive', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=32, unique=True)),
                ('name', models.CharField(max_length=64)),
                ('homepage', models.URLField()),
                ('kind', models.CharField(choices=[('rss', 'RSS feed'), ('api', 'API'), ('html', 'HTML pages')], max_length=8)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='ScrapeRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categories', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=64), blank=True, default=list)),
                ('status', models.CharField(choices=[('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='running', max_length=16)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('fetched_count', models.PositiveIntegerField(default=0)),
                ('created_count', models.PositiveIntegerField(default=0)),
                ('updated_count', models.PositiveIntegerField(default=0)),
                ('error', models.TextField(blank=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='vacancies.source')),
            ],
            options={
                'ordering': ('-started_at',),
                'indexes': [models.Index(fields=['source', '-started_at'], name='scraperun_source_started_idx')],
            },
        ),
        migrations.CreateModel(
            name='Vacancy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(max_length=64)),
                ('url', models.URLField(max_length=1000)),
                ('title', models.CharField(max_length=500)),
                ('categories', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=64), blank=True, default=list)),
                ('locations', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=128), blank=True, default=list)),
                ('is_remote', models.BooleanField(blank=True, null=True)),
                ('salary_text', models.CharField(blank=True, max_length=64)),
                ('description', models.TextField(blank=True)),
                ('description_html', models.TextField(blank=True)),
                ('published_at', models.DateTimeField()),
                ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vacancies', to='vacancies.company')),
                ('skills', models.ManyToManyField(blank=True, related_name='vacancies', to='vacancies.skill')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vacancies', to='vacancies.source')),
            ],
            options={
                'verbose_name_plural': 'vacancies',
                'ordering': ('-published_at',),
                'indexes': [models.Index(fields=['-published_at'], name='vacancy_published_idx'), django.contrib.postgres.indexes.GinIndex(fields=['categories'], name='vacancy_categories_gin')],
                'constraints': [models.UniqueConstraint(fields=('source', 'external_id'), name='vacancy_unique_per_source')],
            },
        ),
    ]
