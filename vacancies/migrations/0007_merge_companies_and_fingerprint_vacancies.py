from collections import defaultdict

from django.db import migrations

from vacancies.dedup import company_key, vacancy_fingerprint

BATCH_SIZE = 500


def merge_companies(apps, schema_editor):
    Company = apps.get_model("vacancies", "Company")
    Vacancy = apps.get_model("vacancies", "Vacancy")
    groups = defaultdict(list)
    for company in Company.objects.order_by("pk"):
        groups[company_key(company.name)].append(company)
    for key, (kept, *duplicates) in groups.items():
        if duplicates:
            Vacancy.objects.filter(company__in=duplicates).update(company=kept)
            kept.website = kept.website or next((c.website for c in duplicates if c.website), "")
            Company.objects.filter(pk__in=[company.pk for company in duplicates]).delete()
        kept.slug = f"merge-{kept.pk}"
        kept.save(update_fields=("slug", "website"))
    for key, (kept, *_) in groups.items():
        kept.slug = key
        kept.save(update_fields=("slug",))


def fingerprint_vacancies(apps, schema_editor):
    Vacancy = apps.get_model("vacancies", "Vacancy")
    vacancies = list(Vacancy.objects.select_related("company"))
    for vacancy in vacancies:
        vacancy.fingerprint = vacancy_fingerprint(
            company=vacancy.company.slug if vacancy.company else "",
            title=vacancy.title,
            fallback=f"{vacancy.source_id}:{vacancy.external_id}",
        )
    Vacancy.objects.bulk_update(vacancies, ("fingerprint",), batch_size=BATCH_SIZE)


class Migration(migrations.Migration):
    dependencies = [("vacancies", "0006_vacancy_fingerprint")]

    operations = [
        migrations.RunPython(merge_companies, migrations.RunPython.noop),
        migrations.RunPython(fingerprint_vacancies, migrations.RunPython.noop),
    ]
