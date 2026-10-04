import os
import requests

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.throttling import ScopedRateThrottle
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.utils.decorators import method_decorator

from .models import (
    Region, Crop, SmsAlert, ChatMessage,
    NewsPost, Event, PageContent, AdvisoryOverride, NewsletterSubscriber, CropDiagnosis,
    FarmerProfile, ForumPost, ForumComment, ForumLike,
    Community, PartnerLogo, TeamMember, HeroMedia, Notification, EmailVerificationToken,
    NdviReading, AdvisoryFeedback, ExpertRequest, Cooperative, InstitutionalPartner,
)
from .serializers import (
    RegionSerializer, CropSerializer, AdvisorySerializer,
    SmsAlertSerializer, ChatMessageSerializer,
    NewsPostSerializer, EventSerializer, PageContentSerializer,
    AdvisoryOverrideSerializer, NewsletterSubscriberSerializer, CropDiagnosisSerializer,
    RegisterSerializer, FarmerProfileSerializer, ForumPostSerializer, ForumCommentSerializer,
    CommunitySerializer, PartnerLogoSerializer, TeamMemberSerializer, HeroMediaSerializer,
    NotificationSerializer, ProfileUpdateSerializer,
    NdviReadingSerializer, AdvisoryFeedbackSerializer, ExpertRequestSerializer,
    CooperativeSerializer, InstitutionalPartnerSerializer,
)
from .services import compute_advice


def _call_claude_json(system_prompt, user_message, api_key, max_tokens=2000):
    """Shared helper: calls Claude, strips markdown fences, parses JSON. Returns None on failure."""
    import json
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": "claude-sonnet-4-6", "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except (requests.RequestException, ValueError, KeyError):
        return None


def _ai_generate_regions(country, api_key):
    system_prompt = (
        "Tu es géographe. On te donne un nom de pays. Réponds UNIQUEMENT avec un tableau JSON "
        "(aucun texte avant ou après, pas de balises markdown) listant les VRAIES divisions administratives "
        "officielles de premier niveau de ce pays (régions, provinces, comtés, États selon le pays) — PAS des "
        "zones climatiques inventées. Inclus-les TOUTES, sans limite arbitraire de nombre (un petit pays peut "
        "en avoir 8, un grand pays peut en avoir 40+ : donne la liste complète et réelle). "
        "Chaque élément doit avoir exactement ces champs : "
        '{"name": string (nom officiel de la division), "admin_center": string (chef-lieu / capitale de cette '
        'division), "zone": string (zone agro-climatique réelle, ex: "Sahélienne", "Soudanienne", "Tropicale humide"), '
        '"soil_type": string, "rain_start_month": int (1-12), "rain_end_month": int (1-12), '
        '"rain_peak_mm": int (pic de pluie mensuel typique en mm), "avg_temp_c": number, '
        '"latitude": number, "longitude": number (coordonnées approximatives du chef-lieu)}. '
        "Utilise des valeurs réalistes basées sur la géographie et le climat réels connus du pays."
    )
    regions = _call_claude_json(system_prompt, f"Pays : {country}", api_key, max_tokens=8000)
    if regions is None:
        return None
    for r in regions:
        r["country"] = country
    return regions


def _ai_generate_crops(country, api_key):
    system_prompt = (
        "Tu es agronome. On te donne un nom de pays. Réponds UNIQUEMENT avec un tableau JSON (aucun texte "
        "avant/après, pas de markdown) listant les cultures vivrières et maraîchères réellement représentatives "
        "de ce pays — céréales, légumineuses ET légumes couramment cultivés, sans limite arbitraire de nombre "
        "(généralement entre 8 et 20 selon la diversité agricole réelle du pays). "
        "Chaque élément doit avoir exactement ces champs : "
        '{"name": string, "sow_window_start_month": int (1-12), "sow_window_end_month": int (1-12), '
        '"cycle_days": int, "water_need": "faible"|"moyen"|"eleve", "min_rain_mm": int, '
        '"grows_rain_season": bool (cultivable en saison des pluies, en pluvial), '
        '"grows_off_season": bool (cultivable en contre-saison sous irrigation), '
        '"yield_range": string (ex: "700-1300 kg/ha, agriculture traditionnelle"), "soil_note": string}. '
        "Utilise des valeurs réalistes basées sur l'agronomie connue du pays."
    )
    crops = _call_claude_json(system_prompt, f"Pays : {country}", api_key, max_tokens=6000)
    if crops is None:
        return None
    for c in crops:
        c["country"] = country
    return crops


class RegionViewSet(viewsets.ModelViewSet):
    """
    Public read access. Creating/editing single regions still requires login (used by
    the admin panel's manual edits) — but any visitor can trigger auto-provisioning of
    a whole new country via the `ensure_country` action below, no admin needed.
    """
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_throttles(self):
        # ensure_country triggers a real (costly) AI call and is open to anyone —
        # give it the strict scope; everything else (list/create/etc.) keeps the
        # default anon/user rates so normal browsing is never rate-limited.
        if getattr(self, "action", None) == "ensure_country":
            self.throttle_scope = "ai_generate"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def ensure_country(self, request):
        """
        POST /api/regions/ensure_country/ {"country": "Sénégal"}

        If regions already exist for this country, returns them as-is. Otherwise asks
        Claude to propose regions AND SAVES THEM IMMEDIATELY — this is the "no admin
        gatekeeping" version of GenerateRegionsView, open to any visitor. Because the
        result is cached (checked first), each country only ever costs one AI call,
        no matter how many users pick it afterwards.
        """
        country = request.data.get("country", "").strip()
        if not country:
            return Response({"detail": "Le champ 'country' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        existing = Region.objects.filter(country=country)
        if existing.exists():
            return Response(RegionSerializer(existing, many=True).data)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return Response({"detail": "ANTHROPIC_API_KEY non configurée côté serveur."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        regions_data = _ai_generate_regions(country, api_key)
        if regions_data is None:
            return Response({"detail": "Échec de la génération IA."}, status=status.HTTP_502_BAD_GATEWAY)

        created = [Region.objects.create(**r) for r in regions_data]
        return Response(RegionSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class CropViewSet(viewsets.ModelViewSet):
    """Includes each crop's cultivation guide stages (soil, sowing, care, harvest, storage)."""
    queryset = Crop.objects.prefetch_related("stages").all()
    serializer_class = CropSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_throttles(self):
        if getattr(self, "action", None) == "ensure_country":
            self.throttle_scope = "ai_generate"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def ensure_country(self, request):
        """Same auto-provisioning pattern as RegionViewSet.ensure_country, for crops."""
        country = request.data.get("country", "").strip()
        if not country:
            return Response({"detail": "Le champ 'country' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        existing = Crop.objects.filter(country=country)
        if existing.exists():
            return Response(CropSerializer(existing, many=True).data)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return Response({"detail": "ANTHROPIC_API_KEY non configurée côté serveur."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        crops_data = _ai_generate_crops(country, api_key)
        if crops_data is None:
            return Response({"detail": "Échec de la génération IA."}, status=status.HTTP_502_BAD_GATEWAY)

        created = [Crop.objects.create(**c) for c in crops_data]
        return Response(CropSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class AdvisoryView(APIView):
    """
    GET /api/advisory/?region=<name>&crop=<name>

    Returns the combined sowing / irrigation / drought-risk advisory for a
    region + crop pair, computed server-side (see services.compute_advice).
    """
    permission_classes = [AllowAny]

    def get(self, request):
        region_name = request.query_params.get("region")
        crop_name = request.query_params.get("crop")
        if not region_name or not crop_name:
            return Response(
                {"detail": "Les paramètres 'region' et 'crop' sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            region = Region.objects.get(name=region_name)
            crop = Crop.objects.get(name=crop_name)
        except (Region.DoesNotExist, Crop.DoesNotExist):
            return Response({"detail": "Région ou culture inconnue."}, status=status.HTTP_404_NOT_FOUND)

        advisory = compute_advice(region, crop)

        # A manually-set advisory (admin panel, optionally AI-assisted) overrides
        # individual fields of the rule-based computation, field by field.
        override = AdvisoryOverride.objects.filter(region=region, crop=crop).first()
        if override:
            if override.sowing_advice:
                advisory.sowing_advice = override.sowing_advice
            if override.irrigation_advice:
                advisory.irrigation_advice = override.irrigation_advice
            if override.risk_advice:
                advisory.risk_advice = override.risk_advice

        serializer = AdvisorySerializer(advisory.__dict__)
        return Response(serializer.data)


class SmsAlertViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for SMS/WhatsApp alerts. If `channel="whatsapp"` and the recipient
    has a phone number, this actually calls the WhatsApp gateway (see
    whatsapp_provider.py) — which requires real Meta/Twilio credentials to
    succeed; without them the alert is correctly marked "failed" with the
    reason recorded, never silently faked as sent. SMS/USSD channel stays
    simulated, as before, since no SMS gateway credentials are configured either.
    """
    queryset = SmsAlert.objects.select_related("region", "crop", "recipient").all()
    serializer_class = SmsAlertSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        alert = serializer.save(status="queued")

        if alert.channel == "whatsapp":
            from .whatsapp_provider import send_whatsapp, WhatsAppError
            phone = alert.recipient.farmer_profile.phone if alert.recipient and hasattr(alert.recipient, "farmer_profile") else ""
            if not phone:
                alert.status = "failed"
                alert.error_detail = "Aucun numéro de téléphone renseigné pour ce destinataire."
            else:
                try:
                    send_whatsapp(phone, alert.message)
                    alert.status = "sent"
                except WhatsAppError as exc:
                    alert.status = "failed"
                    alert.error_detail = str(exc)
        else:
            # SMS/USSD: simulated, same as before (no gateway configured).
            alert.status = "sent"

        alert.save(update_fields=["status", "error_detail"])


class ChatView(APIView):
    """
    POST /api/chat/
    Body: {"session_id": "...", "message": "...", "region": "...", "crop": "..."}

    Server-side proxy to the Anthropic API so the API key never reaches the
    browser. Logs both the farmer's message and the assistant's reply to
    ChatMessage for audit/analytics.
    """
    permission_classes = [AllowAny]
    throttle_scope = "ai_chat"

    def post(self, request):
        session_id = request.data.get("session_id", "anonymous")
        message = request.data.get("message", "").strip()
        region_name = request.data.get("region")
        crop_name = request.data.get("crop")

        if not message:
            return Response({"detail": "Le champ 'message' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        region = Region.objects.filter(name=region_name).first()
        crop = Crop.objects.filter(name=crop_name).first()

        ChatMessage.objects.create(
            session_id=session_id, role="user", content=message, region=region, crop=crop,
        )

        system_prompt = (
            "Tu es l'assistant IA de Mogota Agri-Tech Innovation, un conseiller agricole pour des "
            "agriculteurs tchadiens. Réponds toujours en français, de façon claire, concise "
            "(5-8 phrases maximum) et pratique, adaptée à un agriculteur sans formation technique."
        )
        if region and crop:
            advisory = compute_advice(region, crop)
            system_prompt += (
                f"\nContexte actuel : région {region.name} ({region.zone}), culture {crop.name}."
                f" Conseil de semis du jour : {advisory.sowing_advice}"
                f" Conseil d'irrigation du jour : {advisory.irrigation_advice}"
            )

        history = list(
            ChatMessage.objects.filter(session_id=session_id).order_by("created_at").values("role", "content")
        )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return Response(
                {"detail": "ANTHROPIC_API_KEY n'est pas configurée côté serveur."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1000,
                    "system": system_prompt,
                    "messages": history,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            reply_text = "\n".join(
                block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
            ).strip() or "Désolé, je n'ai pas pu générer de réponse."
        except requests.RequestException:
            return Response(
                {"detail": "Impossible de contacter l'assistant IA pour le moment."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        ChatMessage.objects.create(
            session_id=session_id, role="assistant", content=reply_text, region=region, crop=crop,
        )

        return Response({"reply": reply_text})


# ==============================================================================
# ADMIN AUTH — simple Django session login, used to gate the admin panel.
# ==============================================================================
@method_decorator(csrf_protect, name="post")
class AdminLoginView(APIView):
    """POST {"username": "...", "password": "..."} -> logs in via Django session auth.
    Any valid account can log in (accounts are mandatory to use the public platform);
    admin-only screens separately check `is_staff` on the session."""
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Identifiants invalides."}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        profile = getattr(user, "farmer_profile", None)
        return Response({
            "detail": "Connecté.", "id": user.id, "username": user.username, "is_staff": user.is_staff,
            "country": profile.country if profile else None,
            "region": profile.region_id if profile else None,
            "phone": profile.phone if profile else "",
        })


@method_decorator(csrf_protect, name="post")
@method_decorator(csrf_protect, name="post")
class RegisterView(APIView):
    """POST {"username","password","email","country","region","phone"} -> creates the
    account + farmer profile and logs the user in immediately. Account creation is
    mandatory to use the public platform."""
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        login(request, user)
        _send_verification_email(user, request)
        return Response({
            "detail": "Compte créé. Un email de vérification a été envoyé.", "username": user.username, "is_staff": False,
            "country": user.farmer_profile.country, "region": user.farmer_profile.region_id,
        }, status=status.HTTP_201_CREATED)


class AdminLogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"detail": "Déconnecté."})


class AdminSessionView(APIView):
    """GET -> tells the frontend whether the current session is an authenticated admin."""
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, "farmer_profile", None)
            return Response({
                "authenticated": True, "id": request.user.id, "username": request.user.username, "is_staff": request.user.is_staff,
                "country": profile.country if profile else None,
                "region": profile.region_id if profile else None,
                "phone": profile.phone if profile else "",
            })
        return Response({"authenticated": False})


# ==============================================================================
# CONTENT MANAGEMENT — news, events, editable page blocks, advisory overrides
# ==============================================================================
class NewsPostViewSet(viewsets.ModelViewSet):
    queryset = NewsPost.objects.filter(is_published=True)
    serializer_class = NewsPostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PageContentViewSet(viewsets.ModelViewSet):
    queryset = PageContent.objects.all()
    serializer_class = PageContentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "key"


class AdvisoryOverrideViewSet(viewsets.ModelViewSet):
    queryset = AdvisoryOverride.objects.select_related("region", "crop").all()
    serializer_class = AdvisoryOverrideSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class NewsletterSubscribeView(APIView):
    """POST {"email": "..."} -> adds an address to the newsletter list. Open to everyone."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = NewsletterSubscriberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Treat "already subscribed" as a friendly success rather than an error.
        if "email" in serializer.errors:
            return Response({"detail": "Déjà inscrit."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# AI-ASSISTED REGION GENERATION
# Given a country name, asks Claude to propose a starter set of agro-climatic
# regions (zone, soil, rainy season, typical rainfall/temperature, approximate
# coordinates). Returns a PROPOSAL only — nothing is saved until the admin
# reviews it and posts the confirmed regions to /api/regions/.
# ==============================================================================
class GenerateRegionsView(APIView):
    """Any authenticated user can trigger this — not just admins — since country
    coverage should be self-serve and worldwide. Each country is only generated
    once; results are meant to be saved and reused, not regenerated per request.
    (This admin-panel version returns a proposal for review; RegionViewSet.ensure_country
    is the public, auto-save version used transparently when a user picks a new country.)"""
    permission_classes = [IsAuthenticated]
    throttle_scope = "ai_generate"

    def post(self, request):
        country = request.data.get("country", "").strip()
        if not country:
            return Response({"detail": "Le champ 'country' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return Response(
                {"detail": "ANTHROPIC_API_KEY n'est pas configurée côté serveur."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        regions = _ai_generate_regions(country, api_key)
        if regions is None:
            return Response({"detail": "Échec de la génération IA, réessayez."}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"country": country, "regions": regions})


# ==============================================================================
# PHOTO DIAGNOSIS — proxies an image to Claude's vision capability server-side
# (keeps ANTHROPIC_API_KEY off the client) and logs the result.
# ==============================================================================
class DiagnoseView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "ai_diagnose"

    def post(self, request):
        image_b64 = request.data.get("image")
        media_type = request.data.get("media_type", "image/jpeg")
        region_name = request.data.get("region")
        crop_name = request.data.get("crop")

        if not image_b64:
            return Response({"detail": "Le champ 'image' (base64) est requis."}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return Response(
                {"detail": "ANTHROPIC_API_KEY n'est pas configurée côté serveur."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        region = Region.objects.filter(name=region_name).first()
        crop = Crop.objects.filter(name=crop_name).first()

        system_prompt = (
            "Tu es phytopathologiste, spécialiste des cultures vivrières sahéliennes (sorgho, mil, arachide, maïs). "
            f"On te montre une photo prise par un agriculteur au Tchad (culture : {crop_name}, région : {region_name}). "
            "Réponds en français, en 4 parties courtes séparées par des titres en MAJUSCULES : "
            "OBSERVATION, DIAGNOSTIC PROBABLE (avec un niveau de confiance faible/moyen/élevé), "
            "RECOMMANDATION, LIMITE (rappelle que ce diagnostic est indicatif)."
        )

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 800,
                    "system": system_prompt,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                            {"type": "text", "text": "Merci d'analyser cette photo de culture."},
                        ],
                    }],
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            diagnosis_text = "\n".join(
                block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
            ).strip()
        except requests.RequestException:
            return Response({"detail": "Impossible de contacter l'assistant IA."}, status=status.HTTP_502_BAD_GATEWAY)

        CropDiagnosis.objects.create(region=region, crop=crop, diagnosis_text=diagnosis_text)
        return Response({"diagnosis": diagnosis_text})


# ==============================================================================
# ADMIN DASHBOARD — usage statistics (subscribers, accounts, activity)
# ==============================================================================
class AdminStatsView(APIView):
    """
    GET /api/admin/stats/ — staff only.

    'connected_sessions' counts non-expired Django sessions as a proxy for
    "currently logged in" — it is not a real-time presence count (a session
    stays valid between visits), but it is the honest, low-effort signal
    available without adding websockets/heartbeats.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)

        from django.contrib.auth.models import User
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        from django.db.models import Count

        by_country = list(
            FarmerProfile.objects.values("country").annotate(count=Count("id")).order_by("-count")
        )

        return Response({
            "total_accounts": User.objects.count(),
            "total_farmers": FarmerProfile.objects.count(),
            "farmers_by_country": by_country,
            "newsletter_subscribers": NewsletterSubscriber.objects.count(),
            "connected_sessions": Session.objects.filter(expire_date__gte=timezone.now()).count(),
            "diagnoses_run": CropDiagnosis.objects.count(),
            "chat_sessions": ChatMessage.objects.values("session_id").distinct().count(),
            "forum_posts": ForumPost.objects.count(),
            "forum_comments": ForumComment.objects.count(),
            "sms_alerts_sent": SmsAlert.objects.filter(status="sent").count(),
        })


# ==============================================================================
# FORUM — post problems, comment, like. Reading is open; posting/commenting/
# liking requires an account (accounts are mandatory to use the platform,
# enforced by the frontend login wall; the API itself keeps read access open
# so e.g. an embedded preview can still show forum content).
# ==============================================================================
class ForumPostViewSet(viewsets.ModelViewSet):
    queryset = ForumPost.objects.select_related("author", "region", "crop").prefetch_related("comments", "likes")
    serializer_class = ForumPostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_serializer_context(self):
        return {"request": self.request}


class ForumCommentViewSet(viewsets.ModelViewSet):
    serializer_class = ForumCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = ForumComment.objects.select_related("author")
        post_id = self.request.query_params.get("post")
        if post_id:
            qs = qs.filter(post_id=post_id)
        return qs

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        post = comment.post
        if post.author_id != self.request.user.id:
            Notification.objects.create(
                user=post.author,
                message=f"{self.request.user.username} a répondu à votre publication « {post.title} »",
                link=f"/forum/posts/{post.id}",
            )


class ForumLikeToggleView(APIView):
    """POST /api/forum/posts/<id>/like/ — toggles the current user's like on a post."""
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = ForumPost.objects.filter(id=post_id).first()
        if not post:
            return Response({"detail": "Publication introuvable."}, status=status.HTTP_404_NOT_FOUND)
        like, created = ForumLike.objects.get_or_create(post=post, user=request.user)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
            if post.author_id != request.user.id:
                Notification.objects.create(
                    user=post.author,
                    message=f"{request.user.username} a aimé votre publication « {post.title} »",
                    link=f"/forum/posts/{post.id}",
                )
        return Response({"liked": liked, "likes_count": post.likes.count()})


# ==============================================================================
# AI-ASSISTED CROP GENERATION (per country) — mirrors GenerateRegionsView.
# ==============================================================================
class GenerateCropsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "ai_generate"

    def post(self, request):
        country = request.data.get("country", "").strip()
        if not country:
            return Response({"detail": "Le champ 'country' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return Response(
                {"detail": "ANTHROPIC_API_KEY n'est pas configurée côté serveur."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        crops = _ai_generate_crops(country, api_key)
        if crops is None:
            return Response({"detail": "Échec de la génération IA, réessayez."}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"country": country, "crops": crops})


# ==============================================================================
# EMAIL VERIFICATION
# Uses Django's email backend — configured to print to the console by default
# (see settings.EMAIL_BACKEND) so registration works out of the box in dev.
# For real delivery, set EMAIL_BACKEND to smtp and configure real credentials
# (Gmail, SendGrid, etc.) in .env — see the backend README.
# ==============================================================================
def _send_verification_email(user, request):
    import secrets
    from django.core.mail import send_mail
    from .models import EmailVerificationToken

    token = secrets.token_urlsafe(32)
    EmailVerificationToken.objects.update_or_create(user=user, defaults={"token": token, "verified": False})
    verify_url = f"{request.scheme}://{request.get_host()}/api/auth/verify-email/{token}/"
    send_mail(
        subject="Vérifiez votre compte Mogota Agri-Tech",
        message=(
            f"Bonjour {user.username},\n\n"
            f"Merci de vous être inscrit sur la plateforme Mogota Agri-Tech Innovation.\n"
            f"Confirmez votre adresse email en ouvrant ce lien :\n{verify_url}\n\n"
            f"Si vous n'êtes pas à l'origine de cette inscription, ignorez ce message."
        ),
        from_email=None,
        recipient_list=[user.email] if user.email else [],
        fail_silently=True,
    )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        from .models import EmailVerificationToken
        entry = EmailVerificationToken.objects.filter(token=token).first()
        if not entry:
            return Response({"detail": "Lien de vérification invalide."}, status=status.HTTP_404_NOT_FOUND)
        entry.verified = True
        entry.save(update_fields=["verified"])
        return Response({"detail": "Email vérifié — vous pouvez fermer cette page et vous connecter."})


# ==============================================================================
# USER PROFILE — edit own info, delete own account, logout is already covered
# by AdminLogoutView above (works for any account, not just admin).
# ==============================================================================
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "farmer_profile", None)
        if not profile:
            return Response({"detail": "Profil introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "username": request.user.username, "email": request.user.email,
            "mogota_id": profile.mogota_id, **FarmerProfileSerializer(profile).data,
        })

    def patch(self, request):
        profile = getattr(request.user, "farmer_profile", None)
        if not profile:
            return Response({"detail": "Profil introuvable."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        for field, value in serializer.validated_data.items():
            if field == "email":
                request.user.email = value
                request.user.save(update_fields=["email"])
            else:
                setattr(profile, field, value)
        profile.save()
        return Response({"detail": "Profil mis à jour."})

    def delete(self, request):
        """A user can delete their own account — separate from the admin-only
        DeleteUserView below, which lets an admin remove any account."""
        request.user.delete()
        return Response({"detail": "Compte supprimé."})


class DeleteUserView(APIView):
    """DELETE /api/admin/users/<id>/ — staff only, removes any user account."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        if not request.user.is_staff:
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        from django.contrib.auth.models import User
        target = User.objects.filter(id=user_id).first()
        if not target:
            return Response({"detail": "Compte introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if target.is_staff:
            return Response({"detail": "Impossible de supprimer un compte administrateur depuis cette action."}, status=status.HTTP_400_BAD_REQUEST)
        target.delete()
        return Response({"detail": "Compte supprimé."})


class UserListView(APIView):
    """GET /api/admin/users/ — staff only, lists accounts for the admin dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        from django.contrib.auth.models import User
        users = User.objects.select_related("farmer_profile").order_by("-date_joined")
        return Response([
            {
                "id": u.id, "username": u.username, "email": u.email, "is_staff": u.is_staff,
                "date_joined": u.date_joined, "last_login": u.last_login,
                "country": getattr(u, "farmer_profile", None).country if hasattr(u, "farmer_profile") else None,
                "mogota_id": getattr(u, "farmer_profile", None).mogota_id if hasattr(u, "farmer_profile") else None,
            }
            for u in users
        ])


# ==============================================================================
# COMMUNITIES — multiple forum sub-communities, users join/leave; member counts
# are public.
# ==============================================================================
class CommunityViewSet(viewsets.ModelViewSet):
    queryset = Community.objects.all()
    serializer_class = CommunitySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_context(self):
        return {"request": self.request}

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        community = self.get_object()
        community.members.add(request.user)
        return Response({"joined": True, "members_count": community.members.count()})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        community = self.get_object()
        community.members.remove(request.user)
        return Response({"joined": False, "members_count": community.members.count()})


# ==============================================================================
# HOMEPAGE CONTENT — partner logos, team members, hero media. Admin-only writes.
# ==============================================================================
class PartnerLogoViewSet(viewsets.ModelViewSet):
    queryset = PartnerLogo.objects.all()
    serializer_class = PartnerLogoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class TeamMemberViewSet(viewsets.ModelViewSet):
    queryset = TeamMember.objects.all()
    serializer_class = TeamMemberSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class HeroMediaViewSet(viewsets.ModelViewSet):
    queryset = HeroMedia.objects.all()
    serializer_class = HeroMediaSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


# ==============================================================================
# NOTIFICATIONS
# ==============================================================================
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "Notifications marquées comme lues."})


# ==============================================================================
# NDVI — satellite vegetation health, via ndvi_provider.py (ORNL/MODIS, keyless).
# ==============================================================================
class NdviView(APIView):
    """
    GET /api/ndvi/?region=<name> — returns the latest cached NDVI reading for a
    region if one exists, or fetches a fresh one from ORNL/MODIS on the fly.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from .ndvi_provider import sync_region_ndvi, ndvi_health_label, NdviProviderError

        region_name = request.query_params.get("region")
        region = Region.objects.filter(name=region_name).first()
        if not region:
            return Response({"detail": "Région introuvable."}, status=status.HTTP_404_NOT_FOUND)

        latest = region.ndvi_readings.first()
        # Refresh if we have nothing yet, or the cached reading is older than ~16 days
        # (MODIS MOD13Q1's own composite period, so more frequent polling wouldn't help).
        import datetime
        from django.utils import timezone
        needs_refresh = not latest or (timezone.now().date() - latest.date) > datetime.timedelta(days=16)

        if needs_refresh:
            try:
                latest = sync_region_ndvi(region)
            except NdviProviderError as exc:
                if latest:
                    # Serve the stale cached value rather than failing outright.
                    pass
                else:
                    return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "region": region.name, "date": latest.date, "ndvi_value": latest.ndvi_value,
            "health_label": ndvi_health_label(latest.ndvi_value),
        })


# ==============================================================================
# ADVISORY FEEDBACK — "j'ai suivi ce conseil" + résultat. The field-truth loop.
# ==============================================================================
class AdvisoryFeedbackViewSet(viewsets.ModelViewSet):
    queryset = AdvisoryFeedback.objects.select_related("user", "region", "crop").all()
    serializer_class = AdvisoryFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        # `approved` is writable in the serializer (see the Meta note above) so an
        # admin can set it via PATCH — but that means a plain create() must not
        # trust client-supplied `approved` either, or any user could self-approve.
        # Force it False here regardless of what was submitted.
        serializer.save(user=self.request.user, approved=False)


# ==============================================================================
# EXPERT ESCALATION — shown when an AI diagnosis has low confidence.
# ==============================================================================
class ExpertRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ExpertRequestSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = ExpertRequest.objects.select_related("user", "region", "crop").all()
        if not (self.request.user.is_authenticated and self.request.user.is_staff):
            # Non-staff users can only see their own requests (or none, if anonymous).
            if self.request.user.is_authenticated:
                return qs.filter(user=self.request.user)
            return ExpertRequest.objects.none()
        return qs

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)


# ==============================================================================
# COOPERATIVES — a manager creates a cooperative, farmers join it via their
# profile, the manager sees aggregated (not individual) stats for the group.
# ==============================================================================
class CooperativeViewSet(viewsets.ModelViewSet):
    queryset = Cooperative.objects.select_related("region", "manager").all()
    serializer_class = CooperativeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(manager=self.request.user)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def stats(self, request, pk=None):
        """
        GET /api/cooperatives/<id>/stats/ — manager only. Aggregated numbers for
        the group's members: how many, which crops/regions they farm, and how
        their advice-feedback outcomes break down. No individual member identity
        or per-user data is exposed here — see AdminStats/UserListView for that,
        which stay staff-only.
        """
        coop = self.get_object()
        if coop.manager_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Réservé au responsable de cette coopérative."}, status=status.HTTP_403_FORBIDDEN)

        from django.db.models import Count
        members = coop.members.all()
        member_users = [m.user_id for m in members]

        crop_breakdown = list(
            AdvisoryFeedback.objects.filter(user_id__in=member_users)
            .values("crop__name").annotate(count=Count("id")).order_by("-count")
        )
        outcome_breakdown = list(
            AdvisoryFeedback.objects.filter(user_id__in=member_users)
            .values("outcome").annotate(count=Count("id")).order_by("-count")
        )

        return Response({
            "cooperative": coop.name,
            "members_count": members.count(),
            "crop_breakdown": crop_breakdown,
            "outcome_breakdown": outcome_breakdown,
            "feedback_submitted": AdvisoryFeedback.objects.filter(user_id__in=member_users).count(),
        })


# ==============================================================================
# INSTITUTIONAL DASHBOARD — aggregated, anonymized, cross-region view for NGOs /
# ministries / funders. Requires an approved InstitutionalPartner flag — set by
# an admin, not self-service (see InstitutionalPartnerViewSet below for the
# request flow).
# ==============================================================================
class InstitutionalPartnerViewSet(viewsets.ModelViewSet):
    """
    A user requests partner status by creating one of these (approved=False by
    default); an admin approves it via PATCH. Only staff can list all requests;
    a regular user can only see/create their own.
    """
    serializer_class = InstitutionalPartnerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return InstitutionalPartner.objects.select_related("user").all()
        return InstitutionalPartner.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Force approved=False regardless of what the client sends — otherwise a
        # regular user could self-approve by including "approved": true in the
        # creation payload, since the field is writable (needed for the admin's
        # later PATCH). Only perform_update, gated on is_staff below, may set it.
        serializer.save(user=self.request.user, approved=False)

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Seul un administrateur peut approuver une demande de partenaire.")
        serializer.save()


class InstitutionalDashboardView(APIView):
    """
    GET /api/institutional-dashboard/ — requires an approved InstitutionalPartner
    record. Returns counts and breakdowns by region/country only — no usernames,
    no individual farmer data, ever.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            pass  # staff can always preview this view
        else:
            partner = InstitutionalPartner.objects.filter(user=request.user, approved=True).first()
            if not partner:
                return Response(
                    {"detail": "Accès partenaire non approuvé. Créez une demande via /api/institutional-partners/ et attendez la validation d'un administrateur."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        from django.db.models import Count, Avg

        farmers_by_region = list(
            FarmerProfile.objects.exclude(region__isnull=True)
            .values("region__name", "region__country")
            .annotate(count=Count("id")).order_by("-count")
        )
        feedback_by_region = list(
            AdvisoryFeedback.objects.values("region__name")
            .annotate(count=Count("id"), followed_rate=Avg("followed_advice"))
            .order_by("-count")
        )
        diagnoses_by_region = list(
            CropDiagnosis.objects.exclude(region__isnull=True)
            .values("region__name").annotate(count=Count("id")).order_by("-count")
        )

        return Response({
            "total_farmers": FarmerProfile.objects.count(),
            "farmers_by_region": farmers_by_region,
            "advice_feedback_by_region": feedback_by_region,
            "diagnoses_by_region": diagnoses_by_region,
            "open_expert_requests": ExpertRequest.objects.filter(status="pending").count(),
            "cooperatives_count": Cooperative.objects.count(),
        })


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfCookieView(APIView):
    """
    GET /api/auth/csrf/ — sets the csrftoken cookie. The frontend calls this once
    on load, then reads the cookie and sends it back as X-CSRFToken on every
    POST/PUT/PATCH/DELETE — Django's standard CSRF flow, replacing the dev-only
    CsrfExemptSessionAuthentication shortcut used earlier in this project.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Cookie CSRF posé."})


class HealthCheckView(APIView):
    """
    GET /api/health/ — used to verify a deployment actually worked (Module 9),
    and can be pointed at by Render's health check setting so a bad deploy is
    caught automatically instead of silently serving broken requests.
    Checks the database connection, not just that the process is running —
    a server that boots but can't reach Postgres should NOT read as healthy.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import connection
        db_ok = True
        db_detail = "ok"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:
            db_ok = False
            db_detail = str(exc)

        payload = {"status": "ok" if db_ok else "degraded", "database": db_detail}
        return Response(payload, status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE)
