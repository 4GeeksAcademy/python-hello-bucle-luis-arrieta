import csv
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError


PRODUCTS_PATH = Path(__file__).resolve().parents[1] / "products.csv"
CSV_FIELDS = ["id", "name", "quantity", "unit"]
INVENTORY_LOCK = Lock()


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1)
    quantity: float = Field(ge=0, allow_inf_nan=False, strict=True)
    unit: str = Field(min_length=1)


class Product(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True, extra="forbid")

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    quantity: float = Field(ge=0, allow_inf_nan=False)
    unit: str = Field(min_length=1)


class InventoryStorageError(Exception):
    pass


def read_inventory(path: Path) -> list[Product]:
    try:
        with path.open(encoding="utf-8", newline="") as inventory_file:
            reader = csv.DictReader(inventory_file, strict=True)
            if reader.fieldnames is None:
                return []
            if reader.fieldnames != CSV_FIELDS:
                raise ValueError("Invalid inventory CSV header")

            products = []
            product_ids = set()
            for row in reader:
                product = Product.model_validate(row)
                if product.id in product_ids:
                    raise ValueError("Duplicate product ID")
                product_ids.add(product.id)
                products.append(product)
            return products
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, csv.Error, ValueError, ValidationError) as error:
        raise InventoryStorageError("Could not read inventory CSV") from error


def write_inventory(path: Path, products: list[Product]) -> None:
    if len({product.id for product in products}) != len(products):
        raise InventoryStorageError("Duplicate product ID")

    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as inventory_file:
            temporary_path = Path(inventory_file.name)
            writer = csv.DictWriter(inventory_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(product.model_dump() for product in products)
        os.replace(temporary_path, path)
    except (OSError, UnicodeError, csv.Error) as error:
        raise InventoryStorageError("Could not write inventory CSV") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def get_inventory_path() -> Path:
    return PRODUCTS_PATH


app = FastAPI(title="Coffee Shop Inventory")


@app.get("/inventory", response_model=list[Product])
def list_inventory(path: Path = Depends(get_inventory_path)) -> list[Product]:
    try:
        return read_inventory(path)
    except InventoryStorageError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
@app.post("/inventory", response_model=Product, status_code=201)
def create_product(
    data: ProductCreate, path: Path = Depends(get_inventory_path)
) -> Product:
    try:
        with INVENTORY_LOCK:
            products = read_inventory(path)
            product_id = max((product.id for product in products), default=0) + 1
            product = Product(id=product_id, **data.model_dump())
            write_inventory(path, [*products, product])
        return product
    except InventoryStorageError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
