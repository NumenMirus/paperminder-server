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

        alice_ws.send_json({"recipient_id": "bob", "sender_name": "Alice", "message": "hello"})
        delivery = bob_ws.receive_json()

        assert delivery["kind"] == "message"
        assert delivery["sender_name"] == "Alice"
        assert delivery["message"] == "hello"


def test_subscription_message_with_printer_and_api_key_is_acknowledged() -> None:
    with client.websocket_connect("/ws/printer-client") as printer_ws:
        assert printer_ws.receive_json()["code"] == "info"

        printer_ws.send_json({"printer_name": "office-printer", "api_key": "abc123"})
        acknowledgement = printer_ws.receive_json()

        assert acknowledgement["kind"] == "status"
        assert acknowledgement["code"] == "subscription_accepted"
        assert "office-printer" in acknowledgement["detail"]


def test_subscription_message_missing_api_key_returns_validation_error() -> None:
    with client.websocket_connect("/ws/printer-client-missing-key") as printer_ws:
        assert printer_ws.receive_json()["code"] == "info"

        printer_ws.send_json({"printer_name": "office-printer"})
        failure = printer_ws.receive_json()

        assert failure["kind"] == "status"
        assert failure["code"] == "validation_error"


def test_sender_gets_status_when_recipient_missing() -> None:
    with client.websocket_connect("/ws/charlie") as charlie_ws:
        assert charlie_ws.receive_json()["code"] == "info"

        charlie_ws.send_json({"recipient_id": "ghost", "sender_name": "Charlie", "message": "ping"})
        failure = charlie_ws.receive_json()

        assert failure["kind"] == "status"
        assert failure["code"] == "recipient_not_connected"
        assert "ghost" in failure["detail"]


def test_http_test_endpoint_delivers_message_to_connected_user() -> None:
    with client.websocket_connect("/ws/destiny") as destiny_ws:
        assert destiny_ws.receive_json()["code"] == "info"

        response = client.post(
            "/test/messages",
            json={"recipient_id": "destiny", "message": "http says hi", "sender_name": "System"},
        )

        assert response.status_code == 202
        assert response.json() == {"status": "sent"}

        delivery = destiny_ws.receive_json()
        assert delivery["kind"] == "message"
        assert delivery["sender_name"] == "System"
        assert delivery["message"] == "http says hi"


def test_http_test_endpoint_returns_not_found_when_user_absent() -> None:
    response = client.post(
        "/test/messages", json={"recipient_id": "phantom", "message": "boo", "sender_name": "System"}
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Recipient 'phantom'")
