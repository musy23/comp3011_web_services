"""Tests for /annotations CRUD endpoints."""

import pytest

from tests.conftest import ANNOTATION_PAYLOAD, STATION_PAYLOAD


@pytest.fixture
async def station_id(client):
    resp = await client.post("/stations", json=STATION_PAYLOAD)
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_annotations_empty(public_client):
    resp = await public_client.get("/annotations")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_create_annotation_public(public_client, client):
    resp_station = await client.post("/stations", json=STATION_PAYLOAD)
    sid = resp_station.json()["id"]
    payload = {**ANNOTATION_PAYLOAD, "station_id": sid}
    resp = await public_client.post("/annotations", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["note"] == ANNOTATION_PAYLOAD["note"]
    assert body["approved"] is False


@pytest.mark.asyncio
async def test_create_annotation_invalid_station(public_client):
    payload = {**ANNOTATION_PAYLOAD, "station_id": 99999}
    resp = await public_client.post("/annotations", json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_annotation(client, public_client, station_id):
    payload = {**ANNOTATION_PAYLOAD, "station_id": station_id}
    create = await public_client.post("/annotations", json=payload)
    ann_id = create.json()["id"]
    resp = await public_client.get(f"/annotations/{ann_id}")
    assert resp.status_code == 200
    assert resp.json()["note"] == ANNOTATION_PAYLOAD["note"]


@pytest.mark.asyncio
async def test_get_annotation_not_found(public_client):
    resp = await public_client.get("/annotations/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_annotation(client, public_client, station_id):
    payload = {**ANNOTATION_PAYLOAD, "station_id": station_id}
    create = await public_client.post("/annotations", json=payload)
    ann_id = create.json()["id"]
    resp = await client.patch(f"/annotations/{ann_id}", json={"approved": True})
    assert resp.status_code == 200
    assert resp.json()["approved"] is True


@pytest.mark.asyncio
async def test_approve_annotation_requires_api_key(public_client, client, station_id):
    payload = {**ANNOTATION_PAYLOAD, "station_id": station_id}
    create = await public_client.post("/annotations", json=payload)
    ann_id = create.json()["id"]
    resp = await public_client.patch(f"/annotations/{ann_id}", json={"approved": True})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_filter_annotations_by_approved(client, public_client, station_id):
    payload = {**ANNOTATION_PAYLOAD, "station_id": station_id}
    create = await public_client.post("/annotations", json=payload)
    ann_id = create.json()["id"]
    await client.patch(f"/annotations/{ann_id}", json={"approved": True})
    payload2 = {**ANNOTATION_PAYLOAD, "station_id": station_id, "note": "Another note about this station."}
    await public_client.post("/annotations", json=payload2)
    resp = await public_client.get("/annotations?approved=true")
    assert resp.json()["pagination"]["total"] == 1
    resp2 = await public_client.get("/annotations?approved=false")
    assert resp2.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_delete_annotation(client, public_client, station_id):
    payload = {**ANNOTATION_PAYLOAD, "station_id": station_id}
    create = await public_client.post("/annotations", json=payload)
    ann_id = create.json()["id"]
    resp = await client.delete(f"/annotations/{ann_id}")
    assert resp.status_code == 204
    resp = await public_client.get(f"/annotations/{ann_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_annotation_note_too_short(public_client, client, station_id):
    payload = {**ANNOTATION_PAYLOAD, "station_id": station_id, "note": "Hi"}
    resp = await public_client.post("/annotations", json=payload)
    assert resp.status_code == 422
