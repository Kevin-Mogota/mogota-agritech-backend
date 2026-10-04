from django.db import models


class Region(models.Model):
    """A region/province with a climate profile used to compute advisories.
    Uses real administrative divisions (e.g. Chad's 23 provinces), not invented climate zones."""
    name = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=100, default="Tchad")
    admin_center = models.CharField(max_length=100, blank=True, help_text="Chef-lieu / capitale administrative de la région")
    zone = models.CharField(max_length=100, help_text="Ex: Sahélienne, Soudanienne")
    soil_type = models.CharField(max_length=100)
    rain_start_month = models.PositiveSmallIntegerField(help_text="1-12")
    rain_end_month = models.PositiveSmallIntegerField(help_text="1-12")
    rain_peak_mm = models.PositiveIntegerField(help_text="Pic de pluie mensuel typique, en mm")
    avg_temp_c = models.FloatField(default=32)
    latitude = models.FloatField(null=True, blank=True, help_text="Requis pour brancher une vraie source météo (NASA POWER)")
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name


class Crop(models.Model):
    """A crop with its sowing window and water needs, used to compute advisories."""
    WATER_NEED_CHOICES = [("faible", "Faible"), ("moyen", "Moyen"), ("eleve", "Élevé")]

    name = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=100, default="Tchad")
    sow_window_start_month = models.PositiveSmallIntegerField()
    sow_window_end_month = models.PositiveSmallIntegerField()
    cycle_days = models.PositiveIntegerField()
    water_need = models.CharField(max_length=10, choices=WATER_NEED_CHOICES, default="moyen")
    min_rain_mm = models.PositiveIntegerField(help_text="Cumul de pluie saisonnier minimal requis")
    grows_rain_season = models.BooleanField(default=True, help_text="Cultivable en saison des pluies (pluvial)")
    grows_off_season = models.BooleanField(default=False, help_text="Cultivable en contre-saison, sous irrigation")
    yield_range = models.CharField(max_length=150, blank=True, help_text="Ex: 700-1300 kg/ha")
    soil_note = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CultivationStage(models.Model):
    """One step of the cultivation guide for a crop (before/after harvest practices)."""
    STAGE_ICONS = [
        ("soil", "Préparation du sol"),
        ("seed", "Semis"),
        ("care", "Entretien"),
        ("harvest", "Récolte"),
        ("storage", "Après récolte / stockage"),
    ]

    crop = models.ForeignKey(Crop, related_name="stages", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=100)
    timing_label = models.CharField(max_length=100, help_text="Ex: J-30 à J-7")
    icon = models.CharField(max_length=20, choices=STAGE_ICONS)
    actions = models.JSONField(default=list, help_text="Liste de recommandations pour cette étape")

    class Meta:
        ordering = ["crop", "order"]

    def __str__(self):
        return f"{self.crop.name} — {self.title}"


class WeatherReading(models.Model):
    """A weather data point for a region, meant to be populated from a real weather API."""
    region = models.ForeignKey(Region, related_name="weather_readings", on_delete=models.CASCADE)
    date = models.DateField()
    rainfall_mm = models.FloatField(default=0)
    temperature_c = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=100, default="simulated", help_text="Ex: NASA POWER, station locale, simulated")

    class Meta:
        ordering = ["-date"]
        unique_together = ("region", "date", "source")

    def __str__(self):
        return f"{self.region.name} — {self.date} ({self.rainfall_mm} mm)"


class SmsAlert(models.Model):
    """A (simulated or real) SMS/USSD/WhatsApp advisory sent to farmers for a region/crop."""
    STATUS_CHOICES = [("queued", "En file"), ("sent", "Envoyé"), ("failed", "Échec")]
    CHANNEL_CHOICES = [("sms", "SMS/USSD"), ("whatsapp", "WhatsApp")]

    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE)
    recipient = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="sms")
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="queued")
    error_detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_channel_display()} {self.region.name}/{self.crop.name} — {self.status}"


class ChatMessage(models.Model):
    """One turn of a conversation with the AI advisory assistant, for logging/audit."""
    ROLE_CHOICES = [("user", "Agriculteur"), ("assistant", "Assistant")]

    session_id = models.CharField(max_length=100, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.session_id}] {self.role}: {self.content[:40]}"


class NewsPost(models.Model):
    """An 'Actualité' shown on the public homepage, managed from the admin panel."""
    title = models.CharField(max_length=200)
    content = models.TextField()
    image_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title


class Event(models.Model):
    """An 'Événement' shown on the public homepage, managed from the admin panel."""
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    event_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_date"]

    def __str__(self):
        return self.title


class PageContent(models.Model):
    """Simple key/value CMS for editable static blocks (about us, mission…)."""
    key = models.SlugField(max_length=50, unique=True, help_text="Ex: about, mission")
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


class AdvisoryOverride(models.Model):
    """
    A manually-written advisory for a region/crop pair, set from the admin
    panel (optionally AI-assisted). When present, this takes priority over
    the rule-based computation in services.compute_advice.
    """
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE)
    sowing_advice = models.TextField(blank=True)
    irrigation_advice = models.TextField(blank=True)
    risk_advice = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ("region", "crop")

    def __str__(self):
        return f"Conseil personnalisé — {self.region.name} / {self.crop.name}"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class CropDiagnosis(models.Model):
    """
    Log of an AI photo diagnosis request. The image itself is not stored
    (kept out of the database to avoid bloat) — only the textual result,
    for audit/analytics and to eventually build a training dataset of
    confirmed vs incorrect diagnoses if farmers report back.
    """
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.SET_NULL)
    diagnosis_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Diagnostic {self.region}/{self.crop} — {self.created_at:%Y-%m-%d}"


class FarmerProfile(models.Model):
    """
    Every platform user (account creation is mandatory) has one of these,
    holding the country/region they farm in — this is what the app's
    country → region → crop selection reads on login instead of a fixed dropdown.

    `mogota_id` is a stable public identifier, deliberately kept even though
    this prototype only has one account type — it's the join point for the
    future single-account / professional-spaces architecture, so migrating
    later doesn't require renumbering users.
    """
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="farmer_profile")
    mogota_id = models.CharField(max_length=20, unique=True, blank=True)
    country = models.CharField(max_length=100)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    cooperative = models.ForeignKey("Cooperative", null=True, blank=True, related_name="members", on_delete=models.SET_NULL)
    phone = models.CharField(max_length=30, blank=True)
    sms_opt_in = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=5, default="fr", choices=[("fr", "Français"), ("en", "English")])
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.mogota_id:
            import uuid
            self.mogota_id = "MATI-" + uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} — {self.country}"


class ForumPost(models.Model):
    """A farmer's question/problem posted to the community forum."""
    author = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="forum_posts")
    community = models.ForeignKey("Community", null=True, blank=True, related_name="posts", on_delete=models.SET_NULL)
    title = models.CharField(max_length=200)
    content = models.TextField()
    image_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ForumComment(models.Model):
    post = models.ForeignKey(ForumPost, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.post}"


class ForumLike(models.Model):
    post = models.ForeignKey(ForumPost, related_name="likes", on_delete=models.CASCADE)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")


class Community(models.Model):
    """A forum sub-community (e.g. 'Climat & Agriculture'). Users join to post there."""
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, blank=True, help_text="Emoji, e.g. 🌱")
    description = models.CharField(max_length=255, blank=True)
    members = models.ManyToManyField("auth.User", related_name="communities", blank=True)

    def __str__(self):
        return self.name


class PartnerLogo(models.Model):
    """A partner organization logo shown scrolling on the homepage. Admin-managed only."""
    name = models.CharField(max_length=150)
    logo_url = models.URLField()
    website_url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    """A team member shown on the 'Membres' page. Admin-managed only."""
    full_name = models.CharField(max_length=150)
    title = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=150, blank=True)
    photo_url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "full_name"]

    def __str__(self):
        return self.full_name


class HeroMedia(models.Model):
    """A slide in the homepage's scrolling media banner. Admin can add/remove; video_url
    takes priority over image_url if both are set."""
    title = models.CharField(max_length=150)
    text = models.CharField(max_length=255, blank=True)
    image_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class EmailVerificationToken(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="email_token")
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)


class Notification(models.Model):
    """A per-user notification (e.g. someone replied to your forum post)."""
    user = models.ForeignKey("auth.User", related_name="notifications", on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class NdviReading(models.Model):
    """
    Satellite vegetation health reading (NDVI, from NASA/ORNL MODIS MOD13Q1) for a region.
    NDVI ranges roughly -1 to 1; for cropland, higher generally means denser, healthier
    vegetation. Cached so repeated requests don't re-hit the satellite API every time.
    """
    region = models.ForeignKey(Region, related_name="ndvi_readings", on_delete=models.CASCADE)
    date = models.DateField()
    ndvi_value = models.FloatField()
    source = models.CharField(max_length=50, default="modis_mod13q1")

    class Meta:
        ordering = ["-date"]
        unique_together = ("region", "date", "source")

    def __str__(self):
        return f"{self.region.name} — {self.date} — NDVI {self.ndvi_value:.2f}"


class AdvisoryFeedback(models.Model):
    """
    'J'ai suivi ce conseil' + outcome — the field-truth feedback loop. Lets a farmer
    report whether they followed the day's advisory and what happened, so the platform
    can eventually learn from real outcomes instead of only computing rule-based advice.
    """
    OUTCOME_CHOICES = [
        ("good", "Bon résultat"), ("mixed", "Résultat mitigé"),
        ("poor", "Mauvais résultat"), ("too_early", "Trop tôt pour savoir"),
    ]
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="advisory_feedback")
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE)
    followed_advice = models.BooleanField()
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.region.name}/{self.crop.name} — suivi={self.followed_advice}"


class ExpertRequest(models.Model):
    """
    Escalation to a human agricultural agent — shown to the farmer when an AI photo
    diagnosis has low confidence. Admin sees these as a queue to follow up on.
    """
    STATUS_CHOICES = [("pending", "En attente"), ("contacted", "Contacté"), ("resolved", "Résolu")]
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    phone = models.CharField(max_length=30, blank=True)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.SET_NULL)
    context = models.TextField(help_text="Diagnostic IA ou description du problème, pour donner du contexte à l'agent")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Demande d'expert — {self.region} — {self.status}"


class Cooperative(models.Model):
    """A farmer cooperative. Has one manager (a FarmerProfile) who can see
    aggregated stats for the group's members — not individual member data."""
    name = models.CharField(max_length=150)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey("auth.User", related_name="managed_cooperatives", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class InstitutionalPartner(models.Model):
    """
    Marks a user account as an institutional partner (NGO, ministry, funder) with
    access to the aggregated, anonymized cross-region dashboard — never individual
    farmer data. Admin grants this flag; it is not self-service.
    """
    user = models.OneToOneField("auth.User", related_name="institutional_partner", on_delete=models.CASCADE)
    organization_name = models.CharField(max_length=200)
    approved = models.BooleanField(default=False, help_text="Admin must approve before dashboard access is granted")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.organization_name
