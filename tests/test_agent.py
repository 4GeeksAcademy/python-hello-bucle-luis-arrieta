import json

import httpx
import pytest

from agent import API_TIMEOUT_SECONDS, DEFAULT_API_BASE_URL, TOOLS, dispatch_tool


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