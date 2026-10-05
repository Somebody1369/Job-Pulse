from typing import Any, ClassVar, override

from rest_framework import serializers

from analytics.dashboard import PERIOD_CHOICES
from market.models import MarketSnapshot
from subscriptions.models import Subscriber, Subscription
from vacancies.models import Company, Skill, Source, Vacancy


class SkillSerializer(serializers.ModelSerializer[Skill]):
    vacancy_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Skill
        fields = ("name", "slug", "aliases", "vacancy_count")


class CompanySerializer(serializers.ModelSerializer[Company]):
    class Meta:
        model = Company
        fields = ("name", "slug", "website")


class SalarySerializer(serializers.Serializer[Vacancy]):
    text = serializers.CharField(source="salary_text")
    min = serializers.IntegerField(source="salary_min", allow_null=True)
    max = serializers.IntegerField(source="salary_max", allow_null=True)
    currency = serializers.CharField(source="salary_currency")
    min_usd = serializers.IntegerField(source="salary_min_usd", allow_null=True)
    max_usd = serializers.IntegerField(source="salary_max_usd", allow_null=True)


class VacancySerializer(serializers.ModelSerializer[Vacancy]):
    board: serializers.SlugRelatedField[Source] = serializers.SlugRelatedField(
        source="source", slug_field="code", read_only=True
    )
    company = CompanySerializer(read_only=True, allow_null=True)
    skills: serializers.SlugRelatedField[Skill] = serializers.SlugRelatedField(
        slug_field="name", many=True, read_only=True
    )
    salary = SalarySerializer(source="*", read_only=True)

    class Meta:
        model = Vacancy
        fields: tuple[str, ...] = (
            "id",
            "title",
            "url",
            "board",
            "company",
            "categories",
            "locations",
            "is_remote",
            "salary",
            "experience_months",
            "english_level",
            "skills",
            "published_at",
        )


class VacancyDetailSerializer(VacancySerializer):
    class Meta(VacancySerializer.Meta):
        fields = (*VacancySerializer.Meta.fields, "description")


class MarketSnapshotSerializer(serializers.ModelSerializer[MarketSnapshot]):
    candidates_per_vacancy = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = MarketSnapshot
        fields = (
            "category",
            "category_label",
            "calculated_on",
            "active_candidates",
            "vacancies_online",
            "vacancies_change",
            "candidates_per_vacancy",
            "expected_min",
            "expected_max",
            "offered_min",
            "offered_max",
            "offers_per_candidate",
            "applications_per_vacancy",
            "djinni_index",
        )


class SalaryRowSerializer(serializers.Serializer[Any]):
    group = serializers.CharField()
    responses = serializers.IntegerField()
    p25 = serializers.IntegerField()
    median = serializers.IntegerField()
    p75 = serializers.IntegerField()


class SalaryPointSerializer(serializers.Serializer[Any]):
    period = serializers.DateField()
    responses = serializers.IntegerField()
    median = serializers.IntegerField()


class SkillDemandSerializer(serializers.Serializer[Any]):
    skill = serializers.CharField()
    current = serializers.IntegerField()
    previous = serializers.IntegerField()
    change = serializers.IntegerField()


class SalaryQuerySerializer(serializers.Serializer[Any]):
    language = serializers.CharField(default="Python")
    group = serializers.ChoiceField(choices=("seniority", "experience"), default="seniority")


class LanguageQuerySerializer(serializers.Serializer[Any]):
    language = serializers.CharField(default="Python")


class DemandQuerySerializer(serializers.Serializer[Any]):
    days = serializers.ChoiceField(choices=PERIOD_CHOICES, default=PERIOD_CHOICES[0])


class SubscriberSerializer(serializers.ModelSerializer[Subscriber]):
    class Meta:
        model = Subscriber
        fields = ("chat_id", "username", "created_at")
        read_only_fields = ("created_at",)
        extra_kwargs: ClassVar[dict[str, dict[str, Any]]] = {"chat_id": {"validators": []}}


class SubscriptionSerializer(serializers.ModelSerializer[Subscription]):
    skills = serializers.SlugRelatedField(
        slug_field="slug", many=True, queryset=Skill.objects.all(), required=False
    )

    class Meta:
        model = Subscription
        fields = (
            "id",
            "skills",
            "remote_only",
            "min_salary_usd",
            "max_experience_years",
            "is_active",
            "created_at",
        )
        read_only_fields = ("created_at",)


class NotificationSerializer(serializers.Serializer[Any]):
    subscription = serializers.IntegerField(source="subscription.pk")
    chat_id = serializers.IntegerField(source="subscription.subscriber.chat_id")
    vacancy = VacancySerializer()


class NotificationQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(min_value=1, max_value=50, default=10)


class DeliverySerializer(serializers.Serializer[Any]):
    subscription = serializers.IntegerField(min_value=1)
    vacancy = serializers.IntegerField(min_value=1)


class AcknowledgeSerializer(serializers.Serializer[Any]):
    deliveries = DeliverySerializer(many=True, allow_empty=False)

    @override
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs["pairs"] = [(item["subscription"], item["vacancy"]) for item in attrs["deliveries"]]
        return attrs
