"""Seeds Bellworth Home's product master into Firestore.

Stands in for a nightly ERP sync. Run once before the first autonomous pass.
"""

from google.cloud import firestore

INVENTORY = {
    "SKU-4471": {"name": "Cast iron skillet, 26cm", "supplier": "Kettleworth Foundry",
                 "on_hand": 42, "weekly_sales": 38, "reorder_point": 120, "unit_cost": 25},
    "SKU-9902": {"name": "Stoneware mixing bowl set", "supplier": "Northwind Ceramics",
                 "on_hand": 18, "weekly_sales": 22, "reorder_point": 90, "unit_cost": 34},
    "SKU-2260": {"name": "Bamboo chopping board, large", "supplier": "Kettleworth Foundry",
                 "on_hand": 310, "weekly_sales": 26, "reorder_point": 80, "unit_cost": 12},
    "SKU-7815": {"name": "Stainless steel stockpot, 8L", "supplier": "Northwind Ceramics",
                 "on_hand": 64, "weekly_sales": 9, "reorder_point": 40, "unit_cost": 48},
    "SKU-3390": {"name": "Enamel casserole dish, 4L", "supplier": "Kettleworth Foundry",
                 "on_hand": 7, "weekly_sales": 15, "reorder_point": 60, "unit_cost": 39},
}

if __name__ == "__main__":
    db = firestore.Client.from_service_account_json("firebase-key.json")
    for sku, data in INVENTORY.items():
        db.collection("inventory").document(sku).set(data)
    print(f"seeded {len(INVENTORY)} SKUs")
