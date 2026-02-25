"""Verify system prompt alignment between TypeScript and Python implementations.

This test validates that openclaw-python generates system prompts that structurally
match the TypeScript implementation in openclaw.

To fully verify, you can manually compare outputs with the TypeScript version by:
1. Running the TypeScript version: node openclaw/scripts/test-system-prompt.js
2. Running this test: pytest tests/test_prompt_alignment_with_ts.py -v
"""
from pathlib import Path
from openclaw.agents.system_prompt import build_agent_system_prompt


def test_system_prompt_has_expected_sections():
    """Verify all expected sections are present in the generated prompt."""
    
    # Build a full prompt with typical parameters
    prompt = build_agent_system_prompt(
        workspace_dir=Path.cwd(),
        tool_names=["read_file", "write_file", "bash", "grep", "glob", "memory_search", "message"],
        user_timezone="America/New_York",
        prompt_mode="full",
        runtime_info={
            "agent_id": "test-agent",
            "channel": "telegram",
            "model": "claude-3-5-sonnet-20241022",
            "capabilities": ["inlineButtons"],
        },
        context_files=[
            {"path": "AGENTS.md", "content": "# Test Agent Context\n\nTest content for validation."},
        ],
        has_gateway=True,
    )
    
    # Expected sections (matching TypeScript order)
    expected_sections = [
        # 1. Identity (implicit, always present)
        "You are a personal assistant running inside OpenClaw",
        
        # 2. Tooling
        "## Tooling",
        
        # 3. Tool Call Style
        "## Tool Call Style",
        
        # 4. Safety
        "## Safety",
        
        # 5. CLI Quick Reference
        "## OpenClaw CLI Quick Reference",
        
        # 7. Memory (conditional - we provided memory_search)
        "## Memory Recall",
        
        # 11. Workspace
        "## Workspace",
        
        # 15. Time
        "## Current Date & Time",
        "Time zone: America/New_York",
        
        # 17. Reply Tags
        "## Reply Tags",
        
        # 18. Messaging
        "## Messaging",
        
        # 23. Project Context (we provided AGENTS.md)
        "# Project Context",
        "## AGENTS.md",
        
        # 26. Runtime
        "## Runtime",
    ]
    
    for section in expected_sections:
        assert section in prompt, f"Missing expected section: {section}"
    
    print("✅ All expected sections present")


def test_section_order_matches_typescript():
    """Verify sections appear in the correct order (matching TS 1-26 sequence)."""
    
    prompt = build_agent_system_prompt(
        workspace_dir=Path.cwd(),
        tool_names=["read_file", "write_file", "bash", "memory_search"],
        user_timezone="UTC",
        prompt_mode="full",
    )
    
    # Find indices of key sections
    sections_to_check = [
        ("Identity", "You are a personal assistant"),
        ("Tooling", "## Tooling"),
        ("Tool Call Style", "## Tool Call Style"),
        ("Safety", "## Safety"),
        ("CLI Quick Reference", "## CLI Quick Reference"),
        ("Memory", "## Memory Recall"),
        ("Workspace", "## Workspace"),
        ("Reply Tags", "## Reply Tags"),
        ("Messaging", "## Messaging"),
        ("Runtime", "## Runtime"),
    ]
    
    indices = []
    for name, marker in sections_to_check:
        idx = prompt.find(marker)
        if idx >= 0:
            indices.append((name, idx))
    
    # Verify sections appear in increasing order
    for i in range(len(indices) - 1):
        current_name, current_idx = indices[i]
        next_name, next_idx = indices[i + 1]
        assert current_idx < next_idx, (
            f"Section order violation: {current_name} (idx={current_idx}) "
            f"should come before {next_name} (idx={next_idx})"
        )
    
    print("✅ Section order matches TypeScript sequence")


def test_minimal_mode_excludes_correct_sections():
    """Verify minimal mode excludes non-essential sections."""
    
    prompt = build_agent_system_prompt(
        workspace_dir=Path.cwd(),
        tool_names=["read_file", "write_file"],
        prompt_mode="minimal",
        runtime_info={
            "agent_id": "test-subagent",
            "model": "claude-3-5-sonnet-20241022",
        },
    )
    
    # Sections that should NOT appear in minimal mode
    excluded_in_minimal = [
        "## Skills",
        "## Memory Recall",
        "## User Identity",
        "## Reply Tags",
        "## Messaging",
    ]
    
    for section in excluded_in_minimal:
        assert section not in prompt, f"Section should be excluded in minimal mode: {section}"
    
    # Sections that SHOULD appear in minimal mode
    required_in_minimal = [
        "You are a personal assistant",
        "## Tooling",
        "## Workspace",
        "## Runtime",
    ]
    
    for section in required_in_minimal:
        assert section in prompt, f"Section should be present in minimal mode: {section}"
    
    print("✅ Minimal mode sections correct")


def test_none_mode_returns_identity_only():
    """Verify 'none' mode returns only the identity line."""
    
    prompt = build_agent_system_prompt(
        workspace_dir=Path.cwd(),
        prompt_mode="none",
    )
    
    assert prompt == "You are a personal assistant running inside OpenClaw."
    print("✅ 'None' mode returns identity only")


def test_inbound_meta_functions_work():
    """Verify inbound meta prompt functions work correctly."""
    from openclaw.auto_reply.inbound_meta import (
        build_inbound_meta_system_prompt,
        build_inbound_user_context_prefix,
    )
    from openclaw.auto_reply.inbound_context import MsgContext
    
    # Create a test context (group chat scenario)
    ctx = MsgContext(
        Body="Test message",
        SessionKey="agent:main:telegram:group:123",
        ChatType="group",
        SenderId="456",
        SenderName="Test User",
        SenderUsername="testuser",
        GroupSubject="Test Group",
        MessageSid="msg-789",
        WasMentioned=True,
    )
    
    # Build inbound meta system prompt
    meta_prompt = build_inbound_meta_system_prompt(ctx)
    
    # Verify trusted metadata structure
    assert "## Inbound Context (trusted metadata)" in meta_prompt
    assert "openclaw.inbound_meta.v1" in meta_prompt
    assert "msg-789" in meta_prompt  # message_id
    assert "456" in meta_prompt  # sender_id
    assert "group" in meta_prompt  # chat_type
    assert "was_mentioned" in meta_prompt
    
    # Verify NO untrusted strings in system prompt
    assert "Test User" not in meta_prompt
    assert "testuser" not in meta_prompt
    assert "Test Group" not in meta_prompt
    
    print("✅ Inbound meta system prompt correct (trusted metadata only)")
    
    # Build inbound user context prefix
    user_context = build_inbound_user_context_prefix(ctx)
    
    # Verify untrusted context structure
    assert "Conversation info (untrusted metadata):" in user_context
    assert "Sender (untrusted metadata):" in user_context
    assert "Test User" in user_context  # Untrusted strings OK here
    assert "testuser" in user_context
    assert "Test Group" in user_context
    
    print("✅ Inbound user context prefix correct (untrusted metadata)")


def test_inbound_meta_reply_context():
    """Verify reply and forward context are included correctly."""
    from openclaw.auto_reply.inbound_meta import build_inbound_user_context_prefix
    from openclaw.auto_reply.inbound_context import MsgContext
    
    # Create context with reply and forward info
    ctx = MsgContext(
        Body="Reply message",
        SessionKey="agent:main:telegram:dm:123",
        ChatType="direct",
        ReplyToBody="Original message",
        ReplyToSender="Original Sender",
        ReplyToIsQuote=True,
        ForwardedFrom="Forward Source",
        ForwardedFromType="user",
        ForwardedDate=1234567890000,
    )
    
    user_context = build_inbound_user_context_prefix(ctx)
    
    # Verify reply context
    assert "Replied message (untrusted, for context):" in user_context
    assert "Original message" in user_context
    assert "Original Sender" in user_context
    assert "is_quote" in user_context
    
    # Verify forwarded context
    assert "Forwarded message context (untrusted metadata):" in user_context
    assert "Forward Source" in user_context
    assert "1234567890000" in user_context
    
    print("✅ Reply and forward context included correctly")


def test_inbound_meta_history():
    """Verify chat history is included correctly."""
    from openclaw.auto_reply.inbound_meta import build_inbound_user_context_prefix
    from openclaw.auto_reply.inbound_context import MsgContext
    
    # Create context with history
    ctx = MsgContext(
        Body="Current message",
        SessionKey="agent:main:telegram:group:123",
        ChatType="group",
        InboundHistory=[
            {"sender": "User1", "timestamp": 1000, "body": "Hello"},
            {"sender": "User2", "timestamp": 2000, "body": "Hi there"},
        ],
    )
    
    user_context = build_inbound_user_context_prefix(ctx)
    
    # Verify history block
    assert "Chat history since last reply (untrusted, for context):" in user_context
    assert "User1" in user_context
    assert "Hello" in user_context
    assert "User2" in user_context
    assert "Hi there" in user_context
    
    print("✅ Chat history included correctly")


if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("System Prompt Alignment Verification")
    print("=" * 70)
    print()
    
    try:
        test_system_prompt_has_expected_sections()
        test_section_order_matches_typescript()
        test_minimal_mode_excludes_correct_sections()
        test_none_mode_returns_identity_only()
        test_inbound_meta_functions_work()
        test_inbound_meta_reply_context()
        test_inbound_meta_history()
        
        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED - Prompt alignment verified!")
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
