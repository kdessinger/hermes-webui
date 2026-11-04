from urllib.parse import urlparse


def test_metadata_poll_does_not_reconstruct_regeneration_transcript(monkeypatch):
    import api.routes as routes
    import api.session_ops as session_ops
    from api.models import Session

    session = Session(session_id="metadata_regression", title="Long conversation")
    monkeypatch.setattr(routes, "get_session", lambda sid, metadata_only=False: session)
    monkeypatch.setattr(routes, "_clear_stale_stream_state", lambda s: None)
    monkeypatch.setattr(routes, "_metadata_only_message_summary", lambda *a, **kw: {"message_count": 2732, "last_message_at": 1234})
    monkeypatch.setattr(routes, "_active_stream_ids", lambda: set())
    monkeypatch.setattr(routes, "redact_session_data", lambda payload: payload)
    monkeypatch.setattr(routes, "j", lambda handler, payload, **kw: payload)

    def forbidden(*args, **kwargs):
        raise AssertionError("metadata polling must not reconstruct the full regeneration transcript")

    monkeypatch.setattr(session_ops, "regeneration_state", forbidden)
    response = routes._handle_session_get(object(), urlparse("/api/session?session_id=metadata_regression&messages=0&resolve_model=0"))["session"]
    assert response["messages"] == []
    assert response["message_count"] == 2732
    assert "regeneration_revision" not in response
