"""End-to-end tests for agent execution

Tests the complete agent execution flow including:
- Turn execution
- Streaming responses
- Tool calling
- Multi-turn conversations
- Abort mechanism
- Event propagation
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from openclaw.agents.runtime import MultiProviderRuntime
from openclaw.agents.session import Session
from openclaw.agents.tools.base import AgentTool, ToolResult
from openclaw.agents.providers.base import LLMResponse
from openclaw.events import EventType


class MockTool(AgentTool):
    """Mock tool for testing"""
    
    def __init__(self, name: str = "test_tool"):
        self.name = name
        self.description = "A test tool"
        self.parameters = {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
        self.call_count = 0
    
    async def execute(self, params_or_input=None, **kwargs) -> ToolResult:
        """Execute the tool — supports both legacy (dict args) and named args."""
        self.call_count += 1
        if isinstance(params_or_input, dict):
            input_val = params_or_input.get("input", "")
        else:
            input_val = params_or_input or ""
        return ToolResult(
            success=True,
            output=f"Tool executed with: {input_val}",
            metadata={"call_count": self.call_count}
        )


class TestBasicTurnExecution:
    """Test basic turn execution"""
    
    @pytest.mark.asyncio
    async def test_basic_turn_non_streaming(self):
        """Test basic non-streaming turn execution"""
        # Create mock provider
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value={
            "content": "Hello! I'm the assistant.",
            "tool_calls": [],
            "usage": {"input_tokens": 10, "output_tokens": 20}
        })
        
        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        # Execute turn
        events = []
        async for event in runtime.run_turn(
            session=session,
            message="Hello",
            tools=[]
        ):
            events.append(event)
        
        # Verify we got events
        assert len(events) > 0
        
        # Verify session was updated
        assert len(session.messages) > 0
    
    @pytest.mark.asyncio
    async def test_turn_with_images(self):
        """Test turn execution with image inputs"""
        captured_messages = []

        async def mock_stream_with_images(*args, **kwargs):
            captured_messages.extend(kwargs.get("messages", args[0] if args else []))
            yield LLMResponse(type="text_delta", content="I see the image.")
            yield LLMResponse(type="message_stop", content=None)

        mock_provider = AsyncMock()
        mock_provider.stream = mock_stream_with_images

        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider

        session = Session(session_id="test-session-images")
        images = ["http://example.com/image.jpg"]

        events = []
        async for event in runtime.run_turn(
            session=session,
            message="What's in this image?",
            tools=[],
            images=images
        ):
            events.append(event)

        # Verify provider was called (stream was invoked)
        assert len(captured_messages) > 0 or len(events) > 0


class TestStreamingResponse:
    """Test streaming response generation"""
    
    @pytest.mark.asyncio
    async def test_streaming_text(self):
        """Test streaming text response"""
        async def mock_stream(*args, **kwargs):
            for text in ["Hello ", "world", "!"]:
                yield LLMResponse(type="text_delta", content=text)
            yield LLMResponse(type="message_stop", content=None)

        mock_provider = AsyncMock()
        mock_provider.stream = mock_stream

        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        text_events = []
        async for event in runtime.run_turn(session=session, message="Hi", tools=[]):
            if event.type == EventType.AGENT_TEXT or event.type == "text":
                text_events.append(event)
        
        # Verify we got text events
        assert len(text_events) > 0


class TestToolExecution:
    """Test tool calling functionality"""
    
    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """Test execution with single tool call"""
        test_tool = MockTool("test_tool")
        
        # Mock provider that returns a tool call then text
        async def mock_stream(*args, **kwargs):
            yield LLMResponse(
                type="tool_call",
                content=None,
                tool_calls=[{"name": "test_tool", "id": "call-1", "arguments": {"input": "test"}}],
            )
            yield LLMResponse(type="message_stop", content=None)

        mock_provider = AsyncMock()
        mock_provider.stream = mock_stream
        
        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        events = []
        async for event in runtime.run_turn(
            session=session,
            message="Use the test tool",
            tools=[test_tool]
        ):
            events.append(event)
        
        # Verify tool was called
        assert test_tool.call_count > 0
    
    @pytest.mark.asyncio
    async def test_multi_turn_tool_calls(self):
        """Test multiple tool calls across turns"""
        test_tool = MockTool("test_tool")
        
        mock_provider = AsyncMock()
        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        # First turn with tool call
        async def mock_stream_1(*args, **kwargs):
            yield LLMResponse(
                type="tool_call", content=None,
                tool_calls=[{"name": "test_tool", "id": "call-1", "arguments": {"input": "first"}}],
            )
            yield LLMResponse(type="message_stop", content=None)

        mock_provider.stream = mock_stream_1

        async for event in runtime.run_turn(
            session=session,
            message="First turn",
            tools=[test_tool]
        ):
            pass

        first_call_count = test_tool.call_count

        # Second turn with tool call
        async def mock_stream_2(*args, **kwargs):
            yield LLMResponse(
                type="tool_call", content=None,
                tool_calls=[{"name": "test_tool", "id": "call-2", "arguments": {"input": "second"}}],
            )
            yield LLMResponse(type="message_stop", content=None)

        mock_provider.stream = mock_stream_2
        
        async for event in runtime.run_turn(
            session=session,
            message="Second turn",
            tools=[test_tool]
        ):
            pass
        
        # Verify tool was called in both turns
        assert test_tool.call_count > first_call_count
    
    @pytest.mark.asyncio
    async def test_tool_execution_failure(self):
        """Test handling of tool execution failures"""
        class FailingTool(AgentTool):
            name = "failing_tool"
            description = "A tool that fails"
            parameters = {"type": "object", "properties": {}}
            
            async def execute(self, **kwargs) -> ToolResult:
                raise ValueError("Tool execution failed")
        
        failing_tool = FailingTool()
        
        async def mock_stream():
            yield {"type": "tool_use", "name": "failing_tool", "arguments": {}}
            yield {"type": "stop"}
        
        mock_provider = AsyncMock()
        mock_provider.stream = AsyncMock(return_value=mock_stream())
        
        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        # Should not raise, should handle error gracefully
        events = []
        async for event in runtime.run_turn(
            session=session,
            message="Use failing tool",
            tools=[failing_tool]
        ):
            events.append(event)
        
        # Verify we got an error event or tool_result event with failure
        # (depending on implementation)
        assert len(events) > 0


class TestAbortMechanism:
    """Test abort/cancellation mechanism"""
    
    @pytest.mark.asyncio
    async def test_abort_turn(self):
        """Test aborting a turn mid-execution"""
        # Create a slow mock stream
        async def slow_stream(*args, **kwargs):
            for i in range(100):
                await asyncio.sleep(0.01)
                yield LLMResponse(type="text_delta", content=f"chunk{i} ")

        mock_provider = AsyncMock()
        mock_provider.stream = slow_stream
        
        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        # Start turn in background
        turn_task = asyncio.create_task(
            self._collect_events(runtime.run_turn(session, "Test", []))
        )
        
        # Wait a bit then cancel
        await asyncio.sleep(0.05)
        turn_task.cancel()
        
        # Verify cancellation
        with pytest.raises(asyncio.CancelledError):
            await turn_task
    
    async def _collect_events(self, event_stream):
        """Helper to collect events from stream"""
        events = []
        async for event in event_stream:
            events.append(event)
        return events


class TestEventPropagation:
    """Test event emission and propagation"""
    
    @pytest.mark.asyncio
    async def test_event_emission(self):
        """Test that all expected events are emitted"""
        async def mock_stream_gen(*args, **kwargs):
            yield LLMResponse(type="text_delta", content="Response")
            yield LLMResponse(type="message_stop", content=None)

        mock_provider = AsyncMock()
        mock_provider.stream = mock_stream_gen

        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        # Collect all events
        events = []
        async for event in runtime.run_turn(session, "Test", []):
            events.append(event)
        
        # Verify we got a started event
        started_events = [e for e in events if e.type == EventType.AGENT_STARTED]
        assert len(started_events) > 0
        
        # Verify we got a turn complete event
        complete_events = [e for e in events if e.type == EventType.AGENT_TURN_COMPLETE]
        assert len(complete_events) > 0
    
    @pytest.mark.asyncio
    async def test_event_listener(self):
        """Test event listener registration and callbacks"""
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value={
            "content": "Response",
            "tool_calls": [],
            "usage": {}
        })
        
        runtime = MultiProviderRuntime(model="mock/test")
        runtime.provider = mock_provider
        
        # Register listener
        received_events = []
        
        async def listener(event):
            received_events.append(event)
        
        runtime.add_event_listener(listener)
        
        session = Session(session_id="test-session")
        
        # Execute turn
        async for event in runtime.run_turn(session, "Test", []):
            pass
        
        # Verify listener received events
        assert len(received_events) > 0


class TestQueueManagement:
    """Test queue management features"""
    
    @pytest.mark.asyncio
    async def test_queue_enabled(self):
        """Test runtime with queue management enabled"""
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value={
            "content": "Response",
            "tool_calls": [],
            "usage": {}
        })
        
        runtime = MultiProviderRuntime(
            model="mock/test",
            enable_queuing=True
        )
        runtime.provider = mock_provider
        
        session = Session(session_id="test-session")
        
        # Execute turn with queue
        events = []
        async for event in runtime.run_turn(session, "Test", []):
            events.append(event)
        
        # Verify execution completed
        assert len(events) > 0
        
        # Verify queue manager is present
        assert runtime.queue_manager is not None


class TestSteeringAndFollowup:
    """Test steering and follow-up message features"""
    
    @pytest.mark.asyncio
    async def test_steering_message_queue(self):
        """Test steering message queue"""
        runtime = MultiProviderRuntime(model="mock/test")
        
        # Add steering messages
        runtime.add_steering_message("Interrupt 1")
        runtime.add_steering_message("Interrupt 2")
        
        # Verify messages are queued
        assert len(runtime.steering_queue) == 2
        
        # Check messages
        msg1 = runtime.check_steering()
        assert msg1 == "Interrupt 1"
        assert len(runtime.steering_queue) == 1
        
        msg2 = runtime.check_steering()
        assert msg2 == "Interrupt 2"
        assert len(runtime.steering_queue) == 0
    
    @pytest.mark.asyncio
    async def test_followup_message_queue(self):
        """Test follow-up message queue"""
        runtime = MultiProviderRuntime(model="mock/test")
        
        # Add follow-up messages
        runtime.add_followup_message("Follow-up 1")
        runtime.add_followup_message("Follow-up 2")
        
        # Verify messages are queued
        assert len(runtime.followup_queue) == 2
        
        # Check messages
        msg1 = runtime.check_followup()
        assert msg1 == "Follow-up 1"
        
        msg2 = runtime.check_followup()
        assert msg2 == "Follow-up 2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
