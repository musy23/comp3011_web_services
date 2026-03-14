"""Tests for /observations CRUD endpoints."""

import pytest

from tests.conftest import OBSERVATION_PAYLOAD, STATION_PAYLOAD


@pytest.fixture
async def station_id(client):
    resp = await client.post("/stations", json=STATION_PAYLOAD)
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_observations_empty(public_client):
    resp = await public_client.get("/observations")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_create_observation(client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    resp = await client.post("/observations", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["date"] == "2023-06-15"
    assert body["max_temp_c"] == 22.5
    assert body["station_id"] == station_id


@pytest.mark.asyncio
async def test_create_observation_requires_api_key(public_client, client):
    resp_station = await client.post("/stations", json=STATION_PAYLOAD)
    sid = resp_station.json()["id"]
    payload = {**OBSERVATION_PAYLOAD, "station_id": sid}
    resp = await public_client.post("/observations", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_observation_invalid_station(client):
    payload = {**OBSERVATION_PAYLOAD, "station_id": 99999}
    resp = await client.post("/observations", json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_observation_duplicate(client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    await client.post("/observations", json=payload)
    resp = await client.post("/observations", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_observation(client, public_client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    create = await client.post("/observations", json=payload)
    obs_id = create.json()["id"]

    resp = await public_client.get(f"/observations/{obs_id}")
    assert resp.status_code == 200
    assert resp.json()["date"] == "2023-06-15"


@pytest.mark.asyncio
async def test_get_observation_not_found(public_client):
    resp = await public_client.get("/observations/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_observations_filter_by_station(client, public_client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    await client.post("/observations", json=payload)

    resp = await public_client.get(f"/observations?station_id={station_id}")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 1

    resp2 = await public_client.get("/observations?station_id=99999")
    assert resp2.json()["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_list_observations_date_filter(client, public_client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    await client.post("/observations", json=payload)
    payload2 = {**OBSERVATION_PAYLOAD, "station_id": station_id, "date": "2022-01-15"}
    await client.post("/observations", json=payload2)

    resp = await public_client.get("/observations?date_from=2023-01-01&date_to=2023-12-31")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_patch_observation(client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    create = await client.post("/observations", json=payload)
    obs_id = create.json()["id"]

    resp = await client.patch(f"/observations/{obs_id}", json={"max_temp_c": 30.0})
    assert resp.status_code == 200
    assert resp.json()["max_temp_c"] == 30.0
    assert resp.json()["min_temp_c"] == OBSERVATION_PAYLOAD["min_temp_c"]


@pytest.mark.asyncio
async def test_delete_observation(client, public_client, station_id):
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id}
    create = await client.post("/observations", json=payload)
    obs_id = create.json()["id"]

    resp = await client.delete(f"/observations/{obs_id}")
    assert resp.status_code == 204

    resp = await public_client.get(f"/observations/{obs_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_observation_min_max_validation(client, station_id):
    """min_temp_c must be <= max_temp_c."""
    payload = {**OBSERVATION_PAYLOAD, "station_id": station_id, "min_temp_c": 30.0, "max_temp_c": 10.0}
    resp = await client.post("/observations", json=payload)
    assert resp.status_code == 422
