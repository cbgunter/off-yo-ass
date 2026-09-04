from decimal import Decimal

from oya.store.table import Entity, put_item, query_all


def test_put_item_accepts_native_floats(dynamodb_table):
    """boto3's DynamoDB resource API raises TypeError on a bare Python
    float ("Use Decimal types instead") — every other module in this app
    just writes ordinary floats and relies on put_item to convert them.
    This is a regression test for a real bug this caught: the first
    version of put_item passed attrs straight through and would have
    failed in production on the very first float-valued write."""
    put_item(Entity.WEIGHT, "2026-06-15", {"lbs": 181.4})

    items = query_all(Entity.WEIGHT)
    assert len(items) == 1
    # Decimal(str(181.4)) round-trips exactly; Decimal(181.4) would not
    # (binary floats can't represent 181.4 exactly) — that's the whole
    # reason _to_dynamodb_value converts via str(), not Decimal() directly.
    assert items[0]["lbs"] == Decimal("181.4")


def test_put_item_converts_floats_nested_in_lists_and_dicts(dynamodb_table):
    put_item(
        Entity.SUB,
        "test",
        {"subscription": {"keys": {"p256dh": "abc"}}, "scores": [1.5, 2.5]},
    )

    items = query_all(Entity.SUB)
    assert items[0]["scores"] == [Decimal("1.5"), Decimal("2.5")]
