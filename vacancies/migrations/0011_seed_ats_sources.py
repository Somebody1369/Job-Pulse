from django.db import migrations

SOURCES = (
    {"code": "greenhouse", "name": "Greenhouse", "homepage": "https://www.greenhouse.com/", "kind": "api"},
    {"code": "lever", "name": "Lever", "homepage": "https://www.lever.co/", "kind": "api"},
)


def seed_sources(apps, schema_editor):
    Source = apps.get_model("vacancies", "Source")
    for source in SOURCES:
        Source.objects.update_or_create(code=source["code"], defaults=source)


def remove_sources(apps, schema_editor):
    Source = apps.get_model("vacancies", "Source")
    Source.objects.filter(code__in=[source["code"] for source in SOURCES]).delete()


class Migration(migrations.Migration):
    dependencies = [("vacancies", "0010_seed_skill_stop_phrases")]

    operations = [migrations.RunPython(seed_sources, remove_sources)]
