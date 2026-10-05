from django.contrib import admin

from subscriptions.models import Delivery, Subscriber, Subscription


class SubscriptionInline(admin.TabularInline[Subscription, Subscriber]):
    model = Subscription
    extra = 0
    filter_horizontal = ("skills",)


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin[Subscriber]):
    list_display = ("chat_id", "username", "created_at")
    search_fields = ("username",)
    inlines = (SubscriptionInline,)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin[Delivery]):
    list_display = ("subscription", "vacancy", "delivered_at")
    list_select_related = ("subscription__subscriber", "vacancy")
    date_hierarchy = "delivered_at"
