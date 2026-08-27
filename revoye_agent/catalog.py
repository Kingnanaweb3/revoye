"""Bellworth Home — product catalogue.

Bellworth is a mid-sized home and kitchen retailer: around 2,400 SKUs across
eleven suppliers. Large enough that manual reordering breaks down, small enough
that there is no dedicated procurement team. That gap is what Revoyé fills.

This stands in for a real product master. A production deployment would read it
from the inventory system rather than a dict.
"""

CATALOG = {
    "SKU-4471": {"name": "Cast iron skillet, 26cm", "supplier": "Kettleworth Foundry"},
    "SKU-9902": {"name": "Stoneware mixing bowl set", "supplier": "Northwind Ceramics"},
    "SKU-2260": {"name": "Bamboo chopping board, large", "supplier": "Kettleworth Foundry"},
    "SKU-7815": {"name": "Stainless steel stockpot, 8L", "supplier": "Northwind Ceramics"},
}


def describe(sku: str) -> str:
    """Returns a readable product name for a SKU, or the SKU itself."""
    entry = CATALOG.get(sku)
    return f"{sku} ({entry['name']})" if entry else sku
