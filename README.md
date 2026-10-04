# Mogota Agri-Tech — Backend Django

Projet Django **exécutable tel quel** : `manage.py` + `config/` (settings,
urls, wsgi, asgi) + l'app métier `agroadvisor` (régions, cultures, guide de
culture, conseil du jour, alertes SMS, assistant IA, météo réelle).

## 1. Installation

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseignez ANTHROPIC_API_KEY
```

## 2. Base de données PostgreSQL

Le projet utilise PostgreSQL par défaut (`.env.example` est déjà configuré pour).

**Installer PostgreSQL — Windows**
1. Téléchargez l'installeur sur [postgresql.org/download/windows](https://www.postgresql.org/download/windows/).
2. Lancez-le, gardez le port par défaut (5432), notez le mot de passe que vous donnez à l'utilisateur `postgres`.
3. Ouvrez "SQL Shell (psql)" depuis le menu Démarrer, connectez-vous, puis :
```sql
CREATE USER mati_user WITH PASSWORD 'choisissez-un-mot-de-passe';
CREATE DATABASE mati_db OWNER mati_user;
```

**Installer PostgreSQL — Linux (Ubuntu/Debian)**
```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER mati_user WITH PASSWORD 'choisissez-un-mot-de-passe';"
sudo -u postgres psql -c "CREATE DATABASE mati_db OWNER mati_user;"
```

**Configurer le projet**

Dans `.env`, renseignez le mot de passe choisi :
```
DB_ENGINE=django.db.backends.postgresql
DB_NAME=mati_db
DB_USER=mati_user
DB_PASSWORD=choisissez-un-mot-de-passe
DB_HOST=localhost
DB_PORT=5432
```

**Vérifier que Django y arrive bien**, puis charger les données de démonstration :
```bash
python manage.py makemigrations agroadvisor
python manage.py migrate
python manage.py seed_agroadvisor   # installe les 23 provinces du Tchad et les cultures
python manage.py createsuperuser    # pour accéder à /admin/
python manage.py runserver          # démarre sur http://127.0.0.1:8000/
```

**Basculer sur SQLite pour un test rapide sans PostgreSQL** — dans `.env`, remplacez simplement :
```
DB_ENGINE=django.db.backends.sqlite3
```
Django utilisera automatiquement un fichier `db.sqlite3` local. Pratique pour tester vite, mais SQLite ne convient pas à un déploiement avec plusieurs utilisateurs simultanés — PostgreSQL reste la bonne base pour la suite (Module 7, déploiement).

**Vérifier que les données sont bien dans PostgreSQL** (et pas ailleurs) :
```bash
psql -U mati_user -d mati_db -c "\dt"              # liste les tables
psql -U mati_user -d mati_db -c "SELECT * FROM agroadvisor_region LIMIT 5;"
```

## 3. Météo réelle (NASA POWER)

Les 5 régions du seed ont déjà leurs coordonnées GPS. Pour remplacer les
données de pluie simulées par de vraies données NASA POWER (gratuit, sans
clé API, bonne couverture Sahel) :

```bash
python manage.py fetch_weather --year 2026
# ou une seule région :
python manage.py fetch_weather --year 2026 --region "N'Djamena"
```

Cette commande interroge `https://power.larc.nasa.gov/` et met en cache les
données jour par jour dans `WeatherReading`. `/api/advisory/` et le guide de
culture utilisent automatiquement ces données réelles dès qu'elles existent
pour l'année en cours, et retombent sur l'estimation simulée pour les mois
non encore couverts (utile en cours d'année). Pensez à relancer cette
commande périodiquement (cron / tâche planifiée) pour garder les données à
jour.

## 4. Endpoints exposés

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/regions/` | GET | Liste des régions et leur profil climatique |
| `/api/crops/` | GET | Liste des cultures, avec leur guide de culture (`stages`) |
| `/api/advisory/?region=...&crop=...` | GET | Conseil du jour (semis, irrigation, risque) |
| `/api/sms-alerts/` | GET, POST | Historique et création d'alertes SMS (simulées ou réelles) |
| `/api/chat/` | POST | Proxy vers l'assistant IA (`{"session_id", "message", "region", "crop"}`) |

## 5. Brancher le frontend React sur cette API

Dans le prototype (`mogota-agritech-dashboard.jsx`), remplacer les fonctions
`computeAdvice`, `buildRainfallSeries` et l'appel direct à l'API Anthropic
par des appels `fetch` vers ces endpoints, par exemple :

```js
const res = await fetch(`${API_BASE}/api/advisory/?region=${region}&crop=${crop}`);
const advice = await res.json();
```

## 6. Prochaines étapes suggérées

- Remplacer la pluviométrie simulée (`services.get_rainfall_series`) par un
  vrai fournisseur météo (NASA POWER, station locale, etc.) ou par le modèle
  `WeatherReading` déjà prévu à cet effet.
- Brancher `SmsAlertViewSet.perform_create` sur une vraie passerelle SMS/USSD
  (Africa's Talking, Twilio…).
- Ajouter l'authentification (DRF Token/JWT) avant tout déploiement public,
  les vues sont actuellement ouvertes (`AllowAny`) pour la démonstration.
