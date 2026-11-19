"""RPG Character Tracker - a web app using only the Python standard library.

Run with:  python app.py   (then open http://localhost:8000)
"""
import html
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEFAULT_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters.jsonl")

STAT_DEFAULTS = {"health": 100, "strength": 10, "defense": 10, "level": 1}
STAT_MINIMUMS = {"health": 0, "strength": 0, "defense": 0, "level": 1}


class ValidationError(Exception):
    pass


class Store:
    """Character storage backed by a JSON Lines file (one character per line)."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def _write(self, characters):
        with open(self.path, "w", encoding="utf-8") as f:
            for c in characters:
                f.write(json.dumps(c) + "\n")

    def list(self):
        with self._lock:
            return self._read()

    def get(self, cid):
        with self._lock:
            return next((c for c in self._read() if c["id"] == cid), None)

    def create(self, fields):
        character = {"id": uuid.uuid4().hex, "inventory": [], **fields}
        with self._lock:
            chars = self._read()
            chars.append(character)
            self._write(chars)
        return character

    def update(self, cid, fields):
        with self._lock:
            chars = self._read()
            for c in chars:
                if c["id"] == cid:
                    c.update(fields)
                    self._write(chars)
                    return c
        return None

    def delete(self, cid):
        with self._lock:
            chars = self._read()
            kept = [c for c in chars if c["id"] != cid]
            if len(kept) == len(chars):
                return False
            self._write(kept)
            return True

    def add_item(self, cid, name, quantity):
        with self._lock:
            chars = self._read()
            for c in chars:
                if c["id"] == cid:
                    c["inventory"].append({"name": name, "quantity": quantity})
                    self._write(chars)
                    return True
        return False

    def remove_item(self, cid, index):
        with self._lock:
            chars = self._read()
            for c in chars:
                if c["id"] == cid:
                    if 0 <= index < len(c["inventory"]):
                        c["inventory"].pop(index)
                        self._write(chars)
                        return True
                    return False
        return False


def parse_character(form):
    """Validate form data into character fields. Raises ValidationError."""
    name = form.get("name", "").strip()
    char_class = form.get("char_class", "").strip()
    if not name:
        raise ValidationError("Name is required.")
    if not char_class:
        raise ValidationError("Class is required.")
    fields = {"name": name, "char_class": char_class}
    for stat, default in STAT_DEFAULTS.items():
        raw = form.get(stat, "").strip()
        if raw == "":
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                raise ValidationError(f"{stat.capitalize()} must be a whole number.")
        if value < STAT_MINIMUMS[stat]:
            raise ValidationError(f"{stat.capitalize()} must be at least {STAT_MINIMUMS[stat]}.")
        fields[stat] = value
    return fields


def parse_item(form):
    name = form.get("item_name", "").strip()
    if not name:
        raise ValidationError("Item name is required.")
    raw = form.get("quantity", "").strip() or "1"
    try:
        quantity = int(raw)
    except ValueError:
        raise ValidationError("Quantity must be a whole number.")
    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")
    return name, quantity


# ---------- HTML rendering ----------

def esc(value):
    return html.escape(str(value), quote=True)


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>
body {{ font-family: sans-serif; max-width: 700px; margin: 2em auto; padding: 0 1em; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
.error {{ color: #b00020; font-weight: bold; }}
label {{ display: block; margin: 4px 0; }}
form.inline {{ display: inline; }}
</style></head><body>
<h1><a href="/">RPG Character Tracker</a></h1>
{body}
</body></html>"""


def character_fields_html(c=None):
    c = c or {}
    out = [
        f'<label>Name <input name="name" value="{esc(c.get("name", ""))}" required></label>',
        f'<label>Class <input name="char_class" value="{esc(c.get("char_class", ""))}" required></label>',
    ]
    for stat, default in STAT_DEFAULTS.items():
        out.append(
            f'<label>{stat.capitalize()} <input type="number" name="{stat}" '
            f'min="{STAT_MINIMUMS[stat]}" value="{esc(c.get(stat, default))}"></label>'
        )
    return "\n".join(out)


def render_list(characters, error=""):
    if characters:
        rows = "".join(
            f'<tr><td><a href="/characters/{esc(c["id"])}">{esc(c["name"])}</a></td>'
            f'<td>{esc(c["char_class"])}</td><td>{esc(c["level"])}</td>'
            f'<td>{esc(c["health"])}</td><td>{esc(c["strength"])}</td>'
            f'<td>{esc(c["defense"])}</td></tr>'
            for c in characters
        )
        table = ("<table><tr><th>Name</th><th>Class</th><th>Level</th><th>Health</th>"
                 f"<th>Strength</th><th>Defense</th></tr>{rows}</table>")
    else:
        table = "<p>No characters yet.</p>"
    err = f'<p class="error">{esc(error)}</p>' if error else ""
    body = (f"<h2>Characters</h2>{table}<h2>Create a character</h2>{err}"
            f'<form method="post" action="/characters">{character_fields_html()}'
            "<button>Create</button></form>")
    return page("Characters", body)


def render_detail(c, error=""):
    items = "".join(
        f'<tr><td>{esc(i["name"])}</td><td>{esc(i["quantity"])}</td><td>'
        f'<form class="inline" method="post" action="/characters/{esc(c["id"])}/items/{n}/remove">'
        "<button>Remove</button></form></td></tr>"
        for n, i in enumerate(c["inventory"])
    )
    inv = (f"<table><tr><th>Item</th><th>Qty</th><th></th></tr>{items}</table>"
           if c["inventory"] else "<p>Inventory is empty.</p>")
    err = f'<p class="error">{esc(error)}</p>' if error else ""
    cid = esc(c["id"])
    body = (
        f'<h2>{esc(c["name"])}</h2>'
        f'<p>Class: {esc(c["char_class"])} | Level: {esc(c["level"])} | Health: {esc(c["health"])} | '
        f'Strength: {esc(c["strength"])} | Defense: {esc(c["defense"])}</p>{err}'
        f'<h3>Edit</h3><form method="post" action="/characters/{cid}/edit">'
        f'{character_fields_html(c)}<button>Save</button></form>'
        f'<h3>Inventory</h3>{inv}'
        f'<form method="post" action="/characters/{cid}/items">'
        '<label>Item <input name="item_name" required></label>'
        '<label>Quantity <input type="number" name="quantity" min="1" value="1"></label>'
        '<button>Add item</button></form>'
        f'<h3>Delete</h3><form method="post" action="/characters/{cid}/delete">'
        '<button>Delete character</button></form>'
    )
    return page(c["name"], body)


# ---------- HTTP handling ----------

class Handler(BaseHTTPRequestHandler):
    store = None  # set by make_server

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, content, headers=None):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self._send(303, "", {"Location": location})

    def _not_found(self):
        self._send(404, page("Not found", "<p>Not found.</p>"))

    def _form(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def _parts(self):
        return [p for p in urlparse(self.path).path.split("/") if p]

    def do_GET(self):
        parts = self._parts()
        if not parts:
            self._send(200, render_list(self.store.list()))
        elif len(parts) == 2 and parts[0] == "characters":
            c = self.store.get(parts[1])
            if c:
                self._send(200, render_detail(c))
            else:
                self._not_found()
        else:
            self._not_found()

    def do_POST(self):
        parts = self._parts()
        form = self._form()
        if parts == ["characters"]:
            try:
                c = self.store.create(parse_character(form))
            except ValidationError as e:
                return self._send(400, render_list(self.store.list(), str(e)))
            return self._redirect(f"/characters/{c['id']}")

        if len(parts) >= 3 and parts[0] == "characters":
            cid, action = parts[1], parts[2]
            c = self.store.get(cid)
            if not c:
                return self._not_found()
            back = f"/characters/{cid}"
            if action == "edit" and len(parts) == 3:
                try:
                    self.store.update(cid, parse_character(form))
                except ValidationError as e:
                    return self._send(400, render_detail(c, str(e)))
                return self._redirect(back)
            if action == "delete" and len(parts) == 3:
                self.store.delete(cid)
                return self._redirect("/")
            if action == "items" and len(parts) == 3:
                try:
                    name, qty = parse_item(form)
                except ValidationError as e:
                    return self._send(400, render_detail(c, str(e)))
                self.store.add_item(cid, name, qty)
                return self._redirect(back)
            if action == "items" and len(parts) == 5 and parts[4] == "remove":
                try:
                    index = int(parts[3])
                except ValueError:
                    return self._not_found()
                if self.store.remove_item(cid, index):
                    return self._redirect(back)
                return self._not_found()
        self._not_found()


def make_server(host="127.0.0.1", port=8000, data_file=DEFAULT_DATA_FILE):
    handler = type("BoundHandler", (Handler,), {"store": Store(data_file)})
    return ThreadingHTTPServer((host, port), handler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    server = make_server(port=port, data_file=os.environ.get("DATA_FILE", DEFAULT_DATA_FILE))
    print(f"Serving on http://localhost:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
