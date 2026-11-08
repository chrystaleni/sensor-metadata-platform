from django.test import Client


def test_health_returns_http_200():
    response = Client().get("/health/")

    assert response.status_code == 200


def test_health_returns_expected_json():
    response = Client().get("/health/")

    assert response.json() == {"status": "ok"}


def test_health_accepts_get_requests():
    response = Client().get("/health/")

    assert response.status_code == 200
    assert response.request["REQUEST_METHOD"] == "GET"
