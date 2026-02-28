"""Unit tests for session manager.

Uses unique agent_id per test to avoid polluting or reading the real user's
~/.openclaw/agents/main/sessions/ directory (TS: agentId-scoped sessions dir).
"""

import pytest
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch

from openclaw.agents.session import SessionManager, Session


def _make_isolated_manager(tmp_path: Path) -> SessionManager:
    """
    Create a SessionManager whose sessions dir is inside tmp_path.

    We use a unique agent_id and patch the home-dir resolution so the sessions
    dir is under tmp_path rather than the real ~/.openclaw/.
    """
    unique_id = f"test-{uuid.uuid4().hex[:8]}"
    # Redirect ~/.openclaw → tmp_path/.openclaw
    fake_home = tmp_path
    with patch.object(Path, "home", return_value=fake_home):
        manager = SessionManager(workspace_dir=tmp_path, agent_id=unique_id)
    return manager


@pytest.fixture
def isolated_manager(tmp_path):
    """SessionManager backed by a fresh temp directory — zero pre-existing sessions."""
    return _make_isolated_manager(tmp_path)


def test_session_manager_initialization(tmp_path):
    """Test session manager initialization starts with zero sessions."""
    manager = _make_isolated_manager(tmp_path)
    assert manager is not None
    assert len(manager.list_sessions()) == 0


def test_create_session(tmp_path):
    """Test session creation."""
    manager = _make_isolated_manager(tmp_path)
    session = manager.get_session("test-session")

    assert isinstance(session, Session)
    assert session.session_id == "test-session"


def test_get_existing_session(tmp_path):
    """Test retrieving existing session returns the same object."""
    manager = _make_isolated_manager(tmp_path)

    session1 = manager.get_session("test-session")
    session2 = manager.get_session("test-session")

    assert session1 is session2


def test_list_sessions(tmp_path):
    """Test listing all sessions."""
    manager = _make_isolated_manager(tmp_path)

    manager.get_session("session-1")
    manager.get_session("session-2")
    manager.get_session("session-3")

    sessions = manager.list_sessions()
    assert len(sessions) == 3
    assert "session-1" in sessions
    assert "session-2" in sessions
    assert "session-3" in sessions


def test_session_messages(tmp_path):
    """Test adding and retrieving messages."""
    manager = _make_isolated_manager(tmp_path)
    session = manager.get_session("test-session")

    session.add_user_message("Hello")
    session.add_assistant_message("Hi there!")

    messages = session.get_messages()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Hi there!"


def test_session_clear(tmp_path):
    """Test clearing session messages."""
    manager = _make_isolated_manager(tmp_path)
    session = manager.get_session("test-session")

    session.add_user_message("Message 1")
    session.add_user_message("Message 2")
    assert len(session.get_messages()) == 2

    session.clear()
    assert len(session.get_messages()) == 0
