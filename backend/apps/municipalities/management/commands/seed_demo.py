"""Build a browsable demonstration instance.

The proof of concept is for Reichenbach im Vogtland, so the demonstration uses
that municipality's real name, municipality key and location. Everything else is
invented: the district list is illustrative rather than the official one, the
boundaries are synthetic rectangles rather than surveyed geometry, and the
objects, reports and owners are fictional. A real installation replaces all of
it with imported geodata and its own records.

The command refuses to run outside development unless explicitly forced, because
it creates accounts with known passwords.
"""

import datetime

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.documents.models import DocumentKind, PropertyDocument, Visibility
from apps.geodata.models import GeoFeature, GeoLayer, LayerCategory
from apps.geodata.services import refresh_context
from apps.heritage.models import CheckResult, HeritageCheck, MonumentRecord, ProtectionScope
from apps.inspections.models import Inspection, InspectionKind, InspectionResult
from apps.municipalities.models import District, DistrictKind, Municipality
from apps.owners.models import ContactState, Owner, Ownership, OwnerKind
from apps.parcels.models import Parcel, ParcelSource
from apps.participation.models import Badge
from apps.properties.choices import (
    AssessmentSource,
    ConditionGrade,
    DamageType,
    Priority,
    PropertyType,
    RecordStatus,
    UseCategory,
    VacancyStatus,
)
from apps.properties.models import Property
from apps.reports.models import Report, ReportCategory, ReportStatus
from apps.reports.services import create_property_from_report
from apps.statistics.services import take_snapshot
from apps.workflows.models import Task, TaskType
from organizations.models import Organization, Role

User = get_user_model()

MUNICIPALITY_NAME = "Reichenbach im Vogtland"
MUNICIPALITY_KEY = "14523250"
CENTRE = (12.3036, 50.6236)  # longitude, latitude

# Illustrative districts. Replace with the official list and real boundaries.
DISTRICTS = [
    ("Innenstadt", DistrictKind.QUARTER, (0.000, 0.000)),
    ("Bahnhofsviertel", DistrictKind.QUARTER, (0.012, -0.006)),
    ("Brunn", DistrictKind.LOCALITY, (-0.030, 0.014)),
    ("Cunsdorf", DistrictKind.LOCALITY, (0.026, 0.018)),
    ("Friesen", DistrictKind.LOCALITY, (-0.022, -0.020)),
    ("Rotschau", DistrictKind.LOCALITY, (0.034, -0.024)),
]

# Staff accounts, one per department, so the role boundaries can be tried out.
STAFF = [
    ("demo.owner", Role.OWNER, "Verwaltungsleitung"),
    ("demo.bauamt", Role.BUILDING_AUTHORITY, "Bauaufsicht"),
    ("demo.planung", Role.URBAN_PLANNING, "Stadtplanung"),
    ("demo.liegenschaften", Role.PROPERTY_MANAGEMENT, "Liegenschaften"),
    ("demo.wirtschaft", Role.ECONOMIC_DEVELOPMENT, "Wirtschaftsförderung"),
    ("demo.ordnungsamt", Role.REGULATORY_OFFICE, "Ordnungsamt"),
    ("demo.denkmalschutz", Role.HERITAGE_AUTHORITY, "Denkmalschutz"),
    ("demo.landkreis", Role.EXTERNAL_AGENCY, "Vogtlandkreis"),
    ("demo.helfer", Role.VERIFIED_CONTRIBUTOR, "Verified contributor"),
]

DEMO_PASSWORD = "demo-passwort-nur-lokal"

# Fictional objects, chosen to cover the states the dashboard reports on.
OBJECTS = [
    {
        "street": "Bahnhofstraße",
        "house_number": "12",
        "district": "Bahnhofsviertel",
        "offset": (0.0104, -0.0052),
        "property_type": PropertyType.MIXED_USE,
        "last_known_use": UseCategory.RETAIL,
        "status": RecordStatus.CONFIRMED,
        "vacancy_status": VacancyStatus.VACANT,
        "condition": ConditionGrade.MAJOR_REPAIR,
        "condition_source": AssessmentSource.STAFF_ASSESSMENT,
        "priority": Priority.HIGH,
        "year_built": 1908,
        "units_total": 6,
        "units_vacant": 6,
        "public": "Former shop on the ground floor, empty since 2019.",
        "internal": "Owner reached once in 2024, no response since. Heirs unclear.",
        "damages": [DamageType.FACADE, DamageType.WINDOWS],
        "is_public": True,
    },
    {
        "street": "Zwickauer Straße",
        "house_number": "45",
        "district": "Innenstadt",
        "offset": (0.0018, 0.0011),
        "property_type": PropertyType.RESIDENTIAL,
        "last_known_use": UseCategory.HOUSING,
        "status": RecordStatus.MONITORING,
        "vacancy_status": VacancyStatus.PARTIALLY_VACANT,
        "condition": ConditionGrade.MINOR_REPAIR,
        "condition_source": AssessmentSource.STAFF_ASSESSMENT,
        "priority": Priority.MEDIUM,
        "year_built": 1935,
        "units_total": 4,
        "units_vacant": 2,
        "public": "Two of four flats have stood empty for over a year.",
        "internal": "Owner is renovating gradually and asks to be left alone.",
        "damages": [],
        "is_public": True,
    },
    {
        "street": "Weberstraße",
        "house_number": "3",
        "district": "Innenstadt",
        "offset": (-0.0026, 0.0016),
        "property_type": PropertyType.RESIDENTIAL,
        "last_known_use": UseCategory.HOUSING,
        "status": RecordStatus.RESEARCH,
        "vacancy_status": VacancyStatus.VACANT,
        "condition": ConditionGrade.COLLAPSE_RISK,
        "condition_source": AssessmentSource.EXPERT_REPORT,
        "priority": Priority.CRITICAL,
        "year_built": 1890,
        "units_total": 3,
        "units_vacant": 3,
        "public": "Listed building, secured. Roof partially collapsed.",
        "internal": "Structural report from 2025 recommends immediate securing.",
        "damages": [DamageType.ROOF, DamageType.STRUCTURE, DamageType.MOISTURE],
        "heritage": True,
        "is_public": True,
    },
    {
        "street": "Färbergasse",
        "house_number": "8",
        "district": "Innenstadt",
        "offset": (-0.0011, -0.0019),
        "property_type": PropertyType.COMMERCIAL,
        "last_known_use": UseCategory.CRAFT,
        "status": RecordStatus.ON_SITE_CHECK,
        "vacancy_status": VacancyStatus.SUSPECTED_VACANT,
        "condition": ConditionGrade.UNKNOWN,
        "condition_source": AssessmentSource.CITIZEN_OBSERVATION,
        "priority": Priority.MEDIUM,
        "public": "",
        "internal": "Reported by a citizen; site visit still to be arranged.",
        "damages": [DamageType.VEGETATION],
        "is_public": False,
    },
    {
        "street": "Am Anger",
        "house_number": "",
        "district": "Brunn",
        "offset": (-0.0295, 0.0138),
        "property_type": PropertyType.BROWNFIELD,
        "last_known_use": UseCategory.PRODUCTION,
        "status": RecordStatus.CONFIRMED,
        "vacancy_status": VacancyStatus.VACANT,
        "condition": ConditionGrade.SEVERELY_DAMAGED,
        "condition_source": AssessmentSource.STAFF_ASSESSMENT,
        "priority": Priority.MEDIUM,
        "public": "Former workshop site, buildings largely demolished.",
        "internal": "Municipality holds an option; contamination not yet assessed.",
        "damages": [DamageType.WASTE],
        "address_note": "Behind the fire station",
        "is_public": True,
    },
    {
        "street": "Dorfstraße",
        "house_number": "17",
        "district": "Friesen",
        "offset": (-0.0217, -0.0196),
        "property_type": PropertyType.AGRICULTURAL,
        "last_known_use": UseCategory.AGRICULTURE,
        "status": RecordStatus.NOT_CONFIRMED,
        "vacancy_status": VacancyStatus.IN_USE,
        "condition": ConditionGrade.GOOD,
        "condition_source": AssessmentSource.STAFF_ASSESSMENT,
        "priority": Priority.LOW,
        "public": "",
        "internal": "Report not confirmed: the barn is in use for storage.",
        "damages": [],
        "is_public": False,
    },
]

# Reports still waiting in the moderation queue.
PENDING_REPORTS = [
    {
        "category": ReportCategory.SUSPECTED_VACANCY,
        "description": "Letterbox has been overflowing for months, blinds always down.",
        "street": "Lengenfelder Straße",
        "house_number": "22",
        "offset": (0.0071, 0.0043),
        "damage": [],
        "contact_name": "A. Beispiel",
        "contact_email": "a.beispiel@example.org",
        "wants_feedback": True,
    },
    {
        "category": ReportCategory.HAZARD,
        "description": "Roof tiles falling onto the pavement, children walk past here.",
        "street": "Obere Dunkelgasse",
        "house_number": "4",
        "offset": (-0.0043, 0.0026),
        "damage": [DamageType.ROOF, DamageType.FALLING_PARTS],
        "contact_name": "",
        "contact_email": "",
        "wants_feedback": False,
    },
    {
        "category": ReportCategory.NEGLECT,
        "description": "Garden completely overgrown, rubbish piling up in the entrance.",
        "street": "Cunsdorfer Weg",
        "house_number": "9",
        "offset": (0.0248, 0.0171),
        "damage": [DamageType.VEGETATION, DamageType.WASTE],
        "contact_name": "",
        "contact_email": "",
        "wants_feedback": False,
    },
]

BADGES = [
    ("erste-meldung", "First report", "A first report that led somewhere.", 5, 0, 0),
    ("verlaesslich", "Reliable", "Three reports confirmed on site.", 0, 3, 0),
    ("vor-ort", "On site", "Five verifications carried out.", 0, 0, 5),
]


def rectangle(longitude, latitude, width=0.010, height=0.008):
    """A synthetic rectangle around a point, standing in for real geometry."""
    half_w, half_h = width / 2, height / 2
    return Polygon(
        (
            (longitude - half_w, latitude - half_h),
            (longitude + half_w, latitude - half_h),
            (longitude + half_w, latitude + half_h),
            (longitude - half_w, latitude + half_h),
            (longitude - half_w, latitude - half_h),
        )
    )


class Command(BaseCommand):
    help = "Create a demonstration instance for the Reichenbach proof of concept."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even with DEBUG off. The accounts have known passwords.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the existing demonstration tenant first.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "This creates accounts with a known password. Run it with DEBUG on, "
                "or pass --force if you really want demonstration data here."
            )

        if options["reset"]:
            deleted = Organization.objects.filter(name=MUNICIPALITY_NAME).delete()
            self.stdout.write(f"Removed the previous demonstration data ({deleted[0]} rows).")

        with transaction.atomic():
            municipality = self._municipality()
            districts = self._districts(municipality)
            staff = self._staff(municipality)
            self._geodata(municipality, districts)
            self._parcels(municipality)
            records = self._records(municipality, districts, staff)
            self._heritage(municipality, records, staff)
            self._owners(municipality, records)
            self._documents(municipality, records, staff)
            self._inspections(municipality, records, staff)
            self._reports(municipality, staff)
            self._tasks(municipality, records, staff)
            self._badges()
            self._context(municipality)
            take_snapshot(municipality.organization)

        self._summary(municipality)

    # --- Building blocks --------------------------------------------------
    def _municipality(self):
        organization, _created = Organization.objects.get_or_create(name=MUNICIPALITY_NAME)
        municipality, _created = Municipality.objects.update_or_create(
            organization=organization,
            defaults={
                "name": MUNICIPALITY_NAME,
                "official_name": f"Stadt {MUNICIPALITY_NAME}",
                "municipality_key": MUNICIPALITY_KEY,
                "state": "SN",
                "district_name": "Vogtlandkreis",
                "contact_email": "leerstand@example.org",
                "website": "https://www.example.org",
                "centre": Point(*CENTRE, srid=4326),
                "default_zoom": 15,
                "primary_colour": "#1d4ed8",
                "accent_colour": "#0f766e",
                "boundary": MultiPolygon(rectangle(*CENTRE, width=0.12, height=0.10)),
                "public_intro": (
                    "Melden Sie leerstehende oder vernachlässigte Gebäude in "
                    "Reichenbach im Vogtland. Jede Meldung wird von der Verwaltung "
                    "geprüft."
                ),
                "imprint": (
                    "Demonstration data. Replace with the provider identification "
                    "of the municipality actually running this instance."
                ),
                "privacy_notice": (
                    "Demonstration data. Replace with the privacy notice of the "
                    "municipality actually running this instance."
                ),
            },
        )
        return municipality

    def _districts(self, municipality):
        districts = {}
        longitude, latitude = CENTRE
        for name, kind, (dx, dy) in DISTRICTS:
            centre = Point(longitude + dx, latitude + dy, srid=4326)
            district, _created = District.objects.update_or_create(
                municipality=municipality,
                name=name,
                defaults={
                    "kind": kind,
                    "centre": centre,
                    "boundary": MultiPolygon(rectangle(centre.x, centre.y)),
                    "note": "Illustrative boundary, not surveyed geometry.",
                },
            )
            districts[name] = district
        return districts

    def _staff(self, municipality):
        people = {}
        for username, role, label in STAFF:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.org",
                    "first_name": label.split()[0],
                    "last_name": "Demo",
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
            # Email verification is mandatory, so an unverified demonstration
            # account cannot be signed into without a working mail server. Mark
            # these as verified, or the demonstration is unusable offline.
            EmailAddress.objects.update_or_create(
                user=user,
                email=user.email,
                defaults={"verified": True, "primary": True},
            )
            municipality.organization.add_member(user, role=role)
            people[role] = user
        return people

    def _geodata(self, municipality, districts):
        longitude, latitude = CENTRE
        layers = [
            (
                "sanierungsgebiet-innenstadt",
                "Redevelopment area town centre",
                LayerCategory.REDEVELOPMENT,
                rectangle(longitude, latitude, width=0.020, height=0.016),
            ),
            (
                "denkmalbereich-altstadt",
                "Heritage area old town",
                LayerCategory.HERITAGE,
                rectangle(longitude - 0.002, latitude + 0.001, width=0.012, height=0.010),
            ),
            (
                "foerdergebiet-stadtumbau",
                "Urban restructuring funding area",
                LayerCategory.FUNDING,
                rectangle(longitude + 0.010, latitude - 0.005, width=0.014, height=0.012),
            ),
        ]
        for slug, name, category, polygon in layers:
            layer, _created = GeoLayer.objects.update_or_create(
                organization=municipality.organization,
                slug=slug,
                defaults={
                    "name": name,
                    "category": category,
                    "source": "Demonstration data, not official geodata",
                    "is_public": category != LayerCategory.HERITAGE,
                    "imported_at": timezone.now(),
                },
            )
            layer.features.all().delete()
            GeoFeature.objects.create(
                layer=layer, name=name, geometry=MultiPolygon(polygon)
            )

    def _parcels(self, municipality):
        for number in ("112/3", "112/4", "208/1"):
            Parcel.objects.update_or_create(
                organization=municipality.organization,
                cadastral_district="Reichenbach",
                field_number="4",
                parcel_number=number,
                defaults={
                    "source": ParcelSource.MANUAL,
                    "area_sqm": 640,
                    "note": "Demonstration data.",
                },
            )

    def _records(self, municipality, districts, staff):
        longitude, latitude = CENTRE
        actor = staff[Role.BUILDING_AUTHORITY]
        records = []
        for entry in OBJECTS:
            dx, dy = entry["offset"]
            record, created = Property.objects.get_or_create(
                organization=municipality.organization,
                street=entry["street"],
                house_number=entry["house_number"],
                defaults={
                    "district": districts.get(entry["district"]),
                    "postal_code": "08468",
                    "city": MUNICIPALITY_NAME,
                    "address_note": entry.get("address_note", ""),
                    "location": Point(longitude + dx, latitude + dy, srid=4326),
                    "property_type": entry["property_type"],
                    "last_known_use": entry["last_known_use"],
                    "condition": entry["condition"],
                    "condition_source": entry["condition_source"],
                    "priority": entry["priority"],
                    "public_description": entry["public"],
                    "internal_description": entry["internal"],
                    "sources": "Demonstration data",
                    "is_public": entry["is_public"],
                    "year_built": entry.get("year_built"),
                    "units_total": entry.get("units_total"),
                    "units_vacant": entry.get("units_vacant"),
                    "is_heritage_protected": entry.get("heritage", False),
                    "created_by": actor,
                },
            )
            if created:
                self._walk_to(record, entry["status"], actor)
                record.set_vacancy_status(
                    entry["vacancy_status"], actor=actor, source="Demonstration data"
                )
                for damage in entry["damages"]:
                    record.mark_damage(damage, source=entry["condition_source"])
            records.append(record)
        return records

    def _walk_to(self, record, target, actor):
        """Move a record to its demonstration status through allowed steps only."""
        route = {
            RecordStatus.NEW: [],
            RecordStatus.PRE_CHECK: [RecordStatus.PRE_CHECK],
            RecordStatus.ON_SITE_CHECK: [RecordStatus.PRE_CHECK, RecordStatus.ON_SITE_CHECK],
            RecordStatus.CONFIRMED: [
                RecordStatus.PRE_CHECK,
                RecordStatus.ON_SITE_CHECK,
                RecordStatus.CONFIRMED,
            ],
            RecordStatus.NOT_CONFIRMED: [
                RecordStatus.PRE_CHECK,
                RecordStatus.NOT_CONFIRMED,
            ],
            RecordStatus.RESEARCH: [
                RecordStatus.PRE_CHECK,
                RecordStatus.ON_SITE_CHECK,
                RecordStatus.CONFIRMED,
                RecordStatus.RESEARCH,
            ],
            RecordStatus.MONITORING: [
                RecordStatus.PRE_CHECK,
                RecordStatus.ON_SITE_CHECK,
                RecordStatus.CONFIRMED,
                RecordStatus.MONITORING,
            ],
        }
        for status in route.get(target, []):
            record.transition_to(status, actor=actor, reason="Demonstration data")

    def _heritage(self, municipality, records, staff):
        listed = next((r for r in records if r.is_heritage_protected), None)
        if listed is None:
            return
        monument, _created = MonumentRecord.objects.update_or_create(
            organization=municipality.organization,
            designation="Weberhaus Weberstraße 3",
            defaults={
                "property": listed,
                "monument_id": "09300000",
                "scope": ProtectionScope.SINGLE,
                "authority": "Untere Denkmalschutzbehörde Vogtlandkreis",
                "listed_on": datetime.date(1994, 5, 12),
                "description": "Demonstration data.",
            },
        )
        HeritageCheck.objects.get_or_create(
            organization=municipality.organization,
            property=listed,
            result=CheckResult.PROTECTED,
            defaults={
                "monument": monument,
                "checked_by": staff[Role.HERITAGE_AUTHORITY],
                "authority_reference": "DEMO/2026/001",
                "note": "Demonstration data.",
            },
        )

    def _owners(self, municipality, records):
        target = next((r for r in records if r.street == "Bahnhofstraße"), None)
        if target is None:
            return
        owner, _created = Owner.objects.update_or_create(
            organization=municipality.organization,
            name="Erbengemeinschaft Muster",
            defaults={
                "kind": OwnerKind.COMMUNITY_OF_HEIRS,
                "contact_state": ContactState.UNREACHABLE,
                "representative": "unbekannt",
                "note": "Demonstration data. Internal only.",
            },
        )
        Ownership.objects.get_or_create(
            organization=municipality.organization,
            property=target,
            owner=owner,
            defaults={"share": "unklar", "source": "Demonstration data"},
        )

    def _documents(self, municipality, records, staff):
        from django.core.files.base import ContentFile

        target = records[0]
        if target.documents.exists():
            return
        internal = PropertyDocument(
            organization=municipality.organization,
            property=target,
            title="Gutachten Tragwerk 2025",
            kind=DocumentKind.EXPERT_REPORT,
            description="Demonstration data. Cannot be published.",
            visibility=Visibility.INTERNAL,
            uploaded_by=staff[Role.BUILDING_AUTHORITY],
        )
        internal.file.save(
            "gutachten-demo.txt",
            ContentFile(b"Demonstration document. Internal only."),
            save=False,
        )
        internal.save()

        public = PropertyDocument(
            organization=municipality.organization,
            property=target,
            title="Straßenansicht",
            kind=DocumentKind.PHOTO,
            description="Demonstration data.",
            visibility=Visibility.PUBLIC,
            uploaded_by=staff[Role.BUILDING_AUTHORITY],
        )
        public.file.save(
            "ansicht-demo.txt", ContentFile(b"Demonstration photograph."), save=False
        )
        public.save()

    def _inspections(self, municipality, records, staff):
        target = next((r for r in records if r.street == "Färbergasse"), None)
        if target is None or target.inspections.exists():
            return
        inspection = Inspection.objects.create(
            organization=municipality.organization,
            property=target,
            kind=InspectionKind.ON_SITE,
            result=InspectionResult.UNCLEAR,
            inspected_on=timezone.localdate() - datetime.timedelta(days=6),
            inspector=staff[Role.VERIFIED_CONTRIBUTOR],
            inspector_role=Role.VERIFIED_CONTRIBUTOR,
            observed_vacancy_status=VacancyStatus.SUSPECTED_VACANT,
            observed_condition=ConditionGrade.MAJOR_REPAIR,
            observed_damage=[DamageType.VEGETATION.value],
            findings="Demonstration data: nothing visible from the street.",
        )
        inspection.apply_to_property()

    def _reports(self, municipality, staff):
        longitude, latitude = CENTRE
        for entry in PENDING_REPORTS:
            dx, dy = entry["offset"]
            Report.objects.get_or_create(
                organization=municipality.organization,
                street=entry["street"],
                house_number=entry["house_number"],
                defaults={
                    "category": entry["category"],
                    "description": entry["description"],
                    "postal_code": "08468",
                    "city": MUNICIPALITY_NAME,
                    "location": Point(longitude + dx, latitude + dy, srid=4326),
                    "damage_types": [d.value for d in entry["damage"]],
                    "contact_name": entry["contact_name"],
                    "contact_email": entry["contact_email"],
                    "wants_feedback": entry["wants_feedback"],
                    "accepted_privacy_policy": True,
                    "accepted_terms": True,
                    "consent_given_at": timezone.now(),
                    "status": ReportStatus.SUBMITTED,
                },
            )

        # One report already turned into a record, so the chain is visible.
        accepted, created = Report.objects.get_or_create(
            organization=municipality.organization,
            street="Färbergasse",
            house_number="8",
            defaults={
                "category": ReportCategory.SUSPECTED_VACANCY,
                "description": "Workshop looks abandoned, yard overgrown.",
                "postal_code": "08468",
                "city": MUNICIPALITY_NAME,
                "location": Point(longitude - 0.0011, latitude - 0.0019, srid=4326),
                "damage_types": [DamageType.VEGETATION.value],
                "accepted_privacy_policy": True,
                "accepted_terms": True,
                "consent_given_at": timezone.now(),
            },
        )
        if created and accepted.property_id is None:
            existing = Property.objects.filter(
                organization=municipality.organization, street="Färbergasse"
            ).first()
            if existing is not None:
                from apps.reports.services import attach_report_to_property

                attach_report_to_property(
                    accepted, existing, actor=staff[Role.BUILDING_AUTHORITY]
                )
            else:
                create_property_from_report(
                    accepted, actor=staff[Role.BUILDING_AUTHORITY]
                )

    def _tasks(self, municipality, records, staff):
        if Task.objects.filter(organization=municipality.organization).exists():
            return
        today = timezone.localdate()
        specs = [
            (TaskType.CLARIFY_OWNERSHIP, records[0], Role.PROPERTY_MANAGEMENT, 14),
            (TaskType.ON_SITE_APPOINTMENT, records[3], Role.BUILDING_AUTHORITY, 3),
            (TaskType.VERIFY_HERITAGE, records[2], Role.HERITAGE_AUTHORITY, -2),
            (TaskType.UPDATE_PHOTO, records[4], Role.VERIFIED_CONTRIBUTOR, 21),
        ]
        for task_type, record, role, offset_days in specs:
            Task.objects.create(
                organization=municipality.organization,
                task_type=task_type,
                property=record,
                assignee=staff.get(role),
                due_on=today + datetime.timedelta(days=offset_days),
                priority=Priority.HIGH if offset_days < 0 else Priority.MEDIUM,
                description="Demonstration data.",
                created_by=staff[Role.OWNER],
            )

    def _badges(self):
        for key, name, description, points, confirmed, inspections in BADGES:
            Badge.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "description": description,
                    "required_points": points,
                    "required_confirmed_reports": confirmed,
                    "required_inspections": inspections,
                },
            )

    def _context(self, municipality):
        for record in Property.objects.filter(organization=municipality.organization):
            refresh_context(record)

    def _summary(self, municipality):
        organization = municipality.organization
        counts = {
            "districts": municipality.districts.count(),
            "records": Property.objects.filter(organization=organization).count(),
            "reports": Report.objects.filter(organization=organization).count(),
            "geodata layers": GeoLayer.objects.filter(organization=organization).count(),
            "tasks": Task.objects.filter(organization=organization).count(),
        }
        self.stdout.write(self.style.SUCCESS(f"Demonstration instance for {municipality.name}:"))
        for label, count in counts.items():
            self.stdout.write(f"  {count} {label}")
        self.stdout.write("")
        self.stdout.write("Accounts, all with the password:")
        self.stdout.write(self.style.WARNING(f"  {DEMO_PASSWORD}"))
        for username, role, label in STAFF:
            self.stdout.write(f"  {username:24} {label} ({role})")
        self.stdout.write("")
        self.stdout.write(
            "Districts, boundaries, objects, reports and owners are illustrative. "
            "Replace them with imported geodata and real records."
        )
