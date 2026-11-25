"""Generate an XLSX template matching this backend's import contract."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from openpyxl import Workbook

from metadata.imports import SHEETS


class Command(BaseCommand):
    help = "Write a metadata import template; --example adds synthetic rows for the demo fixtures."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Destination .xlsx file.")
        parser.add_argument("--example", action="store_true")
        parser.add_argument("--force", action="store_true", help="Replace an existing destination.")

    def handle(self, *args, **options):
        destination = Path(options["path"]).expanduser()
        if destination.suffix.lower() != ".xlsx":
            raise CommandError("Use an .xlsx destination.")
        if destination.exists() and not options["force"]:
            raise CommandError("Destination already exists. Use --force to replace it.")
        if not destination.parent.is_dir():
            raise CommandError("The destination directory must exist.")

        examples = {
            "Physical Devices": {
                "ref": "station-a", "name": "Example station", "device_type": 1,
                "location": json.dumps({"type": "Point", "coordinates": [33.36, 35.15]}),
                "communication_parameters": json.dumps({"IP": "10.0.0.10"}),
            },
            "Network Elements": {
                "ref": "site-a", "name": "Example site", "element_type": 1,
                "external_identifiers": json.dumps([{"source": "DEMO", "value": "SITE-101"}]),
                "network_area": "Example area", "elevation": 120.5, "address": "Example Street 1, Nicosia",
            },
            "Measurements": {
                "name": "Example temperature", "physical_device": "@station-a", "network_element": "@site-a",
                "measurement_type": 1, "measurement_unit": 1,
                "data_collection_config": json.dumps({
                    "protocol": "https", "endpoint": "https://example.invalid/metadata",
                    "source_identifier": "DEMO-101", "extra_settings": {"interval_seconds": 60},
                }),
            },
        }
        workbook = Workbook()
        workbook.remove(workbook.active)
        try:
            for name, spec in SHEETS.items():
                sheet = workbook.create_sheet(name)
                headers = (*spec.required, *spec.optional)
                sheet.append(headers)
                if options["example"]:
                    sheet.append([examples[name].get(header) for header in headers])
                sheet.freeze_panes = "A2"
                sheet.auto_filter.ref = sheet.dimensions
            workbook.save(destination)
        except OSError as error:
            raise CommandError(f"Could not write the workbook: {error}") from error
        finally:
            workbook.close()
        self.stdout.write(self.style.SUCCESS(f"Created {destination}"))
