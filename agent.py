import json
import math
import os
from collections.abc import Callable, Mapping
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError


load_dotenv()

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 5.0
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MAX_AGENT_ITERATIONS = 8

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_inventory",
            "description": "List every product currently in the inventory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product",
            "description": "Add a product with its name, quantity, and unit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name."},
                    "quantity": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Starting stock quantity.",
                    },
                    "unit": {"type": "string", "description": "Stock unit."},
                },
                "required": ["name", "quantity", "unit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_stock",
            "description": "Change a product's stock by a positive or negative delta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "ID of the product to update.",
                    },
                    "delta": {
                        "type": "number",
                        "description": "Positive to add stock, negative to remove it.",
                    },
                },
                "required": ["product_id", "delta"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_inventory_alerts",
            "description": "List products below a stock threshold; defaults to 10 units.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Alert when stock is strictly below this value.",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_ARGUMENTS = {
    "list_inventory": (set(), set()),
    "create_product": (
        {"name", "quantity", "unit"},
        {"name", "quantity", "unit"},
    ),
    "adjust_stock": ({"product_id", "delta"}, {"product_id", "delta"}),
    "list_inventory_alerts": (set(), {"threshold"}),
}


def _json_result(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _argument_error(message: str) -> str:
    return _json_result({"error": "Invalid tool arguments", "detail": message})


def _http_error_result(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text

    detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
    return _json_result(
        {
            "error": "Inventory API request failed",
            "status_code": response.status_code,
            "detail": detail,
        }
    )


def _get_api_base_url(base_url: str | None = None) -> str:
    return (base_url or os.getenv("API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")


def dispatch_tool(
    tool_name: str,
    arguments: Mapping[str, Any],
    *,
    base_url: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    """Call one of the inventory API endpoints and return JSON for the LLM."""
    if tool_name not in TOOL_ARGUMENTS:
        return _json_result({"error": f"Unknown tool: {tool_name}"})
    if not isinstance(arguments, Mapping):
        return _argument_error("Arguments must be a JSON object")

    required, allowed = TOOL_ARGUMENTS[tool_name]
    missing = required - arguments.keys()
    unexpected = arguments.keys() - allowed
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"Missing fields: {', '.join(sorted(missing))}")
        if unexpected:
            details.append(f"Unexpected fields: {', '.join(sorted(unexpected))}")
        return _argument_error("; ".join(details))

    if tool_name == "adjust_stock":
        product_id = arguments["product_id"]
        if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id < 1:
            return _argument_error("product_id must be a positive integer")
        method = "PATCH"
        path = f"/inventory/{product_id}"
        request_options = {"json": {"delta": arguments["delta"]}}
    elif tool_name == "create_product":
        method = "POST"
        path = "/inventory"
        request_options = {"json": dict(arguments)}
    elif tool_name == "list_inventory_alerts":
        method = "GET"
        path = "/inventory/alerts"
        request_options = (
            {"params": {"threshold": arguments["threshold"]}}
            if "threshold" in arguments
            else {}
        )
    else:
        method = "GET"
        path = "/inventory"
        request_options = {}

    api_base_url = _get_api_base_url(base_url)
    url = f"{api_base_url}{path}"

    try:
        if client is None:
            with httpx.Client(timeout=API_TIMEOUT_SECONDS) as api_client:
                response = api_client.request(method, url, **request_options)
        else:
            response = client.request(method, url, **request_options)
        response.raise_for_status()
        return _json_result(response.json())
    except httpx.TimeoutException:
        return _json_result({"error": "Inventory API request timed out"})
    except httpx.HTTPStatusError as error:
        return _http_error_result(error.response)
    except httpx.RequestError:
        return _json_result({"error": "Could not reach the inventory API"})
    except (TypeError, ValueError, OverflowError):
        return _argument_error("Arguments must contain valid JSON values")


class AgentConfigurationError(RuntimeError):
    pass


class APIUnavailableError(RuntimeError):
    pass


class AgentProviderError(RuntimeError):
    pass


class AgentLoopLimitError(RuntimeError):
    pass


def create_llm_client() -> tuple[OpenAI, str]:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "").strip()
    if not api_key:
        raise AgentConfigurationError("GROQ_API_KEY is not configured")
    if not model:
        raise AgentConfigurationError("GROQ_MODEL is not configured")
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL), model


def get_max_agent_iterations() -> int:
    value = os.getenv("AGENT_MAX_ITERATIONS", str(DEFAULT_MAX_AGENT_ITERATIONS))
    try:
        max_iterations = int(value)
    except ValueError as error:
        raise AgentConfigurationError(
            "AGENT_MAX_ITERATIONS must be a positive integer"
        ) from error
    if max_iterations < 1:
        raise AgentConfigurationError("AGENT_MAX_ITERATIONS must be a positive integer")
    return max_iterations


def check_api_available(
    *, base_url: str | None = None, client: httpx.Client | None = None
) -> None:
    url = f"{_get_api_base_url(base_url)}/inventory"
    try:
        if client is None:
            with httpx.Client(timeout=API_TIMEOUT_SECONDS) as api_client:
                response = api_client.get(url)
        else:
            response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise APIUnavailableError(
            f"Inventory API returned HTTP {error.response.status_code}"
        ) from error
    except httpx.TimeoutException as error:
        raise APIUnavailableError("Inventory API health check timed out") from error
    except httpx.RequestError as error:
        raise APIUnavailableError("Could not reach the inventory API") from error


def run_agent_turn(
    user_message: str,
    llm_client: OpenAI,
    model: str,
    *,
    messages: list[dict[str, Any]] | None = None,
    max_iterations: int = DEFAULT_MAX_AGENT_ITERATIONS,
    tool_executor: Callable[[str, Mapping[str, Any]], str] = dispatch_tool,
) -> str:
    if not user_message.strip():
        raise ValueError("User message cannot be empty")
    if max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")

    conversation = messages if messages is not None else []
    conversation.append({"role": "user", "content": user_message})

    for _iteration in range(max_iterations):
        try:
            completion = llm_client.chat.completions.create(
                model=model,
                messages=conversation,
                tools=TOOLS,
                tool_choice="auto",
            )
        except OpenAIError as error:
            raise AgentProviderError("The Groq request failed") from error

        if not completion.choices:
            raise AgentProviderError("The LLM returned no response choices")

        response_message = completion.choices[0].message
        tool_calls = response_message.tool_calls or []
        assistant_message = {
            "role": "assistant",
            "content": response_message.content,
        }

        if not tool_calls:
            conversation.append(assistant_message)
            return response_message.content or ""

        assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ]
        conversation.append(assistant_message)

        for tool_call in tool_calls:
            if not tool_call.id:
                raise AgentProviderError("The LLM returned a tool call without an ID")

            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                result = _argument_error("Tool arguments are not valid JSON")
            else:
                if not isinstance(arguments, dict):
                    result = _argument_error("Tool arguments must be a JSON object")
                else:
                    try:
                        result = tool_executor(tool_call.function.name, arguments)
                    except Exception:
                        result = _json_result({"error": "Tool execution failed"})

            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result,
                }
            )

    raise AgentLoopLimitError(
        f"The agent reached its limit of {max_iterations} tool iterations"
    )


def main() -> int:
    try:
        llm_client, model = create_llm_client()
        max_iterations = get_max_agent_iterations()
    except AgentConfigurationError as error:
        print(f"Configuration error: {error}")
        return 1

    try:
        check_api_available()
    except APIUnavailableError as error:
        print(f"Inventory API unavailable: {error}")
        return 1

    conversation: list[dict[str, Any]] = []
    print("Inventory agent ready. Type /exit to quit.")
    while True:
        try:
            user_message = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            return 0

        if user_message.strip().lower() in {"/exit", "exit", "quit"}:
            return 0
        if not user_message.strip():
            continue

        try:
            answer = run_agent_turn(
                user_message,
                llm_client,
                model,
                messages=conversation,
                max_iterations=max_iterations,
            )
        except AgentProviderError as error:
            print(f"Agent request failed: {error}")
        except AgentLoopLimitError as error:
            print(f"Agent stopped: {error}")
        except KeyboardInterrupt:
            print("\nSession ended.")
            return 0
        else:
            print(f"Agent: {answer}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())