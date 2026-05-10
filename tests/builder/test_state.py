from builder.state import ItemState, PhaseState


def test_item_state_default_pending():
    item = ItemState()
    assert item.status == "pending"
    assert item.completed_at is None
    assert item.error is None
    assert item.metadata == {}


def test_item_state_to_dict_round_trip():
    item = ItemState(
        status="done",
        completed_at="2026-05-10T10:00:00Z",
        error=None,
        metadata={"method": "text", "extracted_chars": 12000},
    )
    assert ItemState.from_dict(item.to_dict()) == item


def test_phase_state_default_pending():
    phase = PhaseState(name="ingest")
    assert phase.name == "ingest"
    assert phase.status == "pending"
    assert phase.started_at is None
    assert phase.completed_at is None
    assert phase.items == {}


def test_phase_state_to_dict_round_trip():
    phase = PhaseState(
        name="transform",
        status="in_progress",
        started_at="2026-05-10T10:00:00Z",
        completed_at=None,
        items={
            "doc_001.pdf": ItemState(status="done", completed_at="2026-05-10T10:30:00Z"),
            "doc_002.pdf": ItemState(status="in_progress"),
        },
    )
    assert PhaseState.from_dict(phase.to_dict()) == phase


def test_phase_state_from_dict_accepts_missing_optional_fields():
    """Older state files may omit fields; from_dict must tolerate that."""
    minimal = {"name": "qa", "status": "pending"}
    phase = PhaseState.from_dict(minimal)
    assert phase.name == "qa"
    assert phase.status == "pending"
    assert phase.items == {}
