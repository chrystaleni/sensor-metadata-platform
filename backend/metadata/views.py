from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework import filters, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS

from .access import get_access_policy
from .filters import MetadataFilter, MetadataPagination, NetworkElementSearchFilter, StableOrderingFilter
from .models import ExternalIdentifier
from .platform import configured_platform_department_id
from .serializers import (
    DepartmentSelectionSerializer,
    MeasurementSerializer,
    MeasurementTypeSerializer,
    MeasurementUnitSerializer,
    NetworkElementSerializer,
    NetworkElementTypeSerializer,
    PhysicalDeviceSerializer,
    PhysicalDeviceTypeSerializer,
)
from .writes import lock_metadata_write


class ActiveDependencyConflict(APIException):
    status_code = 409
    default_detail = "Archive the active records that reference this record first."
    default_code = "active_dependencies"


class ArchiveConflict(APIException):
    status_code = 409
    default_detail = "This archived record cannot be changed."
    default_code = "archive_conflict"


# Related records that must be active before a record can be restored.
RESTORE_REQUIREMENTS = (
    ("device_type", "device type"),
    ("element_type", "element type"),
    ("physical_device", "physical device"),
    ("network_element", "network element"),
    ("measurement_type", "measurement type"),
    ("measurement_unit", "measurement unit"),
)


class DepartmentScope:
    permission_classes = (IsAuthenticated,)

    @cached_property
    def access_policy(self):
        return get_access_policy()

    @cached_property
    def platform_department_id(self):
        return configured_platform_department_id()

    def require_writable_department(self, department_id):
        if department_id not in self.access_policy.writable_department_ids(self.request):
            raise PermissionDenied("You do not have write access to this department.")


class MetadataViewSet(DepartmentScope, viewsets.ModelViewSet):
    filter_backends = (MetadataFilter, filters.SearchFilter, StableOrderingFilter)
    pagination_class = MetadataPagination
    search_fields = ("name", "description")
    ordering_fields = ("id", "name", "created_at", "updated_at")
    ordering = ("id",)
    id_filters = ()
    geometry_field = None
    dependent_relations = ()
    controlled_list = False
    write_department_id = None

    @property
    def is_write(self):
        return self.request.method not in SAFE_METHODS

    def active_records(self):
        return self.serializer_class.Meta.model.objects.active()

    def filter_queryset(self, queryset):
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["department_id"] = self.write_department_id
        context["platform_department_id"] = self.platform_department_id
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        self.write_department_id = self.department_for_create()
        lock_metadata_write(self.write_department_id, controlled_list=self.controlled_list)
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self.write_department_id = self.get_object().department_id
        lock_metadata_write(self.write_department_id, controlled_list=self.controlled_list)
        # The DRF update fetches the active record again after the lock.
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        department_id = self.get_object().department_id
        lock_metadata_write(department_id, controlled_list=self.controlled_list)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            department_id=self.write_department_id, created_by=self.request.user, updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        for relation in self.dependent_relations:
            if getattr(instance, relation).active().exists():
                raise ActiveDependencyConflict
        at = timezone.now()
        self.active_records().filter(pk=instance.pk).archive(self.request.user, at=at)
        return at

    # --- Archived records: only archive managers see, restore and permanently delete them.

    def include_archived(self):
        value = self.request.query_params.get("include_archived")
        if value is None or self.is_write:
            return False
        try:
            return serializers.BooleanField().run_validation(value)
        except serializers.ValidationError as error:
            raise serializers.ValidationError({"include_archived": error.detail}) from error

    def archive_manager_department_ids(self):
        return set(self.access_policy.archive_manager_department_ids(self.request))

    def archived_object(self):
        model = self.serializer_class.Meta.model
        try:
            pk = serializers.IntegerField(min_value=1, max_value=2**63 - 1).run_validation(self.kwargs["pk"])
        except serializers.ValidationError:
            raise NotFound from None
        instance = model.objects.select_for_update().filter(pk=pk, deleted_at__isnull=False).first()
        if instance is None or instance.department_id not in self.archive_manager_department_ids():
            raise NotFound
        return instance

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        with transaction.atomic():
            instance = self.archived_object()
            lock_metadata_write(instance.department_id, controlled_list=self.controlled_list)
            for field, label in RESTORE_REQUIREMENTS:
                related = getattr(instance, field, None)
                if related is not None and related.deleted_at is not None:
                    raise ArchiveConflict(f"Restore the {label} '{related.name}' first.")
            archived_at, now = instance.deleted_at, timezone.now()
            try:
                with transaction.atomic():
                    type(instance).objects.filter(pk=instance.pk).update(
                        deleted_at=None, deleted_by=None, updated_at=now, updated_by=request.user,
                    )
                    self.restore_children(instance, archived_at, now)
            except IntegrityError:
                raise ArchiveConflict(
                    "An active record with the same name or identifier already exists. "
                    "Rename or archive that record first."
                ) from None
        instance.refresh_from_db()
        return Response(self.get_serializer(instance).data)

    def restore_children(self, instance, archived_at, now):
        pass

    @action(detail=True, methods=["delete"])
    def purge(self, request, pk=None):
        with transaction.atomic():
            instance = self.archived_object()
            lock_metadata_write(instance.department_id, controlled_list=self.controlled_list)
            for relation in self.dependent_relations:
                if getattr(instance, relation).exists():
                    raise ArchiveConflict(
                        "Other records still use this one. Permanently delete those archived records first."
                    )
            self.delete_children(instance)
            instance.delete()
        return Response(status=204)

    def delete_children(self, instance):
        pass


class OperationalViewSet(MetadataViewSet):
    def get_queryset(self):
        scope = Q(department_id__in=self.access_policy.readable_department_ids(self.request))
        if self.is_write:
            scope |= Q(department_id__in=self.access_policy.writable_department_ids(self.request))
        records = self.active_records()
        if self.include_archived():
            visible = Q(deleted_at__isnull=True) | Q(department_id__in=self.archive_manager_department_ids())
            records = self.serializer_class.Meta.model.objects.filter(visible)
        return records.filter(scope)

    def get_object(self):
        instance = super().get_object()
        if self.is_write:
            # A known, readable record with no write permission is forbidden;
            # records outside both scopes remain hidden by the queryset.
            self.require_writable_department(instance.department_id)
        return instance

    def department_for_create(self):
        selection = DepartmentSelectionSerializer(data=self.request.data)
        selection.is_valid(raise_exception=True)
        department_id = selection.validated_data["department"]
        self.require_writable_department(department_id)
        return department_id


class ControlledListViewSet(MetadataViewSet):
    controlled_list = True

    def active_records(self):
        queryset = super().active_records()
        include_inactive = self.request.query_params.get("include_inactive")
        if not self.is_write and include_inactive is not None:
            try:
                show_history = serializers.BooleanField().run_validation(include_inactive)
            except serializers.ValidationError as error:
                raise serializers.ValidationError({"include_inactive": error.detail}) from error
            if show_history:
                return self.serializer_class.Meta.model.objects.all()
        if self.include_archived() and self.archive_manager_department_ids():
            return self.serializer_class.Meta.model.objects.all()
        return queryset

    def archive_manager_department_ids(self):
        # The shared lists belong to Platform; only list managers handle their archive.
        if self.platform_department_id is None or not self.access_policy.can_manage_controlled_lists(self.request):
            return set()
        return {self.platform_department_id}

    def department_for_create(self):
        if not self.access_policy.can_manage_controlled_lists(self.request) or self.platform_department_id is None:
            raise PermissionDenied("You do not have write access to the shared lists.")
        return self.platform_department_id

    def get_queryset(self):
        if self.is_write:
            self.department_for_create()
        elif not (
            self.access_policy.can_manage_controlled_lists(self.request)
            or self.access_policy.readable_department_ids(self.request)
        ):
            return self.active_records().none()
        if self.platform_department_id is None:
            raise PermissionDenied("The shared controlled lists are unavailable.")
        return self.active_records().filter(department_id=self.platform_department_id)


class MeasurementTypeViewSet(ControlledListViewSet):
    serializer_class = MeasurementTypeSerializer
    dependent_relations = ("measurements",)


class MeasurementUnitViewSet(ControlledListViewSet):
    serializer_class = MeasurementUnitSerializer
    dependent_relations = ("measurements",)
    search_fields = (*ControlledListViewSet.search_fields, "symbol")


class PhysicalDeviceTypeViewSet(ControlledListViewSet):
    serializer_class = PhysicalDeviceTypeSerializer
    dependent_relations = ("devices",)


class NetworkElementTypeViewSet(ControlledListViewSet):
    serializer_class = NetworkElementTypeSerializer
    dependent_relations = ("elements",)


class PhysicalDeviceViewSet(OperationalViewSet):
    serializer_class = PhysicalDeviceSerializer
    id_filters = ("department", "device_type")
    search_fields = (*OperationalViewSet.search_fields, "device_type__name")
    dependent_relations = ("measurements",)
    geometry_field = "location"


class NetworkElementViewSet(OperationalViewSet):
    serializer_class = NetworkElementSerializer
    filter_backends = (MetadataFilter, NetworkElementSearchFilter, StableOrderingFilter)
    id_filters = ("department", "element_type")
    search_fields = (*OperationalViewSet.search_fields, "element_type__name", "dma_model_id", "strategic_model_id")
    dependent_relations = ("measurements",)
    geometry_field = "geometry"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("list", "retrieve"):
            queryset = queryset.prefetch_related(
                Prefetch(
                    "external_identifiers",
                    queryset=ExternalIdentifier.objects.active(),
                    to_attr="_prefetched_active_identifiers",
                )
            )
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if self.action == "list" and "identifier" in self.request.query_params:
            field = serializers.CharField(max_length=255)
            try:
                value = field.run_validation(self.request.query_params["identifier"])
            except serializers.ValidationError as error:
                raise serializers.ValidationError({"identifier": error.detail}) from error
            match = ExternalIdentifier.objects.active().filter(network_element_id=OuterRef("pk"), value=value)
            queryset = queryset.filter(Exists(match))
        return queryset

    def perform_destroy(self, instance):
        at = super().perform_destroy(instance)
        instance.external_identifiers.archive(self.request.user, at=at)

    def restore_children(self, instance, archived_at, now):
        # Bring back the identifiers that were archived together with the element.
        instance.external_identifiers.filter(deleted_at=archived_at).update(
            deleted_at=None, deleted_by=None, updated_at=now, updated_by=self.request.user,
        )

    def delete_children(self, instance):
        instance.external_identifiers.all().delete()


class MeasurementViewSet(OperationalViewSet):
    serializer_class = MeasurementSerializer
    id_filters = ("department", "physical_device", "network_element", "measurement_type", "measurement_unit")
    search_fields = (
        *OperationalViewSet.search_fields,
        "customer_account",
        "meter_account",
        "physical_device__name",
        "network_element__name",
        "measurement_type__name",
        "measurement_unit__name",
    )

    def get_queryset(self):
        return super().get_queryset().select_related("collection_configuration")

    @action(detail=True, methods=["get"], url_path="configuration")
    def configuration(self, request, pk=None):
        """Read-only Data Collection Configuration of an authorized Measurement."""
        configuration = getattr(self.get_object(), "collection_configuration", None)
        if configuration is None:
            raise NotFound("This Measurement has no Data Collection Configuration.")
        return Response(configuration.config)
