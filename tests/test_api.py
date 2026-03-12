import unittest.mock as mock
import unittest

from api import AgentApi, _parse_sse_frame
import core.contracts.models as contract_models


class ParseSseFrameTest(unittest.TestCase):
    def test_parses_event_type_and_json_payload(self) -> None:
        parsed = _parse_sse_frame('event: thinking_step\ndata: {"label":"Working"}\n\n')

        self.assertEqual(parsed, {"label": "Working", "type": "thinking_step"})

    def test_wraps_non_json_payload_as_error_message(self) -> None:
        parsed = _parse_sse_frame("data: not-json\n\n")

        self.assertEqual(parsed["type"], "message")
        self.assertEqual(parsed["message"], "Failed to parse stream payload.")
        self.assertEqual(parsed["raw"], "not-json")


class AgentApiTest(unittest.IsolatedAsyncioTestCase):
    def test_list_available_models_returns_ui_safe_catalog(self) -> None:
        api = AgentApi(mock.Mock())

        payload = api.list_available_models()

        self.assertIn("models", payload)
        self.assertTrue(payload["models"])
        self.assertTrue(
            all(item["id"].startswith("mdl_") for item in payload["models"])
        )
        self.assertTrue(all("model_name" not in item for item in payload["models"]))

    async def test_stream_chat_events_forwards_stream_flag(self) -> None:
        async def fake_stream():
            yield 'event: assistant_message\ndata: {"text":"done"}\n\n'

        platform = mock.Mock()
        platform.stream_chat = mock.AsyncMock(
            return_value=("web.answer", "orchestrated", "session-1", fake_stream())
        )
        api = AgentApi(platform)

        _, mode, _, events_iter = await api.stream_chat_events(
            message="hello",
            agent_id="web.answer",
            mode="orchestrated",
            model_name="gemini-2.0-flash",
            user_id="api-user",
            session_id="session-1",
            stream=False,
        )
        events = [event async for event in events_iter]

        platform.stream_chat.assert_awaited_once_with(
            agent_id="web.answer",
            mode="orchestrated",
            model_name="gemini-2.0-flash",
            message="hello",
            user_id="api-user",
            session_id="session-1",
            history=None,
            stream=False,
        )
        self.assertEqual(mode, "orchestrated")
        self.assertEqual(events[0]["type"], "assistant_message")

    async def test_stream_chat_events_resolves_model_id(self) -> None:
        async def fake_stream():
            yield 'event: assistant_message\ndata: {"text":"done"}\n\n'

        model = contract_models.available_models()[0]
        platform = mock.Mock()
        platform.stream_chat = mock.AsyncMock(
            return_value=("web.answer", "direct", "session-2", fake_stream())
        )
        api = AgentApi(platform)

        await api.stream_chat_events(
            message="hello",
            agent_id="web.answer",
            model_id=model.id,
        )

        platform.stream_chat.assert_awaited_once_with(
            agent_id="web.answer",
            mode=None,
            model_name=model.model_name,
            message="hello",
            user_id="api-user",
            session_id=None,
            history=None,
            stream=True,
        )


if __name__ == "__main__":
    unittest.main()
