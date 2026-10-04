from django.core.management.base import BaseCommand, CommandError

from agroadvisor.models import Region
from agroadvisor.ndvi_provider import sync_region_ndvi, NdviProviderError


class Command(BaseCommand):
    help = "Fetch the latest satellite NDVI (vegetation health) reading from NASA/ORNL MODIS for all regions."

    def add_arguments(self, parser):
        parser.add_argument("--region", type=str, default=None, help="Sync a single region by name instead of all of them.")

    def handle(self, *args, **options):
        regions = Region.objects.all()
        if options["region"]:
            regions = regions.filter(name=options["region"])
            if not regions.exists():
                raise CommandError(f"Région introuvable : {options['region']}")

        for region in regions:
            if region.latitude is None or region.longitude is None:
                self.stdout.write(self.style.WARNING(f"Ignoré — {region.name} n'a pas de latitude/longitude."))
                continue
            try:
                reading = sync_region_ndvi(region)
                self.stdout.write(self.style.SUCCESS(f"{region.name} : NDVI {reading.ndvi_value:.2f} au {reading.date}"))
            except NdviProviderError as exc:
                self.stdout.write(self.style.ERROR(f"{region.name} : {exc}"))
