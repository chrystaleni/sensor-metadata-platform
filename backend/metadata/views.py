from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework import filters, serializers, viewsets
from rest_framework.exceptions import APIException, PermissionDenied
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


class OperationalViewSet(MetadataViewSet):
    def get_queryset(self):
        scope = Q(department_id__in=self.access_policy.readable_department_ids(self.request))
        if self.is_write:
            scope |= Q(department_id__in=self.access_policy.writable_department_ids(self.request))
        return self.active_records().filter(scope)

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
        return queryset

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
