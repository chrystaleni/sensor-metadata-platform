"""User and Department management API (Phase 2 design, Table 4).

System Administrators manage every user and Department. Department
Administrators manage Viewer/Editor users inside Departments they administer.
All other roles, API keys and anonymous callers are refused. The configured
access policy stays authoritative, so the default ``NoAccessPolicy`` denies.
"""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api_keys.authentication import KeyAwareSessionAuthentication
from api_keys.permissions import managed_departments
from local_departments.models import Department, Organisation
from metadata.access import get_access_policy
from metadata.filters import MetadataPagination

from .models import UserDepartment, UserRole

Role = UserRole.Role
MIN_PASSWORD_LENGTH = 12


def _principal(request):
    return SimpleNamespace(user=request.user, auth=None)


def acting_role(request):
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return None
    return UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True).first()


def is_system_admin(request):
    return acting_role(request) == Role.SYSTEM_ADMIN and bool(
        get_access_policy().can_manage_controlled_lists(_principal(request))
    )


def administered_department_ids(request):
    """Department IDs the caller may administer; ``None`` means every Department."""
    if is_system_admin(request):
        return None
    if acting_role(request) == Role.DEPARTMENT_ADMIN:
        return set(managed_departments(request.user).values_list("pk", flat=True))
    return set()


class DepartmentSerializer(serializers.ModelSerializer):
    organisation = serializers.PrimaryKeyRelatedField(queryset=Organisation.objects.all())
    organisation_code = serializers.CharField(source="organisation.code", read_only=True)

    class Meta:
        model = Department
        fields = ("id", "name", "organisation", "organisation_code")
        read_only_fields = ("id",)


class DepartmentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet,
):
    """GET lists readable Departments; POST (System Administrator) creates one."""

    authentication_classes = (KeyAwareSessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = DepartmentSerializer
    pagination_class = MetadataPagination

    def get_queryset(self):
        readable = get_access_policy().readable_department_ids(_principal(self.request))
        return Department.objects.select_related("organisation").filter(pk__in=readable).order_by("id")

    def create(self, request, *args, **kwargs):
        if not is_system_admin(request):
            raise PermissionDenied("System Administrator access is required.")
        return super().create(request, *args, **kwargs)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=Role.choices)
    departments = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Department.objects.all(), required=False,
    )
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=128)

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "is_active", "role", "departments", "password")
        read_only_fields = ("id",)

    def to_representation(self, instance):
        scope = self.context["administered"]
        memberships = UserDepartment.objects.filter(user_id=instance.pk)
        if scope is not None:  # Department Administrators only see their own Departments.
            memberships = memberships.filter(department_id__in=scope)
        return {
            "id": instance.pk,
            "username": instance.get_username(),
            "is_active": instance.is_active,
            "role": UserRole.objects.filter(user_id=instance.pk).values_list("role", flat=True).first(),
            "departments": sorted(memberships.values_list("department_id", flat=True)),
        }

    def validate_password(self, value):
        if len(value) < MIN_PASSWORD_LENGTH:
            raise serializers.ValidationError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
        if "\x00" in value:
            raise serializers.ValidationError("Invalid password.")
        candidate = self.instance or get_user_model()(username=self.initial_data.get("username", ""))
        try:
            validate_password(value, candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages)) from error
        return value

    def validate(self, attrs):
        scope = self.context["administered"]
        if self.instance is None and "password" not in attrs:
            raise serializers.ValidationError({"password": "This field is required."})
        if self.instance is None and "role" not in attrs:
            raise serializers.ValidationError({"role": "This field is required."})
        if scope is not None:
            role = attrs.get("role")
            if role is not None and role not in (Role.VIEWER, Role.EDITOR):
                raise serializers.ValidationError(
                    {"role": "Department Administrators may assign only Viewer or Editor."}
                )
            requested = {d.pk for d in attrs.get("departments", [])}
            if not requested <= scope:
                raise serializers.ValidationError(
                    {"departments": "Choose only Departments you administer."}
                )
            if self.instance is None and not requested:
                raise serializers.ValidationError({"departments": "Assign at least one Department."})
        return attrs


class UserViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """Manage users. DELETE deactivates (logical deletion); PUT is not offered."""

    authentication_classes = (KeyAwareSessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer
    pagination_class = MetadataPagination
    http_method_names = ("get", "post", "patch", "delete", "head", "options")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.administered = administered_department_ids(request)
        if self.administered is not None and not self.administered:
            raise PermissionDenied("Department or System Administrator access is required.")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["administered"] = getattr(self, "administered", set())
        return context

    def get_queryset(self):
        users = get_user_model().objects.order_by("id")
        if self.administered is None:
            return users
        in_scope = UserDepartment.objects.filter(department_id__in=self.administered).values("user_id")
        # Department Administrators manage only Viewer/Editor accounts in their Departments.
        return users.filter(pk__in=in_scope).exclude(
            platform_role__role__in=(Role.SYSTEM_ADMIN, Role.DEPARTMENT_ADMIN)
        )

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        user = get_user_model().objects.create_user(
            username=data["username"], password=data["password"], is_active=data.get("is_active", True),
        )
        UserRole.objects.create(user=user, role=data["role"])
        UserDepartment.objects.bulk_create(
            [UserDepartment(user=user, department=d) for d in data.get("departments", [])]
        )
        serializer.instance = user

    @transaction.atomic
    def perform_update(self, serializer):
        user, data = serializer.instance, serializer.validated_data
        is_self = user.pk == self.request.user.pk
        if is_self and ("role" in data or data.get("is_active") is False):
            raise PermissionDenied("You cannot change your own role or deactivate yourself.")
        if "username" in data:
            user.username = data["username"]
        if "is_active" in data:
            user.is_active = data["is_active"]
        if "password" in data:
            user.set_password(data["password"])
        user.save()
        if "role" in data:
            UserRole.objects.update_or_create(user=user, defaults={"role": data["role"]})
        if "departments" in data:
            wanted = {d.pk for d in data["departments"]}
            current = UserDepartment.objects.filter(user=user)
            if self.administered is not None:  # Preserve memberships outside the caller's scope.
                current = current.filter(department_id__in=self.administered)
            current.exclude(department_id__in=wanted).delete()
            existing = set(UserDepartment.objects.filter(user=user).values_list("department_id", flat=True))
            UserDepartment.objects.bulk_create(
                [UserDepartment(user=user, department_id=pk) for pk in wanted - existing]
            )

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise PermissionDenied("You cannot deactivate yourself.")
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ("id", "name", "code")
        read_only_fields = ("id",)

    def validate_code(self, value):
        if not value.replace("-", "").replace("_", "").isalnum() or value != value.lower():
            raise serializers.ValidationError("Use lowercase letters, digits, hyphens or underscores.")
        return value


class OrganisationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet,
):
    """GET lists Organisations the caller can see; POST (System Administrator) creates one."""

    authentication_classes = (KeyAwareSessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = OrganisationSerializer
    pagination_class = MetadataPagination

    def get_queryset(self):
        if is_system_admin(self.request):
            return Organisation.objects.order_by("id")
        readable = get_access_policy().readable_department_ids(_principal(self.request))
        return Organisation.objects.filter(departments__in=readable).distinct().order_by("id")

    def create(self, request, *args, **kwargs):
        if not is_system_admin(request):
            raise PermissionDenied("System Administrator access is required.")
        return super().create(request, *args, **kwargs)
