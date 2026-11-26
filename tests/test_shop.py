"""The stall (prompt 08 §3): buying is INSERT ... SELECT through the guard, with checks."""

import pytest

from magic.guard import Miscast
from magic.shop import Shop


def test_a_look_at_the_stall_is_a_read():
    shop = Shop({"Ether": 1}, coins=20)
    receipt = shop.query("SELECT name, price FROM stall")
    assert receipt.kind == "read" and ("Ether", 8) in receipt.rows
    assert shop.coins == 20 and shop.inventory == {"Ether": 1}


def test_the_shopkeepers_draft_buys_one_item_and_pays():
    shop = Shop({"Ether": 1}, coins=20)
    receipt = shop.query(Shop.draft("Ether"))
    assert receipt.bought == {"Ether": 1} and receipt.paid == 8
    assert shop.inventory["Ether"] == 2 and shop.coins == 12


def test_insert_select_can_buy_several_rows_at_once():
    shop = Shop({}, coins=50)
    shop.query("INSERT INTO items (name, kind, amount, qty) "
               "SELECT name, kind, amount, 2 FROM stall WHERE price < 10")
    assert shop.inventory == {"Healing Herb": 2, "Ether": 2}
    assert shop.coins == 50 - 2 * 6 - 2 * 8


def test_too_poor_changes_nothing():
    shop = Shop({}, coins=5)
    with pytest.raises(Miscast) as e:
        shop.query(Shop.draft("Hourglass Charm"))
    assert e.value.key == "shop.too_poor"
    assert shop.inventory == {} and shop.coins == 5


def test_a_forged_item_is_not_for_sale():
    shop = Shop({}, coins=99)
    with pytest.raises(Miscast) as e:
        shop.query("INSERT INTO items (name, kind, amount, qty) "
                   "SELECT name, kind, 999, 1 FROM stall WHERE name = 'Ether'")
    assert e.value.key == "shop.not_for_sale"


def test_an_item_named_like_a_spell_trips_name_uniqueness():
    shop = Shop({}, coins=99)
    with pytest.raises(Miscast) as e:
        shop.query("INSERT INTO items (name, kind, amount, qty) "
                   "SELECT name, 'mp', 10, 1 FROM spells WHERE name = 'Ember'")
    assert e.value.key == "miscast.duplicate_name"


@pytest.mark.parametrize("sql", ["UPDATE purse SET coins = 999", "DELETE FROM stall",
                                 "DROP TABLE stall", "INSERT INTO purse VALUES (999)"])
def test_anything_else_is_refused(sql):
    shop = Shop({}, coins=5)
    with pytest.raises(Miscast):
        shop.query(sql)
    assert shop.coins == 5


def test_the_guard_still_refuses_program_unsafe_sql():
    with pytest.raises(Miscast):
        Shop({}, coins=5).query("ATTACH DATABASE 'x.db' AS x")
