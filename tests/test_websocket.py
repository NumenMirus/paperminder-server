"""Integration tests for websocket messaging routes."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.database import MessageLog, session_scope


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_personal_message_delivery_between_connected_users(client: TestClient) -> None:
    alice_id = str(uuid4())
    bob_id = str(uuid4())

    with client.websocket_connect(f"/ws/{alice_id}") as alice_ws, client.websocket_connect(
        f"/ws/{bob_id}"
    ) as bob_ws:
        assert alice_ws.receive_json()["code"] == "info"
        assert bob_ws.receive_json()["code"] == "info"

        alice_ws.send_json({"recipient_id": bob_id, "sender_name": "Alice", "message": "hello"})
        delivery = bob_ws.receive_json()

        assert delivery["kind"] == "message"
        assert delivery["sender_name"] == "Alice"
        assert delivery["message"] == "hello"


def test_subscription_message_with_printer_and_api_key_is_acknowledged(client: TestClient) -> None:
    printer_id = str(uuid4())

    with client.websocket_connect(f"/ws/{printer_id}") as printer_ws:
        assert printer_ws.receive_json()["code"] == "info"

        printer_ws.send_json({"printer_name": "office-printer", "api_key": "abc123"})
        acknowledgement = printer_ws.receive_json()

        assert acknowledgement["kind"] == "status"
        assert acknowledgement["code"] == "subscription_accepted"
        assert "office-printer" in acknowledgement["detail"]


def test_subscription_message_missing_api_key_returns_validation_error(client: TestClient) -> None:
    printer_id = str(uuid4())

    with client.websocket_connect(f"/ws/{printer_id}") as printer_ws:
        assert printer_ws.receive_json()["code"] == "info"

        printer_ws.send_json({"printer_name": "office-printer"})
        failure = printer_ws.receive_json()

        assert failure["kind"] == "status"
        assert failure["code"] == "validation_error"


def test_sender_gets_status_when_recipient_missing(client: TestClient) -> None:
    charlie_id = str(uuid4())
    ghost_id = str(uuid4())

    with client.websocket_connect(f"/ws/{charlie_id}") as charlie_ws:
        assert charlie_ws.receive_json()["code"] == "info"

        charlie_ws.send_json({"recipient_id": ghost_id, "sender_name": "Charlie", "message": "ping"})
        failure = charlie_ws.receive_json()

        assert failure["kind"] == "status"
        assert failure["code"] == "recipient_not_connected"
    assert ghost_id in failure["detail"]


def test_http_test_endpoint_delivers_message_to_connected_user(client: TestClient) -> None:
    destiny_id = str(uuid4())

    with client.websocket_connect(f"/ws/{destiny_id}") as destiny_ws:
        assert destiny_ws.receive_json()["code"] == "info"

        response = client.post(
            "/test/messages",
            json={"recipient_id": destiny_id, "message": "http says hi", "sender_name": "System"},
        )

        assert response.status_code == 202
        assert response.json() == {"status": "sent"}

        delivery = destiny_ws.receive_json()
        assert delivery["kind"] == "message"
        assert delivery["sender_name"] == "System"
        assert delivery["message"] == "http says hi"


def test_http_test_endpoint_returns_not_found_when_user_absent(client: TestClient) -> None:
    phantom_id = str(uuid4())

    response = client.post(
        "/api/message", json={"recipient_id": phantom_id, "message": "boo", "sender_name": "System"}
    )

    assert response.status_code == 404
    assert phantom_id in response.json()["detail"]


def test_message_persisted_in_database(client: TestClient) -> None:
    alice_id = str(uuid4())
    bob_id = str(uuid4())

    with client.websocket_connect(f"/ws/{alice_id}") as alice_ws, client.websocket_connect(
        f"/ws/{bob_id}"
    ) as bob_ws:
        assert alice_ws.receive_json()["code"] == "info"
        assert bob_ws.receive_json()["code"] == "info"

        alice_ws.send_json({"recipient_id": bob_id, "sender_name": "Alice", "message": "hi there"})
        _ = bob_ws.receive_json()

    with session_scope() as session:
        logs = session.query(MessageLog).all()

    assert len(logs) == 1
    log = logs[0]
    assert log.sender_id == alice_id
    assert log.sender_name == "Alice"
    assert log.recipient_id == bob_id
    assert log.message_body == "hi there"
