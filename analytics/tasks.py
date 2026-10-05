from celery import shared_task

from analytics.reports import render_dashboard_report as render_report


@shared_task
def render_dashboard_report() -> int:
    return render_report().pk
