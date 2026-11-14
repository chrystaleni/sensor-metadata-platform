from django.contrib.gis.geos import GEOSException, LineString, Point, Polygon
from django.db import IntegrityError, transaction
from django.db.models import Q, Value
from django.db.models.functions import Lower
from rest_framework import serializers
from rest_framework.utils import json

from .models import (
    NETWORK_GEOMETRY_TYPES,
    ExternalIdentifier,
    Measurement,
    MeasurementType,
    MeasurementUnit,
    NetworkElement,
    NetworkElementType,
    PhysicalDevice,
    PhysicalDeviceType,
)


MAX_ID = 2**63 - 1
RECORD_FIELDS = (
    "id", "department", "name", "description", "created_at", "updated_at", "created_by", "updated_by", "is_active",
)


def position(coordinates):
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError
    lon, lat = coordinates
    if type(lon) not in (int, float) or type(lat) not in (int, float):
        raise ValueError
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError
    return lon, lat


def positions(coordinates, minimum):
    if not isinstance(coordinates, list) or len(coordinates) < minimum:
        raise ValueError
    return [position(item) for item in coordinates]


class GeoJSONField(serializers.Field):
    def __init__(self, allowed_types, **kwargs):
        self.allowed_types = allowed_types
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or data.get("type") not in self.allowed_types or "crs" in data:
            allowed = ", ".join(self.allowed_types)
            raise serializers.ValidationError(f"Expected WGS84 GeoJSON geometry of type {allowed}.")

        try:
            coordinates = data["coordinates"]
            if data["type"] == "Point":
                geometry = Point(*position(coordinates), srid=4326)
            elif data["type"] == "LineString":
                geometry = LineString(positions(coordinates, 2), srid=4326)
            else:
                if not isinstance(coordinates, list) or not coordinates:
                    raise ValueError
                rings = [positions(ring, 4) for ring in coordinates]
                if any(ring[0] != ring[-1] for ring in rings):
                    raise ValueError
                geometry = Polygon(*rings, srid=4326)

            if geometry.empty or not geometry.valid:
                raise ValueError
        except (GEOSException, KeyError, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError(
                "Provide valid two-dimensional longitude and latitude coordinates in WGS84."
            ) from None
        return geometry

    def to_representation(self, value):
        return json.loads(value.geojson)


class CollectionSettingsSerializer(serializers.Serializer):
    protocol = serializers.CharField(max_length=50, required=False, allow_blank=True)
    endpoint = serializers.CharField(max_length=2048, required=False, allow_blank=True)
    source_identifier = serializers.CharField(max_length=255, required=False, allow_blank=True)
    extra_settings = serializers.JSONField(required=False)

    def validate_extra_settings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        return value


class CollectionConfigField(serializers.JSONField):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        settings = CollectionSettingsSerializer(data=data)
        settings.is_valid(raise_exception=True)
        data = {**data, **settings.validated_data}
        try:
            json.dumps(data, ensure_ascii=False).encode("utf-8")
        except (ValueError, TypeError, RecursionError):
            raise serializers.ValidationError("Expected a valid UTF-8 JSON object.") from None

        nodes = [data]
        while nodes:
            node = nodes.pop()
            if isinstance(node, dict):
                nodes.extend(node.keys())
                nodes.extend(node.values())
            elif isinstance(node, list):
                nodes.extend(node)
            elif isinstance(node, str) and "\x00" in node:
                raise serializers.ValidationError("JSON strings cannot contain null characters.")
        return data


class DepartmentSelectionSerializer(serializers.Serializer):
    department = serializers.IntegerField(min_value=1, max_value=MAX_ID)


class RecordSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    def get_is_active(self, instance):
        return instance.deleted_at is None


class ControlledListSerializer(RecordSerializer):
    department = serializers.IntegerField(source="department_id", read_only=True)

    class Meta:
        fields = RECORD_FIELDS
        read_only_fields = ("created_by", "updated_by")

    def validate_name(self, value):
        names = self.Meta.model.objects.active().filter(department_id=self.context["department_id"])
        if self.instance is not None:
            names = names.exclude(pk=self.instance.pk)
        if names.alias(lower_name=Lower("name")).filter(lower_name=Lower(Value(value))).exists():
            raise serializers.ValidationError("An active entry already has this name.")
        return value


class MeasurementTypeSerializer(ControlledListSerializer):
    class Meta(ControlledListSerializer.Meta):
        model = MeasurementType


class MeasurementUnitSerializer(ControlledListSerializer):
    class Meta(ControlledListSerializer.Meta):
        model = MeasurementUnit
        fields = (*RECORD_FIELDS, "symbol")


class PhysicalDeviceTypeSerializer(ControlledListSerializer):
    class Meta(ControlledListSerializer.Meta):
        model = PhysicalDeviceType


class NetworkElementTypeSerializer(ControlledListSerializer):
    class Meta(ControlledListSerializer.Meta):
        model = NetworkElementType


class OperationalSerializer(RecordSerializer):
    department = serializers.IntegerField(source="department_id", min_value=1, max_value=MAX_ID, required=False)
    platform_relationships = ()
    department_relationships = ()

    def get_fields(self):
        fields = super().get_fields()
        for relationship in self.platform_relationships:
            field = fields[relationship]
            field.pk_field = serializers.IntegerField(min_value=1, max_value=MAX_ID)
            field.queryset = field.queryset.active().filter(
                department_id=self.context.get("platform_department_id")
            )
        for relationship in self.department_relationships:
            field = fields[relationship]
            field.pk_field = serializers.IntegerField(min_value=1, max_value=MAX_ID)
            field.queryset = field.queryset.active().filter(department_id=self.context.get("department_id"))
        return fields

    def validate_department(self, value):
        if value != self.context.get("department_id"):
            raise serializers.ValidationError("The department is fixed when the record is created.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            errors = {}
            for name in (*self.platform_relationships, *self.department_relationships):
                if name not in attrs:
                    pk = getattr(self.instance, f"{name}_id")
                    if not self.fields[name].queryset.filter(pk=pk).exists():
                        errors[name] = ["Choose an active record in the permitted department."]
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    class Meta:
        read_only_fields = ("created_by", "updated_by")


class PhysicalDeviceSerializer(OperationalSerializer):
    location = GeoJSONField(("Point",), required=False, allow_null=True)
    platform_relationships = ("device_type",)

    class Meta(OperationalSerializer.Meta):
        model = PhysicalDevice
        fields = (*RECORD_FIELDS, "device_type", "location")


class ExternalIdentifierSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        # Supplied list items are complete replacements, even on a parent PATCH.
        missing = {
            name: [self.fields[name].error_messages["required"]]
            for name in ("source", "value") if name not in attrs
        }
        if missing:
            raise serializers.ValidationError(missing, code="required")
        return attrs

    class Meta:
        model = ExternalIdentifier
        fields = ("id", "source", "value")
        # The parent validates the complete replacement list and excludes its
        # existing identifiers, so retaining an unchanged pair remains valid.
        validators = []


class NetworkElementSerializer(OperationalSerializer):
    geometry = GeoJSONField(NETWORK_GEOMETRY_TYPES, required=False, allow_null=True)
    external_identifiers = ExternalIdentifierSerializer(
        source="active_external_identifiers", many=True, required=False, max_length=100
    )
    platform_relationships = ("element_type",)

    class Meta(OperationalSerializer.Meta):
        model = NetworkElement
        fields = (
            *RECORD_FIELDS, "element_type", "geometry", "external_identifiers", "dma_model_id", "strategic_model_id",
        )

    def validate_external_identifiers(self, identifiers):
        pairs = {(item["source"], item["value"]) for item in identifiers}
        if len(pairs) != len(identifiers):
            raise serializers.ValidationError("Each source and value pair must be unique.")
        if pairs:
            matching = Q()
            for source, value in pairs:
                matching |= Q(source=source, value=value)
            existing = ExternalIdentifier.objects.active().filter(
                matching, department_id=self.context["department_id"],
            )
            if self.instance is not None:
                existing = existing.exclude(network_element_id=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    "An active identifier with this source and value already exists."
                )
        return identifiers

    def create(self, validated_data):
        identifiers = validated_data.pop("active_external_identifiers", [])
        element = super().create(validated_data)
        self.save_identifiers(element, identifiers)
        return element

    def update(self, instance, validated_data):
        identifiers = validated_data.pop("active_external_identifiers", None)
        element = super().update(instance, validated_data)
        if identifiers is not None:
            self.save_identifiers(element, identifiers)
        return element

    def save_identifiers(self, element, identifiers):
        active = element.external_identifiers.active()
        existing = {(item.source, item.value): item.pk for item in active}
        incoming = {(item["source"], item["value"]): item for item in identifiers}

        retired = [pk for pair, pk in existing.items() if pair not in incoming]
        if retired:
            active.filter(pk__in=retired).archive(self.context["request"].user)

        additions = [
            ExternalIdentifier(
                network_element=element, department_id=element.department_id,
                created_by=self.context["request"].user,
                updated_by=self.context["request"].user, **item,
            )
            for pair, item in incoming.items()
            if pair not in existing
        ]
        try:
            with transaction.atomic():
                ExternalIdentifier.objects.bulk_create(additions)
        except IntegrityError as error:
            # A direct writer in this Department can claim a pair after
            # validation. Preserve the constraint and return a field error.
            diagnostic = getattr(error.__cause__, "diag", None)
            if getattr(diagnostic, "constraint_name", None) != "meta_active_dept_external_identifier":
                raise
            raise serializers.ValidationError({
                "external_identifiers": ["An active identifier with this source and value already exists."]
            }) from error


class MeasurementSerializer(OperationalSerializer):
    data_collection_config = CollectionConfigField(required=False, allow_null=True)
    department_relationships = ("physical_device", "network_element")
    platform_relationships = ("measurement_type", "measurement_unit")

    class Meta(OperationalSerializer.Meta):
        model = Measurement
        fields = (
            *RECORD_FIELDS,
            "physical_device",
            "network_element",
            "measurement_type",
            "measurement_unit",
            "data_collection_config",
            "customer_account",
            "meter_account",
        )
