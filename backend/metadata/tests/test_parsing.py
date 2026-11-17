"""Request parsing failures must not change stored metadata or identifiers."""

from urllib.parse import urlencode

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from metadata.models import ExternalIdentifier
from metadata.tests.test_backend import API
from metadata.tests.test_error_contract import database_snapshot, scenario


pytestmark = pytest.mark.postgis


@pytest.mark.parametrize("opening,closing", [("[", "]"), ('{"nested":', "}")], ids=["array", "object"])
def test_deep_json_patch_returns_parse_error_and_preserves_metadata(scenario, opening, closing):
    client = scenario["client"]
    editor, previous_actor = scenario["users"]["editor"], scenario["users"]["multi"]
    client.force_authenticate(editor)
    client.raise_request_exception = False
    element = scenario["records"]["network-elements"]
    element.description = "Preserve this description"
    element.geometry = Point(33.36, 35.15, srid=4326)
    element.dma_model_id = "DMA-saved"
    element.created_by, element.updated_by = editor, previous_actor
    element.save()
    element.external_identifiers.update(created_by=editor, updated_by=previous_actor)
    ExternalIdentifier.objects.create(
        network_element=element, source="OLD", value="archived-identifier",
        created_by=editor, updated_by=previous_actor, deleted_at=timezone.now(), deleted_by=previous_actor,
    )
    before = database_snapshot()
    # Construct raw bytes, avoiding recursion in the client's JSON encoder.
    # Even an unknown field must be fully parsed before any serializer runs.
    # The native decoder in Python 3.13 can accept more nesting than the
    # Python recursion limit; use a payload beyond its native stack budget.
    depth = 100_000
    nested = opening * depth + "0" + closing * depth
    body = ('{"name":"Must not be saved","external_identifiers":'
            '[{"source":"ERP","value":"must-not-replace-existing"}],"extra":' + nested + '}')
    response = client.generic("PATCH", f"{API}network-elements/{element.pk}/",
                              body.encode("utf-8"), content_type="application/json")
    assert response.status_code == 400, response.content
    assert response.json() == {"detail": "JSON parse error."}
    assert response.data["detail"].code == "parse_error"
    assert database_snapshot() == before


@pytest.mark.parametrize("encoding", ["form", "multipart"])
def test_default_form_parsers_still_accept_metadata(scenario, encoding):
    client = scenario["client"]
    editor = scenario["users"]["editor"]
    client.force_authenticate(editor)
    data = {"department": 2, "name": "Form device", "device_type": scenario["catalog"]["device_type"]}
    if encoding == "form":
        response = client.generic("POST", f"{API}physical-devices/", urlencode(data),
                                  content_type="application/x-www-form-urlencoded")
    else:
        response = client.post(f"{API}physical-devices/", data, format="multipart")
    assert response.status_code == 201, response.content
    assert response.json()["name"] == data["name"]
    assert response.json()["created_by"] == editor.pk
