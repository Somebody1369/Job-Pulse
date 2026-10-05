from django.db import migrations
from django.utils.text import slugify

SKILLS = (
    ("Python", ()),
    ("Java", ()),
    ("JavaScript", ("JS",)),
    ("TypeScript", ()),
    ("Go", ("Golang", "golang")),
    ("C#", ()),
    ("C++", ("cpp",)),
    (".NET", ("dotnet", "ASP.NET")),
    ("PHP", ()),
    ("Ruby", ()),
    ("Rust", ()),
    ("Kotlin", ()),
    ("Swift", ()),
    ("Scala", ()),
    ("SQL", ()),
    ("Django", ()),
    ("Django REST Framework", ("DRF",)),
    ("FastAPI", ()),
    ("Flask", ()),
    ("Celery", ()),
    ("SQLAlchemy", ()),
    ("asyncio", ()),
    ("Pydantic", ()),
    ("React", ("React.js", "ReactJS")),
    ("Angular", ()),
    ("Vue.js", ("Vue", "VueJS")),
    ("Node.js", ("NodeJS", "Node")),
    ("Next.js", ("NextJS",)),
    ("Spring", ("Spring Boot",)),
    ("Laravel", ()),
    ("Pandas", ()),
    ("NumPy", ()),
    ("PyTorch", ()),
    ("TensorFlow", ()),
    ("scikit-learn", ("sklearn",)),
    ("Apache Airflow", ("Airflow",)),
    ("Apache Spark", ("Spark", "PySpark")),
    ("Machine Learning", ("ML",)),
    ("LLM", ("LLMs",)),
    ("LangChain", ()),
    ("PostgreSQL", ("Postgres",)),
    ("MySQL", ()),
    ("MongoDB", ("Mongo",)),
    ("Redis", ()),
    ("Elasticsearch", ("Elastic Search",)),
    ("ClickHouse", ()),
    ("Kafka", ()),
    ("RabbitMQ", ()),
    ("Docker", ()),
    ("Kubernetes", ("K8s",)),
    ("AWS", ("Amazon Web Services",)),
    ("GCP", ("Google Cloud",)),
    ("Azure", ()),
    ("Terraform", ()),
    ("Linux", ()),
    ("Git", ()),
    ("CI/CD", ()),
    ("REST", ("RESTful",)),
    ("GraphQL", ()),
    ("gRPC", ()),
    ("Pytest", ()),
    ("Selenium", ()),
    ("Playwright", ()),
    ("Scrapy", ()),
    ("BeautifulSoup", ("Beautiful Soup", "bs4")),
)

CASE_SENSITIVE_SKILLS = frozenset(
    {"Go", "Swift", "React", "Node.js", "Spring", "Apache Spark", "Machine Learning", "LLM", "REST"}
)
SLUG_REPLACEMENTS = {"#": "sharp", "+": "plus"}


def skill_slug(name):
    if name.startswith("."):
        name = f"dot{name[1:]}"
    for char, replacement in SLUG_REPLACEMENTS.items():
        name = name.replace(char, replacement)
    return slugify(name)


def seed_skills(apps, schema_editor):
    Skill = apps.get_model("vacancies", "Skill")
    for name, aliases in SKILLS:
        Skill.objects.update_or_create(
            name=name,
            defaults={
                "slug": skill_slug(name),
                "aliases": list(aliases),
                "is_case_sensitive": name in CASE_SENSITIVE_SKILLS,
            },
        )


def remove_skills(apps, schema_editor):
    Skill = apps.get_model("vacancies", "Skill")
    Skill.objects.filter(name__in=[name for name, _ in SKILLS]).delete()


class Migration(migrations.Migration):
    dependencies = [("vacancies", "0002_seed_sources")]

    operations = [migrations.RunPython(seed_skills, remove_skills)]
