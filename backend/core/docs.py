"""OpenAPI schema and interactive documentation (Phase 2 design, section 1.5)."""

from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.schemas import get_schema_view

# The schema describes every endpoint, so only signed-in users can read it.
schema_view = get_schema_view(
    title="Sensor Metadata Management Platform API",
    version="1.0.0",
    description="Department-scoped metadata API. Sign in first; API keys use the X-API-Key header.",
    patterns=None,
    permission_classes=(IsAuthenticated,),
    renderer_classes=(JSONOpenAPIRenderer,),
)

SWAGGER_VERSION = "5.17.14"
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Sensor Metadata API</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@%(v)s/swagger-ui.css"></head>
<body><div id="ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@%(v)s/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: "/api/v1/openapi.json", dom_id: "#ui", withCredentials: true});</script>
</body></html>"""


@require_GET
@never_cache
def docs(request):
    return HttpResponse(PAGE % {"v": SWAGGER_VERSION}, content_type="text/html; charset=utf-8")
