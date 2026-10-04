from django.contrib import admin
from .models import (
    Region, Crop, CultivationStage, WeatherReading, SmsAlert, ChatMessage,
    NewsPost, Event, PageContent, AdvisoryOverride, NewsletterSubscriber, CropDiagnosis,
    FarmerProfile, ForumPost, ForumComment,
    Community, PartnerLogo, TeamMember, HeroMedia, Notification,
    NdviReading, AdvisoryFeedback, ExpertRequest, Cooperative, InstitutionalPartner,
)


@admin.register(Cooperative)
class CooperativeAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "manager")


@admin.register(InstitutionalPartner)
class InstitutionalPartnerAdmin(admin.ModelAdmin):
    list_display = ("organization_name", "user", "approved")
    list_filter = ("approved",)


class CultivationStageInline(admin.TabularInline):
    model = CultivationStage
    extra = 0


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "zone", "soil_type", "rain_start_month", "rain_end_month", "rain_peak_mm")


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "sow_window_start_month", "sow_window_end_month", "cycle_days", "water_need")
    inlines = [CultivationStageInline]


@admin.register(WeatherReading)
class WeatherReadingAdmin(admin.ModelAdmin):
    list_display = ("region", "date", "rainfall_mm", "temperature_c", "source")
    list_filter = ("region", "source")


@admin.register(SmsAlert)
class SmsAlertAdmin(admin.ModelAdmin):
    list_display = ("region", "crop", "status", "created_at")
    list_filter = ("status", "region")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session_id", "role", "created_at")
    list_filter = ("role",)


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "is_published")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_date", "location")


@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "updated_at")


@admin.register(AdvisoryOverride)
class AdvisoryOverrideAdmin(admin.ModelAdmin):
    list_display = ("region", "crop", "updated_at", "updated_by")


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "subscribed_at")


@admin.register(CropDiagnosis)
class CropDiagnosisAdmin(admin.ModelAdmin):
    list_display = ("region", "crop", "created_at")
    list_filter = ("region", "crop")


@admin.register(FarmerProfile)
class FarmerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "country", "region", "created_at")
    list_filter = ("country",)


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created_at")


@admin.register(ForumComment)
class ForumCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "created_at")


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")


@admin.register(PartnerLogo)
class PartnerLogoAdmin(admin.ModelAdmin):
    list_display = ("name", "order")


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "title", "role", "order")


@admin.register(HeroMedia)
class HeroMediaAdmin(admin.ModelAdmin):
    list_display = ("title", "order")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created_at")


@admin.register(NdviReading)
class NdviReadingAdmin(admin.ModelAdmin):
    list_display = ("region", "date", "ndvi_value", "source")
    list_filter = ("region",)


@admin.register(AdvisoryFeedback)
class AdvisoryFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "region", "crop", "followed_advice", "outcome", "created_at")
    list_filter = ("followed_advice", "outcome")


@admin.register(ExpertRequest)
class ExpertRequestAdmin(admin.ModelAdmin):
    list_display = ("region", "crop", "status", "created_at")
    list_filter = ("status",)
