"""Integration tests for websocket messaging routes."""

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_personal_message_delivery_between_connected_users() -> None:
    with client.websocket_connect("/ws/alice") as alice_ws, client.websocket_connect("/ws/bob") as bob_ws:
        assert alice_ws.receive_json()["code"] == "info"
        assert bob_ws.receive_json()["code"] == "info"

        alice_ws.send_json({"recipient_id": "bob", "content": "hello"})
        delivery = bob_ws.receive_json()

        assert delivery["kind"] == "message"
        assert delivery["sender_id"] == "alice"
        assert delivery["recipient_id"] == "bob"
        assert delivery["content"] == "hello"


def test_sender_gets_status_when_recipient_missing() -> None:
    with client.websocket_connect("/ws/charlie") as charlie_ws:
        assert charlie_ws.receive_json()["code"] == "info"

        charlie_ws.send_json({"recipient_id": "ghost", "content": "ping"})
        failure = charlie_ws.receive_json()

        assert failure["kind"] == "status"
        assert failure["code"] == "recipient_not_connected"
        assert "ghost" in failure["detail"]
