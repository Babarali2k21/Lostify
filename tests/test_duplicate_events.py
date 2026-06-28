"""Phase 2 — Duplicate event deduplication tests."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
NOTIF_SERVICE = str(ROOT / "notification-service")
ITEM_SERVICE = str(ROOT / "item-service")

for name in list(sys.modules):
    if name == "app" or name.startswith("app."):
        del sys.modules[name]

for path in (ITEM_SERVICE,):
    while path in sys.path:
        sys.path.remove(path)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, NOTIF_SERVICE)

consumer = importlib.import_module("app.consumer")
database = importlib.import_module("app.database")
from shared.events import Event, EventType

handle_event = consumer.handle_event
is_duplicate = consumer.is_duplicate
mark_processed = consumer.mark_processed
Base = database.Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestDuplicateEvents:
    def test_first_event_not_duplicate(self, db_session):
        assert is_duplicate(db_session, "evt-001") is False

    def test_second_event_is_duplicate(self, db_session):
        event = Event(EventType.MATCH_FOUND, {"lostItemId": 1, "foundItemId": 2}, event_id="evt-001")
        mark_processed(db_session, event)
        assert is_duplicate(db_session, "evt-001") is True

    def test_handle_event_skips_duplicate(self, db_session, capsys):
        event = Event(
            EventType.MATCH_FOUND,
            {"lostItemId": 1, "foundItemId": 2, "title": "iPhone"},
            event_id="dup-test-001",
        )
        mark_processed(db_session, event)

        with patch.object(consumer, "SessionLocal", return_value=db_session):
            handle_event(event)

        captured = capsys.readouterr()
        assert "NOTIFICATION" not in captured.out

    def test_handle_event_processes_new_event(self, db_session, capsys):
        event = Event(
            EventType.ITEM_CREATED,
            {"itemId": 99, "itemType": "LOST", "title": "Test", "ownerUserId": 1},
            event_id="new-test-001",
        )

        with patch.object(consumer, "SessionLocal", return_value=db_session):
            handle_event(event)

        captured = capsys.readouterr()
        assert "NOTIFICATION" in captured.out
        assert is_duplicate(db_session, "new-test-001") is True
