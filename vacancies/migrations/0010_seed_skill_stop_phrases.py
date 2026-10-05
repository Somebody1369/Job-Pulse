from django.db import migrations

STOP_PHRASES = {"Go": ["Go-to", "Go-live"], "Swift": ["Swift Punk"]}


def seed_stop_phrases(apps, schema_editor):
    Skill = apps.get_model("vacancies", "Skill")
    for name, phrases in STOP_PHRASES.items():
        Skill.objects.filter(name=name).update(stop_phrases=phrases)


def clear_stop_phrases(apps, schema_editor):
    Skill = apps.get_model("vacancies", "Skill")
    Skill.objects.filter(name__in=STOP_PHRASES).update(stop_phrases=[])


class Migration(migrations.Migration):
    dependencies = [("vacancies", "0009_skill_stop_phrases")]

    operations = [migrations.RunPython(seed_stop_phrases, clear_stop_phrases)]
