import datetime
from contextlib import asynccontextmanager

import jwt
import pytest
from channels.testing import WebsocketCommunicator

from stayseated.core.services.event import get_event_config
from stayseated.routing import application


@asynccontextmanager
async def event_communicator():
    communicator = WebsocketCommunicator(application, "/ws/event/sample/")
    await communicator.connect()
    yield communicator
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_client_id():
    async with event_communicator() as c:
        await c.send_json_to(["authenticate", {"client_id": 4}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"event.config", "user.config"}


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("index", [0, 1])
async def test_auth_with_jwt_token(index):
    event_config = await get_event_config("sample")
    config = event_config["event"]["JWT_secrets"][index]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256").decode("utf-8")
    async with event_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "authenticated"
        assert set(response[1].keys()) == {"event.config", "user.config"}


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auth_with_invalid_jwt_token():
    event_config = await get_event_config("sample")
    config = event_config["event"]["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"] + "aaaa", algorithm="HS256").decode(
        "utf-8"
    )
    async with event_communicator() as c:
        await c.send_json_to(["authenticate", {"token": token}])
        response = await c.receive_json_from()
        assert response[0] == "error"
