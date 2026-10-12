import json
import math
import os
from collections.abc import Mapping
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv()

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 5.0

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

    api_base_url = (base_url or os.getenv("API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
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