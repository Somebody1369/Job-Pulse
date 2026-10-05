from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.views import (
    CompanyViewSet,
    LatestReportView,
    MarketOverviewView,
    MarketSnapshotViewSet,
    NotificationViewSet,
    SalaryDynamicsView,
    SalaryStatisticsView,
    SkillDemandView,
    SkillViewSet,
    SubscriberViewSet,
    SubscriptionViewSet,
    VacancyViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register("vacancies", VacancyViewSet, basename="vacancy")
router.register("skills", SkillViewSet, basename="skill")
router.register("companies", CompanyViewSet, basename="company")
router.register("market/snapshots", MarketSnapshotViewSet, basename="market-snapshot")
router.register("subscribers", SubscriberViewSet, basename="subscriber")
router.register("notifications", NotificationViewSet, basename="notification")

subscriptions = SubscriptionViewSet.as_view({"get": "list", "post": "create"})
subscription = SubscriptionViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = [
    path("v1/market/overview/", MarketOverviewView.as_view(), name="market-overview"),
    path("v1/salaries/", SalaryStatisticsView.as_view(), name="salaries"),
    path("v1/salaries/dynamics/", SalaryDynamicsView.as_view(), name="salary-dynamics"),
    path("v1/skills/demand/", SkillDemandView.as_view(), name="skill-demand"),
    path("v1/reports/latest/", LatestReportView.as_view(), name="latest-report"),
    path(
        "v1/subscribers/<int:subscriber_chat_id>/subscriptions/",
        subscriptions,
        name="subscription-list",
    ),
    path(
        "v1/subscribers/<int:subscriber_chat_id>/subscriptions/<int:pk>/",
        subscription,
        name="subscription-detail",
    ),
    path("v1/", include(router.urls)),
    path("v1/auth/token/", TokenObtainPairView.as_view(), name="token"),
    path("v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
]
