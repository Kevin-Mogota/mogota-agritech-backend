from rest_framework import serializers
from .models import (
    Region, Crop, CultivationStage, SmsAlert, ChatMessage,
    NewsPost, Event, PageContent, AdvisoryOverride, NewsletterSubscriber, CropDiagnosis,
    FarmerProfile, ForumPost, ForumComment, ForumLike,
    Community, PartnerLogo, TeamMember, HeroMedia, Notification,
    NdviReading, AdvisoryFeedback, ExpertRequest, Cooperative, InstitutionalPartner,
)
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = "__all__"


class CultivationStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CultivationStage
        fields = ["order", "title", "timing_label", "icon", "actions"]


class CropSerializer(serializers.ModelSerializer):
    stages = CultivationStageSerializer(many=True, read_only=True)

    class Meta:
        model = Crop
        fields = "__all__"


class AdvisorySerializer(serializers.Serializer):
    """Read-only representation of a computed Advisory (services.Advisory dataclass)."""
    sowing_advice = serializers.CharField()
    sowing_level = serializers.CharField()
    irrigation_advice = serializers.CharField()
    irrigation_level = serializers.CharField()
    risk_advice = serializers.CharField()
    risk_level = serializers.CharField()
    drought_index = serializers.CharField()
    this_month_rain_mm = serializers.IntegerField()
    total_season_rain_mm = serializers.IntegerField()
    rain_ratio = serializers.FloatField()
    rain_series = serializers.ListField()


class SmsAlertSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)
    crop_name = serializers.CharField(source="crop.name", read_only=True)

    class Meta:
        model = SmsAlert
        fields = ["id", "region", "region_name", "crop", "crop_name", "recipient", "channel", "message", "status", "error_detail", "created_at", "sent_at"]
        read_only_fields = ["status", "error_detail", "created_at", "sent_at"]


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "session_id", "role", "content", "region", "crop", "created_at"]
        read_only_fields = ["created_at"]


class NewsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsPost
        fields = "__all__"
        read_only_fields = ["published_at"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"
        read_only_fields = ["created_at"]


class PageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageContent
        fields = "__all__"
        read_only_fields = ["updated_at"]


class AdvisoryOverrideSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)
    crop_name = serializers.CharField(source="crop.name", read_only=True)

    class Meta:
        model = AdvisoryOverride
        fields = ["id", "region", "region_name", "crop", "crop_name", "sowing_advice", "irrigation_advice", "risk_advice", "updated_at"]
        read_only_fields = ["updated_at"]


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ["id", "email", "subscribed_at"]
        read_only_fields = ["subscribed_at"]


class CropDiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropDiagnosis
        fields = ["id", "region", "crop", "diagnosis_text", "created_at"]
        read_only_fields = ["created_at"]


class FarmerProfileSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)

    class Meta:
        model = FarmerProfile
        fields = ["country", "region", "region_name", "phone", "created_at"]
        read_only_fields = ["created_at"]


class RegisterSerializer(serializers.Serializer):
    """Creates a Django User + FarmerProfile in one call. Account creation is mandatory
    to use the public platform, per the product requirement."""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)
    country = serializers.CharField(max_length=100)
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(choices=["fr", "en"], required=False, default="fr")

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        FarmerProfile.objects.create(
            user=user,
            country=validated_data["country"],
            region=validated_data.get("region"),
            phone=validated_data.get("phone", ""),
            preferred_language=validated_data.get("preferred_language", "fr"),
        )
        return user


class ForumCommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = ForumComment
        fields = ["id", "post", "author", "author_username", "content", "created_at"]
        read_only_fields = ["author", "created_at"]


class ForumPostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True, default=None)
    crop_name = serializers.CharField(source="crop.name", read_only=True, default=None)
    community_name = serializers.CharField(source="community.name", read_only=True, default=None)
    comments_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = ForumPost
        fields = [
            "id", "author", "author_username", "community", "community_name", "title", "content",
            "image_url", "video_url", "region", "region_name",
            "crop", "crop_name", "created_at", "comments_count", "likes_count", "liked_by_me",
        ]
        read_only_fields = ["author", "created_at"]

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked_by_me(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.likes.filter(user=request.user).exists()


class CommunitySerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    joined_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = ["id", "slug", "name", "icon", "description", "members_count", "joined_by_me"]

    def get_members_count(self, obj):
        return obj.members.count()

    def get_joined_by_me(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.members.filter(id=request.user.id).exists()


class PartnerLogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerLogo
        fields = "__all__"


class TeamMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = "__all__"


class HeroMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroMedia
        fields = "__all__"


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "link", "is_read", "created_at"]
        read_only_fields = ["created_at"]


class ProfileUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    country = serializers.CharField(max_length=100, required=False)
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    sms_opt_in = serializers.BooleanField(required=False)
    preferred_language = serializers.ChoiceField(choices=["fr", "en"], required=False)


class NdviReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NdviReading
        fields = ["region", "date", "ndvi_value", "source"]


class AdvisoryFeedbackSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AdvisoryFeedback
        fields = ["id", "user", "username", "region", "crop", "followed_advice", "outcome", "comment", "created_at"]
        read_only_fields = ["user", "created_at"]


class ExpertRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertRequest
        fields = ["id", "user", "phone", "region", "crop", "context", "status", "created_at"]
        read_only_fields = ["user", "created_at"]


class CooperativeSerializer(serializers.ModelSerializer):
    manager_username = serializers.CharField(source="manager.username", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True, default=None)
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Cooperative
        fields = ["id", "name", "region", "region_name", "manager", "manager_username", "members_count", "created_at"]
        read_only_fields = ["manager", "created_at"]

    def get_members_count(self, obj):
        return obj.members.count()


class InstitutionalPartnerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = InstitutionalPartner
        fields = ["id", "user", "username", "organization_name", "approved", "created_at"]
        read_only_fields = ["user", "created_at"]
        # NOTE: "approved" is deliberately writable here — the actual admin-only gate
        # is enforced in InstitutionalPartnerViewSet.perform_update (checks is_staff),
        # not by making the field read-only, since it must be settable by someone.
