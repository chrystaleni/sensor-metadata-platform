from django.contrib.gis.geos import Polygon
from rest_framework import filters, serializers
from rest_framework.pagination import PageNumberPagination

from .serializers import MAX_ID


class MetadataPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class StableOrderingFilter(filters.OrderingFilter):
    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if "id" in ordering or "-id" in ordering:
            return ordering
        return (*ordering, "id")


class MetadataFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        for param in view.id_filters:
            value = request.query_params.get(param)
            if value is not None:
                try:
                    pk = serializers.IntegerField(min_value=1, max_value=MAX_ID).run_validation(value)
                except serializers.ValidationError as error:
                    raise serializers.ValidationError({param: error.detail}) from error
                queryset = queryset.filter(**{f"{param}_id": pk})

        bbox = request.query_params.get("bbox")
        if bbox is not None and view.geometry_field:
            boundary = parse_bbox(bbox)
            queryset = queryset.filter(**{f"{view.geometry_field}__intersects": boundary})
        return queryset


def parse_bbox(value):
    try:
        west, south, east, north = map(float, value.split(","))
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError
    except ValueError:
        raise serializers.ValidationError(
            {"bbox": "Expected west,south,east,north in WGS84 with increasing coordinates."}
        ) from None

    boundary = Polygon.from_bbox((west, south, east, north))
    boundary.srid = 4326
    return boundary
