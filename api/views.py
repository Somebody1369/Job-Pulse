from typing import Any, override

from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from analytics.queries import (
    latest_survey,
    salary_by_experience,
    salary_by_seniority,
    salary_dynamics,
    skill_demand,
)
from api.filters import VacancyFilter
from api.permissions import HasBotAccess
from api.serializers import (
    AcknowledgeSerializer,
    CompanySerializer,
    DemandQuerySerializer,
    LanguageQuerySerializer,
    MarketSnapshotSerializer,
    NotificationQuerySerializer,
    NotificationSerializer,
    SalaryPointSerializer,
    SalaryQuerySerializer,
    SalaryRowSerializer,
    SkillDemandSerializer,
    SkillSerializer,
    SubscriberSerializer,
    SubscriptionSerializer,
    VacancyDetailSerializer,
    VacancySerializer,
)
from market.models import MarketSnapshot
from subscriptions.models import Subscriber, Subscription
from subscriptions.services import acknowledge, pending_notifications
from vacancies.models import Company, Skill, Vacancy

SKILL_DEMAND_LIMIT = 30


class VacancyViewSet(viewsets.ReadOnlyModelViewSet[Vacancy]):
    permission_classes = (AllowAny,)
    queryset = Vacancy.objects.select_related("source", "company").prefetch_related("skills")
    filterset_class = VacancyFilter
    ordering_fields = ("published_at", "salary_min_usd", "salary_max_usd")
    ordering = ("-published_at",)

    @override
    def get_serializer_class(self) -> type[BaseSerializer[Vacancy]]:
        return VacancyDetailSerializer if self.action == "retrieve" else VacancySerializer


class SkillViewSet(viewsets.ReadOnlyModelViewSet[Skill]):
    permission_classes = (AllowAny,)
    serializer_class = SkillSerializer
    queryset = Skill.objects.annotate(vacancy_count=Count("vacancies"))
    lookup_field = "slug"
    ordering_fields = ("vacancy_count", "name")
    ordering = ("-vacancy_count", "name")


class CompanyViewSet(viewsets.ReadOnlyModelViewSet[Company]):
    permission_classes = (AllowAny,)
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    lookup_field = "slug"
    filter_backends = (SearchFilter,)
    search_fields = ("name",)


class MarketSnapshotViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[MarketSnapshot]):
    permission_classes = (AllowAny,)
    serializer_class = MarketSnapshotSerializer
    queryset = MarketSnapshot.objects.all()
    filterset_fields = ("category",)
    ordering_fields = ("calculated_on",)
    ordering = ("-calculated_on", "category")


class MarketOverviewView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=MarketSnapshotSerializer(many=True))
    def get(self, _request: Request) -> Response:
        latest = MarketSnapshot.objects.order_by("category", "-calculated_on").distinct("category")
        snapshots = sorted(
            latest, key=lambda snapshot: (snapshot.category != "", snapshot.category)
        )
        return Response(MarketSnapshotSerializer(snapshots, many=True).data)


class SalaryStatisticsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[SalaryQuerySerializer],
        responses={
            200: SalaryRowSerializer(many=True),
            404: OpenApiResponse(description="No salary survey has been imported"),
        },
    )
    def get(self, request: Request) -> Response:
        query = _validated(SalaryQuerySerializer, request.query_params)
        survey = latest_survey()
        if survey is None:
            raise NotFound("No salary survey has been imported")
        statistics = salary_by_seniority if query["group"] == "seniority" else salary_by_experience
        rows = statistics(survey, query["language"])
        return Response(SalaryRowSerializer(rows, many=True).data)


class SalaryDynamicsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(parameters=[LanguageQuerySerializer], responses=SalaryPointSerializer(many=True))
    def get(self, request: Request) -> Response:
        query = _validated(LanguageQuerySerializer, request.query_params)
        points = salary_dynamics(query["language"])
        return Response(SalaryPointSerializer(points, many=True).data)


class SkillDemandView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(parameters=[DemandQuerySerializer], responses=SkillDemandSerializer(many=True))
    def get(self, request: Request) -> Response:
        query = _validated(DemandQuerySerializer, request.query_params)
        rows = skill_demand(now=timezone.now(), days=int(query["days"]), limit=SKILL_DEMAND_LIMIT)
        return Response(SkillDemandSerializer(rows, many=True).data)


class SubscriberViewSet(
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[Subscriber],
):
    permission_classes = (HasBotAccess,)
    serializer_class = SubscriberSerializer
    queryset = Subscriber.objects.all()
    lookup_field = "chat_id"

    @extend_schema(
        request=SubscriberSerializer,
        responses={200: SubscriberSerializer, 201: SubscriberSerializer},
    )
    def create(self, request: Request) -> Response:
        serializer = SubscriberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscriber, created = Subscriber.objects.update_or_create(
            chat_id=serializer.validated_data["chat_id"],
            defaults={"username": serializer.validated_data.get("username", "")},
        )
        return Response(
            SubscriberSerializer(subscriber).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SubscriptionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[Subscription],
):
    permission_classes = (HasBotAccess,)
    serializer_class = SubscriptionSerializer
    pagination_class = None

    @override
    def get_queryset(self) -> QuerySet[Subscription]:
        if getattr(self, "swagger_fake_view", False):
            return Subscription.objects.none()
        return Subscription.objects.filter(
            subscriber__chat_id=self.kwargs["subscriber_chat_id"]
        ).prefetch_related("skills")

    @override
    def perform_create(self, serializer: BaseSerializer[Subscription]) -> None:
        subscriber = get_object_or_404(Subscriber, chat_id=self.kwargs["subscriber_chat_id"])
        serializer.save(subscriber=subscriber)


class NotificationViewSet(viewsets.ViewSet):
    permission_classes = (HasBotAccess,)

    @extend_schema(
        parameters=[NotificationQuerySerializer], responses=NotificationSerializer(many=True)
    )
    def list(self, request: Request) -> Response:
        query = _validated(NotificationQuerySerializer, request.query_params)
        notifications = pending_notifications(
            now=timezone.now(), limit_per_subscription=query["limit"]
        )
        return Response(NotificationSerializer(notifications, many=True).data)

    @extend_schema(request=AcknowledgeSerializer, responses={204: None})
    def create(self, request: Request) -> Response:
        serializer = AcknowledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        acknowledge(serializer.validated_data["pairs"])
        return Response(status=status.HTTP_204_NO_CONTENT)


def _validated(serializer_class: type[BaseSerializer[Any]], data: Any) -> dict[str, Any]:
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)
