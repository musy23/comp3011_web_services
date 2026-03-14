"""Tests for /analytics endpoints."""

import pytest

from tests.conftest import STATION_PAYLOAD


async def _seed(client):
    """Create a station and 12 monthly observations for analytics tests."""
    resp = await client.post("/stations", json=STATION_PAYLOAD)
    sid = resp.json()["id"]
    station_code = resp.json()["station_id"]

    months = [
        ("2020-01-15", 5.0, -1.0, 2.0, 80.0, 2.0),
        ("2020-02-15", 7.0, 0.0, 3.5, 55.0, 3.0),
        ("2020-03-15", 10.0, 2.0, 6.0, 45.0, 5.0),
        ("2020-04-15", 14.0, 5.0, 9.5, 40.0, 7.0),
        ("2020-05-15", 18.0, 8.0, 13.0, 50.0, 9.0),
        ("2020-06-15", 22.0, 12.0, 17.0, 30.0, 11.0),
        ("2020-07-15", 25.0, 14.0, 19.5, 25.0, 12.0),
        ("2020-08-15", 24.0, 13.0, 18.5, 35.0, 10.0),
        ("2020-09-15", 19.0, 9.0, 14.0, 55.0, 8.0),
        ("2020-10-15", 13.0, 5.0, 9.0, 70.0, 5.0),
        ("2020-11-15", 8.0, 1.0, 4.5, 75.0, 3.0),
        ("2020-12-15", 5.0, -2.0, 1.5, 85.0, 1.5),
    ]
    for date, tmax, tmin, tmean, rain, sun in months:
        await client.post("/observations", json={
            "station_id": sid,
            "date": date,
            "max_temp_c": tmax,
            "min_temp_c": tmin,
            "mean_temp_c": tmean,
            "rainfall_mm": rain,
            "sunshine_hours": sun,
            "data_quality": 1,
        })

    return sid, station_code


@pytest.mark.asyncio
async def test_health_check(public_client):
    resp = await public_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_extremes_empty(public_client):
    resp = await public_client.get("/analytics/extremes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hottest_day"] is None
    assert body["coldest_day"] is None


@pytest.mark.asyncio
async def test_extremes_with_data(client, public_client):
    await _seed(client)
    resp = await public_client.get("/analytics/extremes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hottest_day"] is not None
    assert body["hottest_day"]["value"] == 25.0
    assert body["coldest_day"]["value"] == -2.0
    assert body["wettest_day"]["value"] == 85.0


@pytest.mark.asyncio
async def test_seasonal(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(
        f"/analytics/seasonal/{station_code}?variable=mean_temp_c&year_from=2020&year_to=2020"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["station_id"] == station_code
    assert len(body["monthly_stats"]) == 12
    july = next(m for m in body["monthly_stats"] if m["month"] == 7)
    assert july["season"] == "Summer"
    assert july["mean"] == pytest.approx(19.5, abs=0.1)


@pytest.mark.asyncio
async def test_seasonal_invalid_station(public_client):
    resp = await public_client.get("/analytics/seasonal/NOPE?variable=mean_temp_c&year_from=2020&year_to=2020")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trends(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(
        f"/analytics/trends/{station_code}?variable=mean_temp_c&date_from=2020-01-01&date_to=2020-12-31"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["station_id"] == station_code
    assert "slope_per_decade" in body
    assert len(body["data_points"]) == 12


@pytest.mark.asyncio
async def test_trends_invalid_variable(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(
        f"/analytics/trends/{station_code}?variable=invalid_var&date_from=2020-01-01&date_to=2020-12-31"
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_anomalies(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(
        f"/analytics/anomalies/{station_code}?variable=max_temp_c&threshold_sigma=0.5"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["station_id"] == station_code
    assert "anomalies" in body


@pytest.mark.asyncio
async def test_heatmap(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(
        f"/analytics/heatmap/{station_code}?variable=mean_temp_c&year=2020"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2020
    assert len(body["cells"]) == 12


@pytest.mark.asyncio
async def test_heatmap_empty_year(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(
        f"/analytics/heatmap/{station_code}?variable=mean_temp_c&year=1800"
    )
    assert resp.status_code == 200
    assert resp.json()["cells"] == []


@pytest.mark.asyncio
async def test_climate_normal(client, public_client):
    _, station_code = await _seed(client)
    resp = await public_client.get(f"/analytics/climate-normal/{station_code}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["normal_period"] == "1991-2020"
    # Our seed data is 2020, which is within 1991-2020, so normals should be empty or minimal
    assert "normals" in body


@pytest.mark.asyncio
async def test_compare(client, public_client):
    _, code1 = await _seed(client)
    # Create a second station
    second_payload = {**STATION_PAYLOAD, "station_id": "COMP2", "name": "Compare Station 2"}
    resp2 = await client.post("/stations", json=second_payload)
    sid2 = resp2.json()["id"]
    await client.post("/observations", json={
        "station_id": sid2, "date": "2020-06-15",
        "max_temp_c": 20.0, "min_temp_c": 10.0, "mean_temp_c": 15.0,
        "rainfall_mm": 40.0, "data_quality": 1,
    })

    resp = await public_client.get(
        f"/analytics/compare?stations={code1},COMP2&variable=mean_temp_c"
        f"&date_from=2020-01-01&date_to=2020-12-31"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["stations"]) == 2


@pytest.mark.asyncio
async def test_compare_requires_two_stations(public_client):
    resp = await public_client.get(
        "/analytics/compare?stations=ONLY1&variable=mean_temp_c&date_from=2020-01-01&date_to=2020-12-31"
    )
    assert resp.status_code == 422
