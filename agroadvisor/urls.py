from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import (
    RegionViewSet, CropViewSet, AdvisoryView, SmsAlertViewSet, ChatView,
    AdminLoginView, AdminLogoutView, AdminSessionView, RegisterView,
    NewsPostViewSet, EventViewSet, PageContentViewSet, AdvisoryOverrideViewSet,
    NewsletterSubscribeView, GenerateRegionsView, GenerateCropsView, DiagnoseView,
    AdminStatsView, ForumPostViewSet, ForumCommentViewSet, ForumLikeToggleView,
    VerifyEmailView, ProfileView, DeleteUserView, UserListView,
    CommunityViewSet, PartnerLogoViewSet, TeamMemberViewSet, HeroMediaViewSet,
    NotificationViewSet, NdviView, AdvisoryFeedbackViewSet, ExpertRequestViewSet,
    CooperativeViewSet, InstitutionalPartnerViewSet, InstitutionalDashboardView,
    CsrfCookieView, HealthCheckView,
)

router = DefaultRouter()
router.register(r"regions", RegionViewSet, basename="region")
router.register(r"crops", CropViewSet, basename="crop")
router.register(r"sms-alerts", SmsAlertViewSet, basename="sms-alert")
router.register(r"news", NewsPostViewSet, basename="news")
router.register(r"events", EventViewSet, basename="event")
router.register(r"page-content", PageContentViewSet, basename="page-content")
router.register(r"advisory-overrides", AdvisoryOverrideViewSet, basename="advisory-override")
router.register(r"forum/posts", ForumPostViewSet, basename="forum-post")
router.register(r"forum/comments", ForumCommentViewSet, basename="forum-comment")
router.register(r"communities", CommunityViewSet, basename="community")
router.register(r"partners", PartnerLogoViewSet, basename="partner")
router.register(r"team", TeamMemberViewSet, basename="team")
router.register(r"hero-media", HeroMediaViewSet, basename="hero-media")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"advisory-feedback", AdvisoryFeedbackViewSet, basename="advisory-feedback")
router.register(r"expert-requests", ExpertRequestViewSet, basename="expert-request")
router.register(r"cooperatives", CooperativeViewSet, basename="cooperative")
router.register(r"institutional-partners", InstitutionalPartnerViewSet, basename="institutional-partner")

urlpatterns = [
    path("", include(router.urls)),
    path("advisory/", AdvisoryView.as_view(), name="advisory"),
    path("chat/", ChatView.as_view(), name="chat"),
    path("diagnose/", DiagnoseView.as_view(), name="diagnose"),
    path("newsletter/", NewsletterSubscribeView.as_view(), name="newsletter"),
    path("auth/login/", AdminLoginView.as_view(), name="login"),
    path("auth/csrf/", CsrfCookieView.as_view(), name="csrf"),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("auth/logout/", AdminLogoutView.as_view(), name="logout"),
    path("auth/session/", AdminSessionView.as_view(), name="session"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-email/<str:token>/", VerifyEmailView.as_view(), name="verify-email"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("admin/generate-regions/", GenerateRegionsView.as_view(), name="generate-regions"),
    path("admin/generate-crops/", GenerateCropsView.as_view(), name="generate-crops"),
    path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("admin/users/", UserListView.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", DeleteUserView.as_view(), name="admin-delete-user"),
    path("forum/posts/<int:post_id>/like/", ForumLikeToggleView.as_view(), name="forum-like"),
    path("ndvi/", NdviView.as_view(), name="ndvi"),
    path("institutional-dashboard/", InstitutionalDashboardView.as_view(), name="institutional-dashboard"),
]
