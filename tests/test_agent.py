import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAIError

import agent as agent_module
from agent import (
    API_TIMEOUT_SECONDS,
    DEFAULT_API_BASE_URL,
    DEFAULT_MAX_AGENT_ITERATIONS,
    GROQ_BASE_URL,
    TOOLS,
    APIUnavailableError,
    AgentConfigurationError,
    AgentLoopLimitError,
    AgentProviderError,
    check_api_available,
    create_llm_client,
    dispatch_tool,
    get_max_agent_iterations,
    run_agent_turn,
)


def test_tools_define_all_inventory_operations_with_typed_parameters():
    functions = {tool["function"]["name"]: tool["function"] for tool in TOOLS}

    assert set(functions) == {
        "list_inventory",
        "create_product",
        "adjust_stock",
        "list_inventory_alerts",
    }
    assert all(tool["type"] == "function" for tool in TOOLS)
    assert all(function["description"] for function in functions.values())
    assert all(
        function["parameters"]["type"] == "object"
        and function["parameters"]["additionalProperties"] is False
        for function in functions.values()
    )
    assert functions["create_product"]["parameters"]["required"] == [
        "name",
        "quantity",
        "unit",
    ]
    assert functions["adjust_stock"]["parameters"]["properties"]["delta"]["type"] == "number"
    assert functions["list_inventory_alerts"]["parameters"]["properties"]["threshold"]["type"] == "number"


@pytest.mark.parametrize(
    ("name", "arguments", "method", "path", "expected_body", "expected_params"),
    [
        ("list_inventory", {}, "GET", "/inventory", None, {}),
        (
            "create_product",
            {"name": "Coffee", "quantity": 2.5, "unit": "kg"},
            "POST",
            "/inventory",
            {"name": "Coffee", "quantity": 2.5, "unit": "kg"},
            {},
        ),
        (
            "adjust_stock",
            {"product_id": 7, "delta": -1.5},
            "PATCH",
            "/inventory/7",
            {"delta": -1.5},
            {},
        ),
        (
            "list_inventory_alerts",
            {"threshold": 4},
            "GET",
            "/inventory/alerts",
            None,
            {"threshold": "4"},
        ),
    ],
)
def test_dispatch_tool_maps_name_to_expected_api_request(
    name, arguments, method, path, expected_body, expected_params
):
    requests = []

    def handle_request(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handle_request)
    with httpx.Client(transport=transport) as client:
        result = dispatch_tool(
            name,
            arguments,
            base_url="http://inventory.test/",
            client=client,
        )

    assert json.loads(result) == {"ok": True}
    assert len(requests) == 1
    request = requests[0]
    assert request.method == method
    assert request.url.path == path
    assert dict(request.url.params) == expected_params
    if expected_body is None:
        assert request.content == b""
    else:
        assert json.loads(request.content) == expected_body


def test_alert_tool_omits_threshold_to_use_api_default():
    requests = []
    transport = httpx.MockTransport(
        lambda request: requests.append(request) or httpx.Response(200, json=[])
    )
    with httpx.Client(transport=transport) as client:
        result = dispatch_tool("list_inventory_alerts", {}, client=client)

    assert json.loads(result) == []
    assert requests[0].url == f"{DEFAULT_API_BASE_URL}/inventory/alerts"


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("unknown_tool", {}),
        ("list_inventory", {"unexpected": True}),
        ("create_product", {"name": "Coffee", "quantity": 1}),
        (
            "create_product",
            {"name": "Coffee", "quantity": 1, "unit": "kg", "id": 7},
        ),
        ("adjust_stock", {"product_id": 0, "delta": 1}),
        ("adjust_stock", {"product_id": True, "delta": 1}),
        ("list_inventory", None),
    ],
)
def test_dispatch_tool_rejects_unknown_or_invalid_arguments(name, arguments):
    result = dispatch_tool(name, arguments)

    assert json.loads(result)["error"]


def test_dispatch_tool_returns_api_status_and_detail():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            404, json={"detail": "Product not found"}, request=request
        )
    )
    with httpx.Client(transport=transport) as client:
        result = dispatch_tool("adjust_stock", {"product_id": 7, "delta": 1}, client=client)

    assert json.loads(result) == {
        "error": "Inventory API request failed",
        "status_code": 404,
        "detail": "Product not found",
    }


def test_dispatch_tool_reports_timeout():
    def raise_timeout(request):
        raise httpx.ReadTimeout("request timed out", request=request)

    transport = httpx.MockTransport(raise_timeout)
    with httpx.Client(transport=transport) as client:
        result = dispatch_tool("list_inventory", {}, client=client)

    assert json.loads(result) == {"error": "Inventory API request timed out"}


def test_dispatch_tool_reports_connection_errors():
    def raise_connection_error(request):
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(raise_connection_error)
    with httpx.Client(transport=transport) as client:
        result = dispatch_tool("list_inventory", {}, client=client)

    assert json.loads(result) == {"error": "Could not reach the inventory API"}


def test_default_http_client_has_a_finite_timeout():
    assert 0 < API_TIMEOUT_SECONDS <= 30


def make_tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def make_llm_response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        self.calls.append(
            {
                "model": request["model"],
                "messages": deepcopy(request["messages"]),
                "tools": request["tools"],
                "tool_choice": request["tool_choice"],
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def test_run_agent_turn_returns_final_response_and_keeps_session_history():
    history = [{"role": "system", "content": "Inventory assistant"}]
    llm_client = FakeLLM(make_llm_response("You have 4 products."))

    answer = run_agent_turn("Show my inventory", llm_client, "test-model", messages=history)

    assert answer == "You have 4 products."
    assert [message["role"] for message in history] == [
        "system",
        "user",
        "assistant",
    ]
    assert llm_client.calls[0]["model"] == "test-model"
    assert llm_client.calls[0]["tools"] == TOOLS
    assert llm_client.calls[0]["tool_choice"] == "auto"


def test_run_agent_turn_executes_tool_and_returns_to_llm_with_matching_call_id():
    llm_client = FakeLLM(
        make_llm_response(
            tool_calls=[
                make_tool_call("call-inventory-1", "list_inventory", {})
            ]
        ),
        make_llm_response("There are 2 products."),
    )
    dispatched = []

    def execute_tool(name, arguments):
        dispatched.append((name, arguments))
        return '[{"id":1},{"id":2}]'

    history = []
    answer = run_agent_turn(
        "List inventory",
        llm_client,
        "test-model",
        messages=history,
        tool_executor=execute_tool,
    )

    assert answer == "There are 2 products."
    assert dispatched == [("list_inventory", {})]
    assert history[1]["tool_calls"][0]["id"] == "call-inventory-1"
    assert history[2] == {
        "role": "tool",
        "tool_call_id": "call-inventory-1",
        "name": "list_inventory",
        "content": '[{"id":1},{"id":2}]',
    }
    assert [message["role"] for message in llm_client.calls[1]["messages"]] == [
        "user",
        "assistant",
        "tool",
    ]


def test_run_agent_turn_handles_multiple_tool_calls_in_one_response():
    llm_client = FakeLLM(
        make_llm_response(
            tool_calls=[
                make_tool_call("call-list", "list_inventory", {}),
                make_tool_call(
                    "call-alerts", "list_inventory_alerts", {"threshold": 5}
                ),
            ]
        ),
        make_llm_response("Inventory and alerts checked."),
    )
    dispatched = []

    def execute_tool(name, arguments):
        dispatched.append((name, arguments))
        return "{}"

    answer = run_agent_turn(
        "Check inventory and alerts",
        llm_client,
        "test-model",
        tool_executor=execute_tool,
    )

    assert answer == "Inventory and alerts checked."
    assert dispatched == [
        ("list_inventory", {}),
        ("list_inventory_alerts", {"threshold": 5}),
    ]
    tool_messages = [
        message for message in llm_client.calls[1]["messages"] if message["role"] == "tool"
    ]
    assert [message["tool_call_id"] for message in tool_messages] == [
        "call-list",
        "call-alerts",
    ]


def test_run_agent_turn_supports_add_then_check_alerts_across_iterations():
    llm_client = FakeLLM(
        make_llm_response(
            tool_calls=[
                make_tool_call(
                    "call-create",
                    "create_product",
                    {"name": "Coffee", "quantity": 2, "unit": "kg"},
                )
            ]
        ),
        make_llm_response(
            tool_calls=[
                make_tool_call(
                    "call-alerts", "list_inventory_alerts", {"threshold": 10}
                )
            ]
        ),
        make_llm_response("Coffee was added and appears in low-stock alerts."),
    )
    dispatched = []

    def execute_tool(name, arguments):
        dispatched.append((name, arguments))
        return '{"ok":true}'

    answer = run_agent_turn(
        "Add coffee and check low-stock alerts",
        llm_client,
        "test-model",
        tool_executor=execute_tool,
    )

    assert answer == "Coffee was added and appears in low-stock alerts."
    assert dispatched == [
        ("create_product", {"name": "Coffee", "quantity": 2, "unit": "kg"}),
        ("list_inventory_alerts", {"threshold": 10}),
    ]
    assert len(llm_client.calls) == 3
    assert [message["tool_call_id"] for message in llm_client.calls[2]["messages"] if message["role"] == "tool"] == [
        "call-create",
        "call-alerts",
    ]


def test_run_agent_turn_returns_invalid_tool_json_to_the_llm():
    malformed_call = SimpleNamespace(
        id="call-malformed",
        function=SimpleNamespace(name="create_product", arguments="{"),
    )
    llm_client = FakeLLM(
        make_llm_response(tool_calls=[malformed_call]),
        make_llm_response("I could not parse that request."),
    )
    executor_calls = []

    answer = run_agent_turn(
        "Add a product",
        llm_client,
        "test-model",
        tool_executor=lambda name, arguments: executor_calls.append(name) or "{}",
    )

    assert answer == "I could not parse that request."
    assert executor_calls == []
    tool_result = llm_client.calls[1]["messages"][-1]
    assert tool_result["tool_call_id"] == "call-malformed"
    assert json.loads(tool_result["content"])["error"] == "Invalid tool arguments"


def test_run_agent_turn_enforces_iteration_limit():
    llm_client = FakeLLM(
        make_llm_response(
            tool_calls=[make_tool_call("call-1", "list_inventory", {})]
        )
    )

    with pytest.raises(AgentLoopLimitError, match="limit of 1"):
        run_agent_turn(
            "List inventory",
            llm_client,
            "test-model",
            max_iterations=1,
            tool_executor=lambda name, arguments: "[]",
        )


def test_run_agent_turn_converts_provider_errors():
    llm_client = FakeLLM(OpenAIError("provider unavailable"))

    with pytest.raises(AgentProviderError, match="Groq request failed"):
        run_agent_turn("Hello", llm_client, "test-model")


def test_run_agent_turn_converts_tool_executor_exceptions_to_tool_results():
    llm_client = FakeLLM(
        make_llm_response(
            tool_calls=[make_tool_call("call-failure", "list_inventory", {})]
        ),
        make_llm_response("The inventory API is unavailable."),
    )

    answer = run_agent_turn(
        "List inventory",
        llm_client,
        "test-model",
        tool_executor=lambda name, arguments: (_ for _ in ()).throw(RuntimeError()),
    )

    assert answer == "The inventory API is unavailable."
    error_result = json.loads(llm_client.calls[1]["messages"][-1]["content"])
    assert error_result == {"error": "Tool execution failed"}


@pytest.mark.parametrize("user_message", ["", "   "])
def test_run_agent_turn_rejects_blank_user_messages(user_message):
    with pytest.raises(ValueError, match="cannot be empty"):
        run_agent_turn(user_message, FakeLLM(), "test-model")


def test_create_llm_client_uses_groq_and_requires_credentials(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    constructor_calls = []
    client = object()

    def fake_openai(**kwargs):
        constructor_calls.append(kwargs)
        return client

    monkeypatch.setattr(agent_module, "OpenAI", fake_openai)

    created_client, model = create_llm_client()

    assert created_client is client
    assert model == "test-model"
    assert constructor_calls == [
        {"api_key": "test-key", "base_url": GROQ_BASE_URL}
    ]


@pytest.mark.parametrize(
    ("api_key", "model", "missing_setting"),
    [("", "test-model", "GROQ_API_KEY"), ("test-key", "", "GROQ_MODEL")],
)
def test_create_llm_client_rejects_missing_configuration(
    monkeypatch, api_key, model, missing_setting
):
    monkeypatch.setenv("GROQ_API_KEY", api_key)
    monkeypatch.setenv("GROQ_MODEL", model)

    with pytest.raises(AgentConfigurationError, match=missing_setting):
        create_llm_client()


@pytest.mark.parametrize(
    ("value", "expected"), [(None, DEFAULT_MAX_AGENT_ITERATIONS), ("3", 3)]
)
def test_get_max_agent_iterations(value, expected, monkeypatch):
    if value is None:
        monkeypatch.delenv("AGENT_MAX_ITERATIONS", raising=False)
    else:
        monkeypatch.setenv("AGENT_MAX_ITERATIONS", value)

    assert get_max_agent_iterations() == expected


@pytest.mark.parametrize("value", ["0", "-1", "many"])
def test_get_max_agent_iterations_rejects_invalid_values(value, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", value)

    with pytest.raises(AgentConfigurationError, match="positive integer"):
        get_max_agent_iterations()


def test_check_api_available_accepts_successful_health_check():
    requests = []
    transport = httpx.MockTransport(
        lambda request: requests.append(request)
        or httpx.Response(200, json=[], request=request)
    )
    with httpx.Client(transport=transport) as client:
        check_api_available(base_url="http://inventory.test", client=client)

    assert requests[0].method == "GET"
    assert requests[0].url.path == "/inventory"


def test_check_api_available_reports_http_errors():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, json={"detail": "broken"}, request=request)
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(APIUnavailableError, match="HTTP 500"):
            check_api_available(client=client)


def test_check_api_available_reports_connection_failures():
    def raise_connection_error(request):
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(raise_connection_error)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(APIUnavailableError, match="Could not reach"):
            check_api_available(client=client)


def test_main_runs_cli_and_preserves_history_between_user_turns(monkeypatch, capsys):
    llm_client = FakeLLM(
        make_llm_response("First answer."), make_llm_response("Second answer.")
    )
    monkeypatch.setattr(
        agent_module, "create_llm_client", lambda: (llm_client, "test-model")
    )
    monkeypatch.setattr(agent_module, "get_max_agent_iterations", lambda: 2)
    monkeypatch.setattr(agent_module, "check_api_available", lambda: None)
    user_messages = iter(["First question", "Second question", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(user_messages))

    exit_code = agent_module.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Agent: First answer." in output
    assert "Agent: Second answer." in output
    assert [message["role"] for message in llm_client.calls[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]


def test_main_exits_cleanly_on_eof(monkeypatch, capsys):
    llm_client = FakeLLM()
    monkeypatch.setattr(
        agent_module, "create_llm_client", lambda: (llm_client, "test-model")
    )
    monkeypatch.setattr(agent_module, "get_max_agent_iterations", lambda: 2)
    monkeypatch.setattr(agent_module, "check_api_available", lambda: None)

    def end_input(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", end_input)

    assert agent_module.main() == 0
    assert "Session ended." in capsys.readouterr().out


def test_main_stops_when_api_is_unavailable(monkeypatch, capsys):
    llm_client = FakeLLM()
    monkeypatch.setattr(
        agent_module, "create_llm_client", lambda: (llm_client, "test-model")
    )
    monkeypatch.setattr(agent_module, "get_max_agent_iterations", lambda: 2)

    def fail_api_check():
        raise APIUnavailableError("Could not reach the inventory API")

    monkeypatch.setattr(agent_module, "check_api_available", fail_api_check)

    assert agent_module.main() == 1
    assert "Inventory API unavailable" in capsys.readouterr().out
    assert llm_client.calls == []