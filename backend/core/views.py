from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


def ready(request):
    """Read-only readiness check, without disclosing database errors."""
    from django.db import connection, DatabaseError
    from django.db.migrations.executor import MigrationExecutor
    from django.http import JsonResponse
    try:
        connection.ensure_connection()
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            return JsonResponse({"status": "migrations_pending"}, status=503)
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    response = JsonResponse({"status": "ready"})
    # An ephemeral runner marker prevents browser tests targeting a reused port.
    import os
    if os.environ.get("SENSOR_DISPOSABLE_VALIDATION") == "1":
        response["X-Sensor-Validation-Instance"] = os.environ.get("SENSOR_VALIDATION_INSTANCE", "")
    return response
