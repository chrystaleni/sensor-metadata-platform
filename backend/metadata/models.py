from django.conf import settings
from django.contrib.gis.db import models
from django.db.models.functions import Lower
from django.db.models.lookups import In
from django.utils import timezone


NETWORK_GEOMETRY_TYPES = ("Point", "LineString", "Polygon")


_UNSET = object()


class MetadataQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def archive(self, actor, at=None):
        at = at or timezone.now()
        self.active().update(deleted_at=at, deleted_by=actor, updated_at=at, updated_by=actor)


class MetadataRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = MetadataQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("id",)


class DepartmentRecord(MetadataRecord):
    department = models.ForeignKey(
        settings.METADATA_DEPARTMENT_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta(MetadataRecord.Meta):
        abstract = True

    def __str__(self):
        return self.name


class ControlledListEntry(DepartmentRecord):
    class Meta(DepartmentRecord.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "department",
                condition=models.Q(deleted_at__isnull=True),
                name="meta_%(class)s_active_name",
            ),
        ]


class MeasurementType(ControlledListEntry):
    pass


class MeasurementUnit(ControlledListEntry):
    symbol = models.CharField(max_length=24, blank=True)


class PhysicalDeviceType(ControlledListEntry):
    pass


class NetworkElementType(ControlledListEntry):
    pass


class PhysicalDevice(DepartmentRecord):
    device_type = models.ForeignKey(PhysicalDeviceType, on_delete=models.PROTECT, related_name="devices")
    location = models.PointField(srid=4326, null=True, blank=True)
    # How external systems reach the device (for example an IP address); free-form JSON object.
    communication_parameters = models.JSONField(null=True, blank=True)

    class Meta(DepartmentRecord.Meta):
        constraints = [
            models.UniqueConstraint(fields=("department", "id"), name="meta_device_department_id"),
        ]


class NetworkElement(DepartmentRecord):
    element_type = models.ForeignKey(NetworkElementType, on_delete=models.PROTECT, related_name="elements")
    geometry = models.GeometryField(srid=4326, null=True, blank=True)
    dma_model_id = models.CharField(max_length=255, blank=True)
    strategic_model_id = models.CharField(max_length=255, blank=True)
    network_area = models.CharField(max_length=255, blank=True)
    elevation = models.FloatField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    class Meta(DepartmentRecord.Meta):
        constraints = [
            models.UniqueConstraint(fields=("department", "id"), name="meta_element_department_id"),
            models.CheckConstraint(
                condition=In(
                    models.Func("geometry", function="ST_GeometryType", output_field=models.CharField()),
                    [f"ST_{kind}" for kind in NETWORK_GEOMETRY_TYPES],
                ),
                name="meta_network_geometry_type",
            ),
        ]

    @property
    def active_external_identifiers(self):
        if hasattr(self, "_prefetched_active_identifiers"):
            return self._prefetched_active_identifiers
        return self.external_identifiers.active()


class ExternalIdentifier(MetadataRecord):
    department = models.ForeignKey(
        settings.METADATA_DEPARTMENT_MODEL, on_delete=models.PROTECT, related_name="+", editable=False,
    )
    network_element = models.ForeignKey(
        NetworkElement, on_delete=models.PROTECT, related_name="external_identifiers"
    )
    source = models.CharField(max_length=120)
    value = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        # Ordinary ORM creation derives ownership from the parent. Bulk writers
        # supply it explicitly; the composite database FK enforces agreement.
        if self.department_id is None and self.network_element_id is not None:
            self.department_id = self.network_element.department_id
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "department"}
        super().save(*args, **kwargs)

    class Meta(MetadataRecord.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=("department", "source", "value"),
                condition=models.Q(deleted_at__isnull=True),
                name="meta_active_dept_external_identifier",
            ),
        ]


class Measurement(DepartmentRecord):
    physical_device = models.ForeignKey(PhysicalDevice, on_delete=models.PROTECT, related_name="measurements")
    network_element = models.ForeignKey(NetworkElement, on_delete=models.PROTECT, related_name="measurements")
    measurement_type = models.ForeignKey(MeasurementType, on_delete=models.PROTECT, related_name="measurements")
    measurement_unit = models.ForeignKey(MeasurementUnit, on_delete=models.PROTECT, related_name="measurements")
    customer_account = models.CharField(max_length=255, blank=True)
    meter_account = models.CharField(max_length=255, blank=True)

    # The Data Collection Configuration is its own entity (DataCollectionConfiguration).
    # This property keeps the established ``data_collection_config`` API/ORM contract:
    # assigning stores the value and ``save()`` persists it (``None`` removes it).
    @property
    def data_collection_config(self):
        pending = self.__dict__.get("_pending_config", _UNSET)
        if pending is not _UNSET:
            return pending
        try:
            return self.collection_configuration.config
        except DataCollectionConfiguration.DoesNotExist:
            return None

    @data_collection_config.setter
    def data_collection_config(self, value):
        self._pending_config = value

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        pending = self.__dict__.pop("_pending_config", _UNSET)
        if pending is _UNSET:
            return
        if pending is None:
            DataCollectionConfiguration.objects.filter(measurement=self).delete()
        else:
            DataCollectionConfiguration.objects.update_or_create(
                measurement=self,
                defaults={"config": pending, "department_id": self.department_id, "updated_by_id": self.updated_by_id},
                create_defaults={
                    "config": pending, "department_id": self.department_id,
                    "created_by_id": self.created_by_id, "updated_by_id": self.updated_by_id,
                },
            )
        self._state.fields_cache.pop("collection_configuration", None)


class DataCollectionConfiguration(models.Model):
    """External data-collection settings of one Measurement (Phase 2 design, Table 2)."""

    measurement = models.OneToOneField(
        Measurement, on_delete=models.CASCADE, related_name="collection_configuration"
    )
    department = models.ForeignKey(
        settings.METADATA_DEPARTMENT_MODEL, on_delete=models.PROTECT, related_name="+", editable=False,
    )
    config = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return f"Configuration of {self.measurement_id}"
