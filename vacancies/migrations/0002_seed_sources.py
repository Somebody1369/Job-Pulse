from django.db import migrations

SOURCES = (
    {"code": "dou", "name": "DOU", "homepage": "https://jobs.dou.ua/", "kind": "rss"},
    {"code": "djinni", "name": "Djinni", "homepage": "https://djinni.co/jobs/", "kind": "rss"},
)


def seed_sources(apps, schema_editor):
    Source = apps.get_model("vacancies", "Source")
    for source in SOURCES:
        Source.objects.update_or_create(code=source["code"], defaults=source)


def remove_sources(apps, schema_editor):
    Source = apps.get_model("vacancies", "Source")
    Source.objects.filter(code__in=[source["code"] for source in SOURCES]).delete()


class Migration(migrations.Migration):
    dependencies = [("vacancies", "0001_initial")]

    operations = [migrations.RunPython(seed_sources, remove_sources)]
