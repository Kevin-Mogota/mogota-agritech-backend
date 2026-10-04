from django.core.management.base import BaseCommand
from agroadvisor.models import Region, Crop, CultivationStage, Community

COMMUNITIES = [
    dict(slug="agriculture-generale", name="Agriculture générale", icon="🌱", description="Discussions générales sur les pratiques agricoles."),
    dict(slug="climat-agriculture", name="Climat & Agriculture", icon="🌦️", description="Adaptation climatique, sécheresse, saisons des pluies."),
    dict(slug="marche-agricole", name="Marché agricole", icon="🛒", description="Prix, débouchés, vente des récoltes."),
    dict(slug="agriculture-durable", name="Agriculture durable & Environnement", icon="🌍", description="Pratiques durables, sols, ressources en eau."),
    dict(slug="environnement-biodiversite", name="Environnement & Biodiversité", icon="🌳", description="Biodiversité, écosystèmes agricoles."),
]

REGIONS = [
    # Nord saharien — très aride, quasi pas de saison des pluies exploitable
    dict(name="Tibesti", admin_center="Bardaï", zone="Saharienne", soil_type="Rocailleux/désertique", rain_start_month=8, rain_end_month=8, rain_peak_mm=5, avg_temp_c=32, latitude=21.35, longitude=17.00),
    dict(name="Borkou", admin_center="Faya-Largeau", zone="Saharienne", soil_type="Sableux désertique", rain_start_month=7, rain_end_month=9, rain_peak_mm=8, avg_temp_c=38, latitude=17.92, longitude=19.11),
    dict(name="Ennedi Est", admin_center="Amdjarass", zone="Saharienne", soil_type="Rocailleux/sableux", rain_start_month=7, rain_end_month=9, rain_peak_mm=12, avg_temp_c=36, latitude=16.10, longitude=22.85),
    dict(name="Ennedi Ouest", admin_center="Fada", zone="Saharienne", soil_type="Rocailleux/sableux", rain_start_month=7, rain_end_month=9, rain_peak_mm=15, avg_temp_c=36, latitude=17.23, longitude=21.59),
    # Sahélienne sèche
    dict(name="Kanem", admin_center="Mao", zone="Sahélo-saharienne", soil_type="Sableux", rain_start_month=7, rain_end_month=9, rain_peak_mm=25, avg_temp_c=37, latitude=14.12, longitude=15.31),
    dict(name="Lac", admin_center="Bol", zone="Sahélienne sèche", soil_type="Sablo-limoneux (proche lac Tchad)", rain_start_month=6, rain_end_month=9, rain_peak_mm=35, avg_temp_c=35, latitude=13.47, longitude=14.72),
    dict(name="Barh el Gazel", admin_center="Moussoro", zone="Sahélienne sèche", soil_type="Sableux", rain_start_month=6, rain_end_month=9, rain_peak_mm=30, avg_temp_c=36, latitude=13.64, longitude=16.49),
    dict(name="Wadi Fira", admin_center="Biltine", zone="Sahélienne sèche", soil_type="Sablo-rocailleux", rain_start_month=6, rain_end_month=9, rain_peak_mm=40, avg_temp_c=35, latitude=14.53, longitude=20.92),
    dict(name="Batha", admin_center="Ati", zone="Sahélienne sèche", soil_type="Sablo-limoneux", rain_start_month=6, rain_end_month=9, rain_peak_mm=45, avg_temp_c=36, latitude=13.22, longitude=18.69),
    # Sahélienne
    dict(name="N'Djaména", admin_center="N'Djaména (capitale)", zone="Sahélienne", soil_type="Sableux", rain_start_month=6, rain_end_month=9, rain_peak_mm=90, avg_temp_c=34, latitude=12.11, longitude=15.06),
    dict(name="Hadjer-Lamis", admin_center="Massakory", zone="Sahélienne", soil_type="Sablo-argileux", rain_start_month=6, rain_end_month=9, rain_peak_mm=85, avg_temp_c=34, latitude=13.00, longitude=15.73),
    dict(name="Chari-Baguirmi", admin_center="Massenya", zone="Sahélienne", soil_type="Argilo-sableux", rain_start_month=6, rain_end_month=10, rain_peak_mm=95, avg_temp_c=33, latitude=11.40, longitude=16.17),
    dict(name="Guéra", admin_center="Mongo", zone="Sahélienne", soil_type="Ferrugineux", rain_start_month=6, rain_end_month=9, rain_peak_mm=100, avg_temp_c=33, latitude=12.18, longitude=18.69),
    dict(name="Ouaddaï", admin_center="Abéché", zone="Sahélienne", soil_type="Sablo-limoneux", rain_start_month=6, rain_end_month=9, rain_peak_mm=70, avg_temp_c=35, latitude=13.83, longitude=20.83),
    dict(name="Sila", admin_center="Goz Beïda", zone="Sahélienne", soil_type="Sablo-argileux", rain_start_month=6, rain_end_month=9, rain_peak_mm=75, avg_temp_c=34, latitude=12.22, longitude=21.42),
    dict(name="Salamat", admin_center="Am Timan", zone="Sahélienne", soil_type="Argilo-sableux", rain_start_month=5, rain_end_month=10, rain_peak_mm=110, avg_temp_c=33, latitude=11.03, longitude=20.28),
    # Sahélo-soudanienne / transition
    dict(name="Mayo-Kebbi Est", admin_center="Bongor", zone="Sahélo-soudanienne", soil_type="Argilo-sableux", rain_start_month=5, rain_end_month=10, rain_peak_mm=150, avg_temp_c=31, latitude=10.28, longitude=15.37),
    dict(name="Tandjilé", admin_center="Laï", zone="Sahélo-soudanienne", soil_type="Argilo-sableux", rain_start_month=5, rain_end_month=10, rain_peak_mm=160, avg_temp_c=31, latitude=9.40, longitude=16.30),
    # Soudanienne — sud, plus arrosé
    dict(name="Mayo-Kebbi Ouest", admin_center="Pala", zone="Soudanienne", soil_type="Argilo-sableux", rain_start_month=4, rain_end_month=10, rain_peak_mm=190, avg_temp_c=30, latitude=9.36, longitude=14.90),
    dict(name="Logone Occidental", admin_center="Moundou", zone="Soudanienne", soil_type="Argilo-sableux", rain_start_month=4, rain_end_month=10, rain_peak_mm=220, avg_temp_c=30, latitude=8.57, longitude=16.08),
    dict(name="Logone Oriental", admin_center="Doba", zone="Soudanienne", soil_type="Ferrugineux", rain_start_month=4, rain_end_month=10, rain_peak_mm=230, avg_temp_c=29, latitude=8.65, longitude=16.85),
    dict(name="Mandoul", admin_center="Koumra", zone="Soudanienne", soil_type="Ferrugineux", rain_start_month=4, rain_end_month=10, rain_peak_mm=225, avg_temp_c=29, latitude=8.91, longitude=17.55),
    dict(name="Moyen-Chari", admin_center="Sarh", zone="Soudanienne", soil_type="Ferrugineux", rain_start_month=4, rain_end_month=10, rain_peak_mm=200, avg_temp_c=31, latitude=9.14, longitude=18.39),
]

CROPS = [
    dict(name="Sorgho", sow_window_start_month=6, sow_window_end_month=7, cycle_days=110, water_need="moyen",
         grows_rain_season=True, grows_off_season=False,
         min_rain_mm=400, yield_range="700 – 1 300 kg/ha (systèmes traditionnels pluvial, faible intrant)",
         soil_note="Culture rustique, peu exigeante, mais préfère un sol bien drainé sans excès d'eau stagnante.",
         stages=[
             ("Avant semis", "J-30 à J-7", "soil", [
                 "Labour ou grattage du sol après les premières pluies utiles",
                 "Épandage de fumure organique si disponible (compost, fumier)",
                 "Sélection de semences saines de la campagne précédente ou certifiées",
             ]),
             ("Semis", "J0", "seed", [
                 "Semis en poquets à 3-4 cm de profondeur, écartement ~0,8 x 0,4 m",
                 "2-3 graines par poquet, démariage prévu 2 semaines après levée",
             ]),
             ("Entretien", "J15 – J60", "care", [
                 "Démariage à 1-2 plants par poquet vers J15",
                 "1er sarclage à J15-20, 2e sarclage à J35-40",
                 "Buttage léger si nécessaire pour limiter la verse",
             ]),
             ("Récolte", "J95 – J110", "harvest", [
                 "Récolte quand les grains sont durs et les panicules sèches",
                 "Coupe des panicules, séchage au champ 3-5 jours avant battage",
             ]),
             ("Après récolte", "Post-récolte", "storage", [
                 "Battage et vannage, séchage final à moins de 13% d'humidité",
                 "Stockage en sacs ou greniers traditionnels, à l'abri de l'humidité et des insectes",
             ]),
         ]),
    dict(name="Mil", sow_window_start_month=6, sow_window_end_month=7, cycle_days=90, water_need="faible",
         grows_rain_season=True, grows_off_season=False,
         min_rain_mm=300, yield_range="400 – 900 kg/ha (systèmes traditionnels pluvial, faible intrant)",
         soil_note="Très tolérant à la sécheresse et aux sols pauvres — souvent la culture de dernier recours en zone sahélienne sèche.",
         stages=[
             ("Avant semis", "J-20 à J-5", "soil", [
                 "Grattage léger du sol, pas de labour profond nécessaire",
                 "Épandage de matière organique si disponible sur les points de semis",
             ]),
             ("Semis", "J0", "seed", [
                 "Semis en poquets à 2-3 cm de profondeur, écartement ~1 x 0,5 m",
                 "4-6 graines par poquet",
             ]),
             ("Entretien", "J10 – J45", "care", [
                 "Démariage à 2-3 plants par poquet vers J10-12",
                 "Sarclage précoce dès J10 (sensible à la concurrence des adventices en début de cycle)",
             ]),
             ("Récolte", "J80 – J90", "harvest", [
                 "Récolte à maturité des épis (grains durs, épis penchés)",
                 "Coupe des épis, séchage au soleil avant battage",
             ]),
             ("Après récolte", "Post-récolte", "storage", [
                 "Battage manuel, vannage soigné (grain léger et fragile)",
                 "Stockage en greniers ventilés, protection contre les charançons",
             ]),
         ]),
    dict(name="Arachide", sow_window_start_month=6, sow_window_end_month=6, cycle_days=100, water_need="moyen",
         grows_rain_season=True, grows_off_season=False,
         min_rain_mm=450, yield_range="650 – 950 kg/ha (systèmes traditionnels pluvial, faible intrant)",
         soil_note="Un sol trop compact ou argileux gêne la formation des gousses en terre — éviter les sols lourds.",
         stages=[
             ("Avant semis", "J-20 à J-5", "soil", [
                 "Labour léger et émiettement fin du sol",
                 "Éviter les parcelles ayant reçu de la fumure fraîche non décomposée",
             ]),
             ("Semis", "J0", "seed", [
                 "Semis à 3-5 cm de profondeur, écartement ~0,5 x 0,2 m",
                 "1-2 graines décortiquées par poquet",
             ]),
             ("Entretien", "J15 – J55", "care", [
                 "1er sarclage à J15-20, 2e sarclage à J35-40",
                 "Buttage léger au stade floraison pour faciliter l'entrée des gynophores dans le sol",
             ]),
             ("Récolte", "J90 – J100", "harvest", [
                 "Arrachage quand les feuilles jaunissent et les gousses ont une coque marquée",
                 "Séchage en petits tas (andains) au champ 5-8 jours",
             ]),
             ("Après récolte", "Post-récolte", "storage", [
                 "Égoussage puis séchage final des gousses avant stockage",
                 "Stockage au sec, ventilé, vigilance contre l'aflatoxine (moisissures) en cas d'humidité",
             ]),
         ]),
    dict(name="Maïs", sow_window_start_month=5, sow_window_end_month=6, cycle_days=95, water_need="eleve",
         grows_rain_season=True, grows_off_season=False,
         min_rain_mm=600, yield_range="950 – 1 300 kg/ha en culture traditionnelle (jusqu'à 3-4,5 t/ha avec intrants)",
         soil_note="Le plus exigeant des quatre cultures en fertilité du sol et en eau — à réserver aux zones les mieux arrosées.",
         stages=[
             ("Avant semis", "J-30 à J-7", "soil", [
                 "Labour profond, apport de fumure organique ou minérale de fond",
                 "Choix de variétés adaptées à la durée de la saison des pluies locale",
             ]),
             ("Semis", "J0", "seed", [
                 "Semis à 4-5 cm de profondeur, écartement ~0,8 x 0,4 m",
                 "2 graines par poquet",
             ]),
             ("Entretien", "J15 – J60", "care", [
                 "Démariage à 1 plant par poquet vers J15",
                 "Sarclage-buttage à J20-25, apport d'engrais azoté de couverture si disponible",
                 "Surveillance renforcée des ravageurs (chenilles légionnaires)",
             ]),
             ("Récolte", "J85 – J95", "harvest", [
                 "Récolte quand les spathes jaunissent et les grains sont fermes",
                 "Séchage des épis avant égrenage",
             ]),
             ("Après récolte", "Post-récolte", "storage", [
                 "Égrenage puis séchage final à moins de 13% d'humidité",
                 "Stockage en sacs hermétiques ou silos métalliques pour limiter les pertes post-récolte",
             ]),
         ]),

    dict(name="Tomate", sow_window_start_month=10, sow_window_end_month=12, cycle_days=90, water_need="eleve",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="15 – 35 t/ha en maraîchage irrigué avec bonne conduite",
         soil_note="Sensible à l'excès d'eau au niveau des racines. Rotation conseillée (éviter après aubergine, poivron, piment, pomme de terre).",
         stages=[
             ("Pépinière", "J-30 à J-25", "seed", ["Semis en pépinière ombragée, terreau léger, arrosage quotidien", "Repiquage à 4-5 vraies feuilles"]),
             ("Avant repiquage", "J-25 à J-1", "soil", ["Labour profond, apport de compost", "Buttes ou billons pour le drainage"]),
             ("Repiquage", "J0", "seed", ["Écartement ~0,5 x 0,6 m"]),
             ("Entretien", "J10 – J60", "care", ["Tuteurage/paillage", "Irrigation régulière et constante"]),
             ("Récolte", "J60 – J90", "harvest", ["Récolte échelonnée dès coloration, tous les 3-4 jours"]),
         ]),
    dict(name="Poivron", sow_window_start_month=10, sow_window_end_month=12, cycle_days=100, water_need="eleve",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="10 – 20 t/ha en maraîchage irrigué",
         soil_note="Exigeant en chaleur, sensible aux excès d'eau. Éviter après aubergine, tomate ou piment.",
         stages=[
             ("Pépinière", "J-45 à J-35", "seed", ["Semis en pépinière, germination lente (10-15 jours)"]),
             ("Avant repiquage", "J-35 à J-1", "soil", ["Sol ameubli, apport de matière organique"]),
             ("Repiquage", "J0", "seed", ["Écartement ~0,4 x 0,5 m"]),
             ("Entretien", "J10 – J70", "care", ["Irrigation régulière", "Tuteurage léger conseillé"]),
             ("Récolte", "J75 – J100", "harvest", ["Récolte vert ou coloré selon marché, cueillette régulière"]),
         ]),
    dict(name="Chou", sow_window_start_month=9, sow_window_end_month=11, cycle_days=75, water_need="moyen",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="20 – 40 t/ha en maraîchage irrigué",
         soil_note="Grand consommateur d'eau et de matière organique. Sensible à la chaleur excessive.",
         stages=[
             ("Pépinière", "J-30 à J-25", "seed", ["Semis en pépinière ombragée"]),
             ("Avant repiquage", "J-25 à J-1", "soil", ["Labour profond, fumure organique généreuse"]),
             ("Repiquage", "J0", "seed", ["Écartement ~0,5 x 0,5 m"]),
             ("Entretien", "J10 – J50", "care", ["Arrosage fréquent, surtout à la formation de la pomme", "Surveillance des chenilles"]),
             ("Récolte", "J60 – J75", "harvest", ["Récolte quand la pomme est ferme et compacte"]),
         ]),
    dict(name="Oignon", sow_window_start_month=10, sow_window_end_month=11, cycle_days=120, water_need="moyen",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="15 – 25 t/ha en maraîchage irrigué",
         soil_note="Sensible à la concurrence des adventices (racines superficielles). Rotation conseillée.",
         stages=[
             ("Pépinière", "J-60 à J-50", "seed", ["Semis dense en pépinière"]),
             ("Avant repiquage", "J-50 à J-1", "soil", ["Sol finement travaillé, matière organique bien décomposée"]),
             ("Repiquage", "J0", "seed", ["Écartement ~0,1 x 0,2 m en lignes"]),
             ("Entretien", "J10 – J90", "care", ["Désherbage fréquent", "Irrigation réduite en fin de cycle"]),
             ("Récolte", "J110 – J130", "harvest", ["Récolte au jaunissement des feuilles, séchage 2-3 jours"]),
         ]),
    dict(name="Aubergine", sow_window_start_month=9, sow_window_end_month=11, cycle_days=100, water_need="moyen",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="15 – 30 t/ha en maraîchage irrigué",
         soil_note="Bonne tolérance à la chaleur. Éviter la succession avec tomate, poivron, piment.",
         stages=[
             ("Pépinière", "J-35 à J-25", "seed", ["Semis en pépinière ombragée"]),
             ("Avant repiquage", "J-25 à J-1", "soil", ["Labour profond, fumure organique"]),
             ("Repiquage", "J0", "seed", ["Écartement ~0,6 x 0,6 m"]),
             ("Entretien", "J10 – J70", "care", ["Irrigation régulière, paillage conseillé", "Surveillance punaises/chenilles foreuses"]),
             ("Récolte", "J70 – J100", "harvest", ["Récolte ferme et brillante, cueillette régulière"]),
         ]),
    dict(name="Carotte", sow_window_start_month=10, sow_window_end_month=12, cycle_days=90, water_need="moyen",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="15 – 30 t/ha en maraîchage irrigué",
         soil_note="Sol trop compact ou caillouteux déforme les racines. Éviter fumure fraîche non décomposée.",
         stages=[
             ("Avant semis", "J-20 à J-5", "soil", ["Labour profond, émiettement fin, sol débarrassé des cailloux"]),
             ("Semis", "J0", "seed", ["Semis direct, faible profondeur (~1 cm), pas de repiquage"]),
             ("Entretien", "J10 – J70", "care", ["Éclaircissage à J20-25", "Arrosage léger et régulier", "Désherbage manuel soigné"]),
             ("Récolte", "J90 – J110", "harvest", ["Récolte au diamètre souhaité, après arrosage pour faciliter l'arrachage"]),
         ]),
    dict(name="Piment", sow_window_start_month=9, sow_window_end_month=11, cycle_days=100, water_need="moyen",
         min_rain_mm=0, grows_rain_season=False, grows_off_season=True,
         yield_range="5 – 12 t/ha en maraîchage irrigué (frais)",
         soil_note="Proche de la conduite du poivron mais plus tolérant à la chaleur et à la sécheresse modérée.",
         stages=[
             ("Pépinière", "J-40 à J-30", "seed", ["Semis en pépinière ombragée"]),
             ("Avant repiquage", "J-30 à J-1", "soil", ["Sol ameubli, apport de compost"]),
             ("Repiquage", "J0", "seed", ["Écartement ~0,4 x 0,5 m"]),
             ("Entretien", "J10 – J70", "care", ["Irrigation modérée mais régulière"]),
             ("Récolte", "J70 – J100", "harvest", ["Récolte échelonnée sur plusieurs mois"]),
         ]),
    dict(name="Gombo", sow_window_start_month=3, sow_window_end_month=6, cycle_days=60, water_need="faible",
         min_rain_mm=100, grows_rain_season=True, grows_off_season=True,
         yield_range="6 – 12 t/ha (fruits frais), culture traditionnelle à intrants modérés",
         soil_note="Culture rustique et résistante à la chaleur — se cultive en saison des pluies comme en contre-saison avec irrigation d'appoint.",
         stages=[
             ("Avant semis", "J-15 à J-5", "soil", ["Labour léger, fumure organique si disponible"]),
             ("Semis", "J0", "seed", ["Semis direct en poquets, écartement ~0,6 x 0,4 m"]),
             ("Entretien", "J10 – J50", "care", ["Démariage à 1-2 plants/poquet", "Sarclage régulier, arrosage d'appoint en contre-saison"]),
             ("Récolte", "J55 – J55+", "harvest", ["Récolte des fruits jeunes tous les 2-3 jours dès J55"]),
         ]),
]


class Command(BaseCommand):
    help = "Seed the database with the regions, crops and cultivation guide used in the Mogota Agri-Tech prototype."

    def handle(self, *args, **options):
        for r in REGIONS:
            obj, created = Region.objects.update_or_create(name=r["name"], defaults=r)
            self.stdout.write(f"{'Créé' if created else 'Mis à jour'} : région {obj.name}")

        for c in CROPS:
            stages = c.pop("stages")
            obj, created = Crop.objects.update_or_create(name=c["name"], defaults=c)
            self.stdout.write(f"{'Créé' if created else 'Mis à jour'} : culture {obj.name}")
            obj.stages.all().delete()
            for i, (title, timing, icon, actions) in enumerate(stages):
                CultivationStage.objects.create(
                    crop=obj, order=i, title=title, timing_label=timing, icon=icon, actions=actions,
                )

        for com in COMMUNITIES:
            obj, created = Community.objects.update_or_create(slug=com["slug"], defaults=com)
            self.stdout.write(f"{'Créée' if created else 'Mise à jour'} : communauté {obj.name}")

        self.stdout.write(self.style.SUCCESS("Données de démonstration installées."))
