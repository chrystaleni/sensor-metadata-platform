from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from .authentication import KeyAwareSessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from metadata.filters import MetadataPagination
from .models import APIKey
from .permissions import managed_departments


class APIKeySerializer(serializers.ModelSerializer):
    department = serializers.IntegerField(source="department_id", min_value=1, max_value=2**63 - 1)
    expires_at = serializers.DateTimeField(default=lambda: timezone.now() + timedelta(days=90))

    class Meta:
        model = APIKey
        fields = ("id", "name", "prefix", "department", "created_at", "expires_at", "revoked_at")
        read_only_fields = ("id", "prefix", "created_at", "revoked_at")

    def validate_expires_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value


class APIKeyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    authentication_classes = (KeyAwareSessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = APIKeySerializer
    pagination_class = MetadataPagination

    def get_queryset(self):
        scope = managed_departments(self.request.user)
        if not scope.exists():
            raise PermissionDenied("Department or System Administrator access is required.")
        rows = APIKey.objects.filter(department__in=scope).order_by("id")
        selected = self.request.query_params.get("department")
        if selected is not None:
            try:
                selected = serializers.IntegerField(min_value=1, max_value=2**63 - 1).run_validation(selected)
            except serializers.ValidationError:
                raise serializers.ValidationError({"department": "Use a positive integer."}) from None
            get_object_or_404(scope, pk=selected)
            rows = rows.filter(department_id=selected)
        return rows

    def create(self, request, *args, **kwargs):
        self.get_queryset()  # Enforce manager role, even if there are no keys yet.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        department = get_object_or_404(managed_departments(request.user), pk=data["department_id"])
        key, raw = APIKey.issue(name=data["name"], department=department,
                              creator=request.user, expires_at=data["expires_at"])
        response = Response({**self.get_serializer(key).data, "key": raw}, status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "no-store"
        return response

    def destroy(self, request, *args, **kwargs):
        key = self.get_object()
        APIKey.objects.filter(pk=key.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
