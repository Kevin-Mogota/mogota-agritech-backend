import datetime

from django.core.management.base import BaseCommand, CommandError

from agroadvisor.models import Region
from agroadvisor.weather_provider import sync_region_weather, WeatherProviderError


class Command(BaseCommand):
    help = "Fetch real daily rainfall/temperature data from NASA POWER for all regions and cache it in WeatherReading."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year", type=int, default=datetime.date.today().year,
            help="Calendar year to fetch (default: current year).",
        )
        parser.add_argument(
            "--region", type=str, default=None,
            help="Fetch a single region by name instead of all of them.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        regions = Region.objects.all()
        if options["region"]:
            regions = regions.filter(name=options["region"])
            if not regions.exists():
                raise CommandError(f"Région introuvable : {options['region']}")

        for region in regions:
            if region.latitude is None or region.longitude is None:
                self.stdout.write(self.style.WARNING(
                    f"Ignoré — {region.name} n'a pas de latitude/longitude renseignée."
                ))
                continue
            try:
                count = sync_region_weather(region, year)
                self.stdout.write(self.style.SUCCESS(f"{region.name} : {count} jours synchronisés pour {year}."))
            except WeatherProviderError as exc:
                self.stdout.write(self.style.ERROR(f"{region.name} : {exc}"))
