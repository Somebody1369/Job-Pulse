from typing import Any, override

from django.http import Http404, HttpRequest, HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView

from analytics.dashboard import Dashboard
from analytics.exports import EXPORTERS
from analytics.forms import FilterForm
from analytics.queries import latest_survey, market_categories, survey_languages


def build_dashboard(request: HttpRequest) -> tuple[Dashboard, FilterForm]:
    survey = latest_survey()
    form = FilterForm(
        request.GET or None,
        languages=survey_languages(survey) if survey else [],
        categories=market_categories(),
    )
    return Dashboard(form.filters(), survey=survey, now=timezone.now()), form


class DashboardView(TemplateView):
    template_name = "analytics/dashboard.html"

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        dashboard, form = build_dashboard(self.request)
        context.update(
            dashboard=dashboard,
            form=form,
            tables={name: dashboard.table(name) for name in dashboard.table_names},
            charts=dashboard.charts(),
            query=self.request.GET.urlencode(),
        )
        return context


def export_table(request: HttpRequest, name: str, extension: str) -> HttpResponse:
    dashboard, _ = build_dashboard(request)
    if name not in dashboard.table_names:
        raise Http404(f"Unknown table {name!r}")
    return EXPORTERS[extension](dashboard.table(name))
