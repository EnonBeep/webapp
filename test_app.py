"""Tests for the RPG Character Tracker. Each test name starts with the requirement ID it checks."""
import http.client
import os
import tempfile
import threading
import unittest
from urllib.parse import urlencode

import app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_file = os.path.join(self.tmp.name, "characters.jsonl")
        self.server = app.make_server(port=0, data_file=self.data_file)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, data=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        body = urlencode(data) if data is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded"} if body else {}
        conn.request(method, path, body, headers)
        resp = conn.getresponse()
        text = resp.read().decode("utf-8")
        location = resp.getheader("Location")
        conn.close()
        return resp.status, text, location

    def create(self, name="Aria", char_class="Rogue", **extra):
        status, _, loc = self.request("POST", "/characters", {"name": name, "char_class": char_class, **extra})
        self.assertEqual(status, 303)
        return loc  # /characters/<id>


class TestR1Create(AppTestCase):
    def test_R1_create_with_name_and_class(self):
        loc = self.create("Thorin", "Warrior")
        status, text, _ = self.request("GET", loc)
        self.assertEqual(status, 200)
        self.assertIn("Thorin", text)
        self.assertIn("Warrior", text)

    def test_R1_name_required(self):
        status, text, _ = self.request("POST", "/characters", {"name": " ", "char_class": "Mage"})
        self.assertEqual(status, 400)
        self.assertIn("Name is required", text)

    def test_R1_class_required(self):
        status, text, _ = self.request("POST", "/characters", {"name": "X", "char_class": ""})
        self.assertEqual(status, 400)
        self.assertIn("Class is required", text)

    def test_R1_persists_across_server_restart(self):
        self.create("Persisto", "Cleric")
        other = app.make_server(port=0, data_file=self.data_file)
        self.assertEqual([c["name"] for c in other.RequestHandlerClass.store.list()], ["Persisto"])
        other.server_close()


class TestR2Stats(AppTestCase):
    def test_R2_defaults(self):
        loc = self.create()
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual((c["health"], c["strength"], c["defense"], c["level"]), (100, 10, 10, 1))

    def test_R2_custom_stats_saved(self):
        loc = self.create(health="55", strength="17", defense="9", level="4")
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual((c["health"], c["strength"], c["defense"], c["level"]), (55, 17, 9, 4))

    def test_R2_stats_shown_on_detail_page(self):
        loc = self.create(health="55", strength="17", defense="9", level="4")
        _, text, _ = self.request("GET", loc)
        for label, val in [("Health", 55), ("Strength", 17), ("Defense", 9), ("Level", 4)]:
            self.assertIn(f"{label}: {val}", text)

    def test_R2_non_numeric_stat_rejected(self):
        status, text, _ = self.request("POST", "/characters", {"name": "A", "char_class": "B", "health": "lots"})
        self.assertEqual(status, 400)
        self.assertIn("Health must be a whole number", text)

    def test_R2_level_must_be_at_least_one(self):
        status, _, _ = self.request("POST", "/characters", {"name": "A", "char_class": "B", "level": "0"})
        self.assertEqual(status, 400)

    def test_R2_negative_health_rejected(self):
        status, _, _ = self.request("POST", "/characters", {"name": "A", "char_class": "B", "health": "-5"})
        self.assertEqual(status, 400)


class TestR3List(AppTestCase):
    def test_R3_empty_list_message(self):
        _, text, _ = self.request("GET", "/")
        self.assertIn("No characters yet", text)

    def test_R3_lists_all_characters(self):
        self.create("Alpha", "Mage")
        self.create("Beta", "Knight")
        status, text, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Alpha", text)
        self.assertIn("Beta", text)
        self.assertIn("Mage", text)
        self.assertIn("Knight", text)

    def test_R3_html_is_escaped(self):
        self.create("<script>x</script>", "Mage")
        _, text, _ = self.request("GET", "/")
        self.assertNotIn("<script>x</script>", text)
        self.assertIn("&lt;script&gt;", text)


class TestR4Edit(AppTestCase):
    def test_R4_edit_details(self):
        loc = self.create("Old", "Rogue")
        status, _, _ = self.request("POST", loc + "/edit", {
            "name": "New", "char_class": "Paladin", "health": "80", "strength": "12", "defense": "14", "level": "3"})
        self.assertEqual(status, 303)
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual((c["name"], c["char_class"], c["health"], c["level"]), ("New", "Paladin", 80, 3))

    def test_R4_invalid_edit_rejected_and_unchanged(self):
        loc = self.create("Keep", "Rogue")
        status, _, _ = self.request("POST", loc + "/edit", {"name": "", "char_class": "Rogue"})
        self.assertEqual(status, 400)
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual(c["name"], "Keep")

    def test_R4_edit_keeps_inventory(self):
        loc = self.create()
        self.request("POST", loc + "/items", {"item_name": "Dagger", "quantity": "1"})
        self.request("POST", loc + "/edit", {"name": "Renamed", "char_class": "Rogue"})
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual(c["inventory"], [{"name": "Dagger", "quantity": 1}])

    def test_R4_edit_unknown_character_404(self):
        status, _, _ = self.request("POST", "/characters/nope/edit", {"name": "a", "char_class": "b"})
        self.assertEqual(status, 404)


class TestR5Delete(AppTestCase):
    def test_R5_delete_removes_character(self):
        loc = self.create("Doomed", "Bard")
        status, _, redirect = self.request("POST", loc + "/delete", {})
        self.assertEqual((status, redirect), (303, "/"))
        self.assertEqual(self.request("GET", loc)[0], 404)
        self.assertNotIn("Doomed", self.request("GET", "/")[1])

    def test_R5_delete_only_removes_target(self):
        a = self.create("Stay", "Bard")
        b = self.create("Go", "Bard")
        self.request("POST", b + "/delete", {})
        self.assertEqual(self.request("GET", a)[0], 200)


class TestR6Inventory(AppTestCase):
    def test_R6_new_character_has_empty_inventory(self):
        loc = self.create()
        _, text, _ = self.request("GET", loc)
        self.assertIn("Inventory is empty", text)

    def test_R6_inventory_is_per_character(self):
        a = self.create("A", "Mage")
        b = self.create("B", "Mage")
        self.request("POST", a + "/items", {"item_name": "Staff", "quantity": "1"})
        self.assertIn("Staff", self.request("GET", a)[1])
        self.assertNotIn("Staff", self.request("GET", b)[1])


class TestR7InventoryEdit(AppTestCase):
    def test_R7_add_item(self):
        loc = self.create()
        status, _, _ = self.request("POST", loc + "/items", {"item_name": "Potion", "quantity": "3"})
        self.assertEqual(status, 303)
        _, text, _ = self.request("GET", loc)
        self.assertIn("Potion", text)
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual(c["inventory"], [{"name": "Potion", "quantity": 3}])

    def test_R7_add_item_default_quantity_one(self):
        loc = self.create()
        self.request("POST", loc + "/items", {"item_name": "Rope", "quantity": ""})
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual(c["inventory"][0]["quantity"], 1)

    def test_R7_item_name_required(self):
        loc = self.create()
        status, _, _ = self.request("POST", loc + "/items", {"item_name": "  ", "quantity": "1"})
        self.assertEqual(status, 400)

    def test_R7_quantity_must_be_positive(self):
        loc = self.create()
        status, _, _ = self.request("POST", loc + "/items", {"item_name": "Gem", "quantity": "0"})
        self.assertEqual(status, 400)

    def test_R7_remove_item(self):
        loc = self.create()
        self.request("POST", loc + "/items", {"item_name": "Sword", "quantity": "1"})
        self.request("POST", loc + "/items", {"item_name": "Shield", "quantity": "1"})
        status, _, _ = self.request("POST", loc + "/items/0/remove", {})
        self.assertEqual(status, 303)
        c = self.server.RequestHandlerClass.store.get(loc.split("/")[-1])
        self.assertEqual([i["name"] for i in c["inventory"]], ["Shield"])

    def test_R7_remove_bad_index_404(self):
        loc = self.create()
        self.assertEqual(self.request("POST", loc + "/items/5/remove", {})[0], 404)


if __name__ == "__main__":
    unittest.main()
