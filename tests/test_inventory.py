import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import (
    CSV_FIELDS,
    InventoryStorageError,
    Product,
    app,
    get_inventory_path,
    read_inventory,
    write_inventory,
)


@pytest.fixture
def inventory_path(tmp_path):
    return tmp_path / "products.csv"


@pytest.fixture
def client(inventory_path):
    app.dependency_overrides[get_inventory_path] = lambda: inventory_path
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_missing_inventory_returns_empty_list(client, inventory_path):
    response = client.get("/inventory")

    assert response.status_code == 200
    assert response.json() == []
    assert not inventory_path.exists()


@pytest.mark.parametrize("content", ["", "id,name,quantity,unit\n"])
def test_empty_inventory_returns_empty_list(client, inventory_path, content):
    inventory_path.write_text(content, encoding="utf-8")

    response = client.get("/inventory")

    assert response.status_code == 200
    assert response.json() == []
    assert inventory_path.read_text(encoding="utf-8") == content


def test_inventory_reads_existing_csv_without_changing_ids(client, inventory_path):
    inventory_path.write_text(
        "id,name,quantity,unit\n7,Coffee beans,2.5,kg\n42,Milk,0,liters\n",
        encoding="utf-8",
    )
    original = inventory_path.read_bytes()
    expected = [
        {"id": 7, "name": "Coffee beans", "quantity": 2.5, "unit": "kg"},
        {"id": 42, "name": "Milk", "quantity": 0.0, "unit": "liters"},
    ]

    response = client.get("/inventory")
    with TestClient(app) as restarted_client:
        restarted_response = restarted_client.get("/inventory")

    assert response.status_code == restarted_response.status_code == 200
    assert response.json() == restarted_response.json() == expected
    assert inventory_path.read_bytes() == original


@pytest.mark.parametrize(
    "content",
    [
        "name,quantity,unit\nCoffee,1,kg\n",
        "id,name,quantity,unit\n1,Coffee,-1,kg\n",
        "id,name,quantity,unit\n1,Coffee,nan,kg\n",
        "id,name,quantity,unit\n1,Coffee,inf,kg\n",
        "id,name,quantity,unit\n1,Coffee,unknown,kg\n",
        "id,name,quantity,unit\n0,Coffee,1,kg\n",
        "id,name,quantity,unit\n1,   ,1,kg\n",
        "id,name,quantity,unit\n1,Coffee,1,\n",
        "id,name,quantity,unit\n1,Coffee,1\n",
        "id,name,quantity,unit\n1,Coffee,1,kg,extra\n",
        "id,name,quantity,unit\n1,Coffee,1,kg\n1,Milk,2,liters\n",
        'id,name,quantity,unit\n1,"Coffee,1,kg\n',
    ],
)
def test_corrupt_inventory_returns_error_without_data_loss(
    client, inventory_path, content
):
    inventory_path.write_text(content, encoding="utf-8")
    original = inventory_path.read_bytes()

    response = client.get("/inventory")

    assert response.status_code == 500
    assert response.json() == {"detail": "Could not read inventory CSV"}
    assert inventory_path.read_bytes() == original


def test_invalid_encoding_returns_error_without_data_loss(client, inventory_path):
    original = b"id,name,quantity,unit\n1,\xff,1,kg\n"
    inventory_path.write_bytes(original)

    response = client.get("/inventory")

    assert response.status_code == 500
    assert inventory_path.read_bytes() == original


def test_unreadable_inventory_returns_descriptive_error(client, inventory_path):
    inventory_path.mkdir()

    response = client.get("/inventory")

    assert response.status_code == 500
    assert response.json() == {"detail": "Could not read inventory CSV"}
    assert inventory_path.is_dir()


def test_write_inventory_round_trip_preserves_data(inventory_path):
    products = [
        Product(id=7, name='Coffee, "special"\nblend', quantity=2.5, unit="kg"),
        Product(id=42, name="Milk", quantity=0, unit="liters"),
    ]

    write_inventory(inventory_path, products)

    assert read_inventory(inventory_path) == products
    with inventory_path.open(encoding="utf-8", newline="") as inventory_file:
        assert next(csv.reader(inventory_file)) == CSV_FIELDS
    assert list(inventory_path.parent.iterdir()) == [inventory_path]


def test_write_empty_inventory_keeps_csv_header(inventory_path):
    write_inventory(inventory_path, [])

    assert read_inventory(inventory_path) == []
    assert inventory_path.read_text(encoding="utf-8").strip() == ",".join(CSV_FIELDS)


def test_failed_write_preserves_previous_inventory(inventory_path, monkeypatch):
    original = b"id,name,quantity,unit\n7,Coffee,1,kg\n"
    inventory_path.write_bytes(original)

    def fail_replace(source, destination):
        raise OSError("Simulated storage failure")

    monkeypatch.setattr("api.app.os.replace", fail_replace)

    with pytest.raises(InventoryStorageError, match="Could not write inventory CSV"):
        write_inventory(
            inventory_path, [Product(id=42, name="Milk", quantity=2, unit="liters")]
        )

    assert inventory_path.read_bytes() == original
    assert list(inventory_path.parent.iterdir()) == [inventory_path]


def test_duplicate_ids_are_not_written(inventory_path):
    product = Product(id=1, name="Coffee", quantity=1, unit="kg")

    with pytest.raises(InventoryStorageError, match="Duplicate product ID"):
        write_inventory(inventory_path, [product, product])

    assert not inventory_path.exists()


def test_default_inventory_path_does_not_depend_on_working_directory(
    tmp_path, monkeypatch
):
    expected = Path(__file__).resolve().parents[1] / "products.csv"
    monkeypatch.chdir(tmp_path)

    assert get_inventory_path() == expected
