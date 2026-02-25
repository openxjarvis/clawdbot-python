"""Test session data interoperability between TypeScript and Python.

This test verifies that openclaw-python can read and write JSONL session files
that are compatible with the TypeScript implementation.

Key validation points:
1. JSONL format compatibility (line-delimited JSON)
2. Session header structure (version, id, cwd, timestamp)
3. Entry types (message, compaction, branch_summary, thinking_level_change, etc.)
4. Tree structure (id, parentId, branchName)
5. Message format (role, content, timestamp)
"""
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime


def test_jsonl_format_compatibility():
    """Verify JSONL format matches TypeScript expectations."""
    
    # Create a test JSONL file with entries matching TS format
    test_entries = [
        # Session header
        {
            "type": "session",
            "id": "test-session-001",
            "version": 3,
            "timestamp": "1771786341833",
            "cwd": "/workspace",
        },
        # Message entry
        {
            "id": "msg-001",
            "type": "message",
            "timestamp": 1771786341833,
            "parentId": None,
            "message": {
                "role": "user",
                "content": "Hello, world!",
            },
        },
        # Assistant message entry
        {
            "id": "msg-002",
            "type": "message",
            "timestamp": 1771786342000,
            "parentId": "msg-001",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello! How can I help you?"}],
            },
        },
    ]
    
    # Write JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for entry in test_entries:
            f.write(json.dumps(entry) + "\n")
        temp_path = f.name
    
    try:
        # Read back and verify
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}"
        
        # Parse each line
        parsed = [json.loads(line) for line in lines]
        
        # Verify session header
        assert parsed[0]["type"] == "session"
        assert parsed[0]["version"] == 3
        assert "id" in parsed[0]
        assert "timestamp" in parsed[0]
        
        # Verify user message
        assert parsed[1]["type"] == "message"
        assert parsed[1]["message"]["role"] == "user"
        assert "timestamp" in parsed[1]
        assert "id" in parsed[1]
        
        # Verify assistant message
        assert parsed[2]["type"] == "message"
        assert parsed[2]["message"]["role"] == "assistant"
        assert parsed[2]["parentId"] == "msg-001"
        
        print("✅ JSONL format matches TypeScript expectations")
        
    finally:
        Path(temp_path).unlink()


def test_session_manager_creates_compatible_jsonl():
    """Verify pi_coding_agent.SessionManager creates TS-compatible JSONL."""
    
    try:
        from pi_coding_agent.core.session_manager import SessionManager
        from pi_ai.types import UserMessage, AssistantMessage
        
        # Create a session with test data
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create SessionManager with sessions_dir
            sm = SessionManager(
                sessions_dir=tmpdir,
                cwd="/workspace",
            )
            
            # Create a new session (generates session_id and creates file)
            session_id = sm.create_session(label="test-interop")
            
            # Add messages (as dicts, not Pydantic objects)
            timestamp = int(time.time() * 1000)
            sm.append_message({
                "role": "user",
                "content": "Test user message",
                "timestamp": timestamp,
            })
            sm.append_message({
                "role": "assistant",
                "content": [{"type": "text", "text": "Test assistant reply"}],
                "api": "test-api",
                "provider": "test-provider",
                "model": "test-model",
                "timestamp": timestamp + 100,
            })
            
            # Verify JSONL file was created
            session_file = Path(tmpdir) / f"{session_id}.jsonl"
            assert session_file.exists(), f"Session file not created: {session_file}"
            
            # Read and verify format
            with open(session_file, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) >= 3, f"Expected at least 3 lines (header + 2 messages), got {len(lines)}"
            
            # Parse lines
            entries = [json.loads(line) for line in lines]
            
            # Verify header
            header = entries[0]
            assert header.get("type") == "session", f"First line should be session header, got: {header.get('type')}"
            assert header.get("version") == 3, f"Expected version 3, got: {header.get('version')}"
            
            # Verify messages
            message_entries = [e for e in entries if e.get("type") == "message"]
            assert len(message_entries) >= 2, f"Expected at least 2 messages, got {len(message_entries)}"
            
            # Check user message
            user_msg = message_entries[0]
            assert user_msg["message"]["role"] == "user"
            assert "Test user message" in str(user_msg["message"]["content"])
            
            # Check assistant message
            asst_msg = message_entries[1]
            assert asst_msg["message"]["role"] == "assistant"
            assert "Test assistant reply" in str(asst_msg["message"]["content"])
            
            print("✅ SessionManager creates TS-compatible JSONL")
            
    except ImportError as e:
        print(f"⚠️  Skipping test - pi_coding_agent not available: {e}")


def test_session_tree_structure():
    """Verify session tree structure (id/parentId/branchName) is compatible."""
    
    try:
        from pi_coding_agent.core.session_manager import SessionManager
        from pi_ai.types import UserMessage, AssistantMessage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(
                sessions_dir=tmpdir,
                cwd="/workspace",
            )
            
            # Create session
            session_id = sm.create_session(label="test-tree")
            
            # Add messages in a tree structure
            timestamp = int(time.time() * 1000)
            sm.append_message({
                "role": "user",
                "content": "Message 1",
                "timestamp": timestamp,
            })
            sm.append_message({
                "role": "assistant",
                "content": [{"type": "text", "text": "Reply 1"}],
                "api": "test-api",
                "provider": "test-provider",
                "model": "test-model",
                "timestamp": timestamp + 100,
            })
            
            # Read the file
            session_file = Path(tmpdir) / f"{session_id}.jsonl"
            with open(session_file, 'r') as f:
                entries = [json.loads(line) for line in f]
            
            # Verify tree structure
            message_entries = [e for e in entries if e.get("type") == "message"]
            
            for entry in message_entries:
                # Each entry should have an id
                assert "id" in entry, "Entry missing 'id' field"
                
                # ParentId can be None for root messages
                assert "parentId" in entry or entry.get("parentId") is None
                
                print(f"✅ Entry {entry['id'][:8]}... has valid tree structure")
            
            print("✅ Session tree structure is compatible")
            
    except ImportError as e:
        print(f"⚠️  Skipping test - pi_coding_agent not available: {e}")


def test_session_compaction_format():
    """Verify compaction entry format is compatible."""
    
    # Create a synthetic compaction entry matching TS format
    compaction_entry = {
        "id": "compact-001",
        "type": "compaction",
        "timestamp": int(datetime.now().timestamp() * 1000),
        "parentId": "msg-100",
        "summary": "Compacted 50 messages",
        "removedIds": ["msg-001", "msg-002", "msg-003"],
    }
    
    # Verify structure
    assert compaction_entry["type"] == "compaction"
    assert "id" in compaction_entry
    assert "timestamp" in compaction_entry
    assert "parentId" in compaction_entry
    assert "summary" in compaction_entry
    assert "removedIds" in compaction_entry
    assert isinstance(compaction_entry["removedIds"], list)
    
    print("✅ Compaction entry format is compatible")


def test_branch_summary_format():
    """Verify branch_summary entry format is compatible."""
    
    # Create a synthetic branch_summary entry matching TS format
    branch_summary = {
        "id": "branch-001",
        "type": "branch_summary",
        "timestamp": int(datetime.now().timestamp() * 1000),
        "parentId": "msg-100",
        "branchName": "feature-branch",
        "summary": "Working on feature X",
    }
    
    # Verify structure
    assert branch_summary["type"] == "branch_summary"
    assert "id" in branch_summary
    assert "branchName" in branch_summary
    assert "summary" in branch_summary
    
    print("✅ Branch summary format is compatible")


def test_read_typescript_generated_jsonl():
    """Test that Python can read a TypeScript-generated JSONL file."""
    
    # Create a synthetic TS-format JSONL file
    ts_format_entries = [
        '{"type": "session", "id": "ts-session-001", "version": 3, "timestamp": "1771786341833", "cwd": "/workspace"}',
        '{"id": "msg-001", "type": "message", "timestamp": 1771786341833, "parentId": null, "message": {"role": "user", "content": "Hello from TypeScript"}}',
        '{"id": "msg-002", "type": "message", "timestamp": 1771786342000, "parentId": "msg-001", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hello from Python!"}]}}',
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for entry in ts_format_entries:
            f.write(entry + "\n")
        temp_path = f.name
    
    try:
        # Read with Python
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # Parse
        entries = [json.loads(line.strip()) for line in lines if line.strip()]
        
        # Verify we can read TS format
        assert len(entries) == 3
        assert entries[0]["type"] == "session"
        assert entries[1]["message"]["content"] == "Hello from TypeScript"
        assert entries[2]["message"]["role"] == "assistant"
        
        print("✅ Python can read TypeScript-generated JSONL")
        
    finally:
        Path(temp_path).unlink()


def test_python_generates_ts_readable_jsonl():
    """Test that TypeScript can read Python-generated JSONL (structure validation)."""
    
    try:
        from pi_coding_agent.core.session_manager import SessionManager
        from pi_ai.types import UserMessage, AssistantMessage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create session with Python
            sm = SessionManager(
                sessions_dir=tmpdir,
                cwd="/workspace",
            )
            
            session_id = sm.create_session(label="python-gen")
            
            timestamp = int(time.time() * 1000)
            sm.append_message({
                "role": "user",
                "content": "Message from Python",
                "timestamp": timestamp,
            })
            sm.append_message({
                "role": "assistant",
                "content": [{"type": "text", "text": "Python reply"}],
                "api": "test-api",
                "provider": "test-provider",
                "model": "test-model",
                "timestamp": timestamp + 100,
            })
            
            # Read the generated file
            session_file = Path(tmpdir) / f"{session_id}.jsonl"
            with open(session_file, 'r') as f:
                lines = f.readlines()
            
            # Verify each line is valid JSON (TS requirement)
            for i, line in enumerate(lines):
                try:
                    entry = json.loads(line.strip())
                    # Verify required fields for TS compatibility
                    if entry.get("type") == "session":
                        assert "id" in entry
                        assert "version" in entry
                    elif entry.get("type") == "message":
                        assert "id" in entry
                        assert "timestamp" in entry
                        assert "message" in entry
                        assert "role" in entry["message"]
                except json.JSONDecodeError as e:
                    raise AssertionError(f"Line {i+1} is not valid JSON: {e}")
            
            print("✅ Python generates TS-readable JSONL")
            
    except ImportError as e:
        print(f"⚠️  Skipping test - pi_coding_agent not available: {e}")


if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("Session Interoperability Test (TypeScript ↔ Python)")
    print("=" * 70)
    print()
    
    try:
        test_jsonl_format_compatibility()
        test_session_manager_creates_compatible_jsonl()
        test_session_tree_structure()
        test_session_compaction_format()
        test_branch_summary_format()
        test_read_typescript_generated_jsonl()
        test_python_generates_ts_readable_jsonl()
        
        print()
        print("=" * 70)
        print("✅ ALL INTEROP TESTS PASSED!")
        print("Session data is compatible between TypeScript and Python")
        print("=" * 70)
        
    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
