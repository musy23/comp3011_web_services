"""Tests for /stations CRUD endpoints."""

import pytest

from tests.conftest import STATION_PAYLOAD


@pytest.mark.asyncio
async def test_list_stations_empty(public_client):
    resp = await public_client.get("/stations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == []
    assert data["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_create_station(client):
    resp = await client.post("/stations", json=STATION_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["station_id"] == "TESTST"
    assert body["name"] == "Test Station"
    assert body["region"] == "Test Region"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_station_requires_api_key(public_client):
    resp = await public_client.post("/stations", json=STATION_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_station_duplicate(client):
    await client.post("/stations", json=STATION_PAYLOAD)
    resp = await client.post("/stations", json=STATION_PAYLOAD)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_station(client, public_client):
    create = await client.post("/stations", json=STATION_PAYLOAD)
    station_id = create.json()["id"]

    resp = await public_client.get(f"/stations/{station_id}")
    assert resp.status_code == 200
    assert resp.json()["station_id"] == "TESTST"


@pytest.mark.asyncio
async def test_get_station_not_found(public_client):
    resp = await public_client.get("/stations/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_stations_with_data(client, public_client):
    await client.post("/stations", json=STATION_PAYLOAD)
    second = {**STATION_PAYLOAD, "station_id": "TESTB", "name": "Second Station", "region": "Scotland"}
    await client.post("/stations", json=second)

    resp = await public_client.get("/stations")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_list_stations_filter_region(client, public_client):
    await client.post("/stations", json=STATION_PAYLOAD)
    scottish = {**STATION_PAYLOAD, "station_id": "SCOT1", "region": "Scotland"}
    await client.post("/stations", json=scottish)

    resp = await public_client.get("/stations?region=Scotland")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 1
    assert resp.json()["data"][0]["region"] == "Scotland"


@pytest.mark.asyncio
async def test_update_station(client):
    create = await client.post("/stations", json=STATION_PAYLOAD)
    station_id = create.json()["id"]

    updated = {**STATION_PAYLOAD, "name": "Updated Name"}
    resp = await client.put(f"/stations/{station_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_patch_station(client):
    create = await client.post("/stations", json=STATION_PAYLOAD)
    station_id = create.json()["id"]

    resp = await client.patch(f"/stations/{station_id}", json={"name": "Patched Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Patched Name"
    # Other fields unchanged
    assert resp.json()["region"] == STATION_PAYLOAD["region"]


@pytest.mark.asyncio
async def test_delete_station(client, public_client):
    create = await client.post("/stations", json=STATION_PAYLOAD)
    station_id = create.json()["id"]

    resp = await client.delete(f"/stations/{station_id}")
    assert resp.status_code == 204

    resp = await public_client.get(f"/stations/{station_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_station_not_found(client):
    resp = await client.delete("/stations/99999")
    assert resp.status_code == 404