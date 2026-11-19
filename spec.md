# Spec

Requirements come from `problem.md`. Implementation is in `app.py`; tests are in `test_app.py`.

## Architecture
- Python standard library only: `http.server.ThreadingHTTPServer`, server-rendered HTML, plain HTML forms (POST, then 303 redirect).
- Storage: `Store` class persisting to a JSON Lines file (one character per line, rewritten on each change, guarded by a lock). Default `characters.jsonl`; override with `DATA_FILE`.
- Character: `id`, `name`, `char_class`, `health`, `strength`, `defense`, `level`, `inventory` (list of `{name, quantity}`).
- All user text is HTML-escaped on output. Invalid input returns HTTP 400 with an error message and changes nothing.

## Routes
| Method | Path | Action |
|---|---|---|
| GET | `/` | List characters + create form |
| POST | `/characters` | Create |
| GET | `/characters/<id>` | Detail, edit form, inventory |
| POST | `/characters/<id>/edit` | Edit |
| POST | `/characters/<id>/delete` | Delete |
| POST | `/characters/<id>/items` | Add item |
| POST | `/characters/<id>/items/<index>/remove` | Remove item |

## Requirements

| ID | Requirement | How it is met | Tests |
|---|---|---|---|
| R1 | Create a character with a name and class | Create form on `/`; `POST /characters` requires non-blank name and class, saves to the JSONL file | `TestR1Create` |
| R2 | Health, strength, defense, level | Every character stores all four as integers. Defaults: 100/10/10/1. Health, strength, defense >= 0; level >= 1; non-numbers rejected | `TestR2Stats` |
| R3 | List all characters | `GET /` shows a table of every character (name linked to detail, class, level, stats), or "No characters yet." | `TestR3List` |
| R4 | Edit a character's details | Edit form on the detail page; `POST /characters/<id>/edit` applies the same validation as create and leaves inventory untouched | `TestR4Edit` |
| R5 | Delete a character | "Delete character" button; `POST /characters/<id>/delete` removes only that character, redirects to `/` | `TestR5Delete` |
| R6 | Each character has an inventory | Every character has its own `inventory` list (empty at creation), shown on its detail page | `TestR6Inventory` |
| R7 | Add/remove inventory items | Add form (item name, quantity >= 1, default 1) and a Remove button per item | `TestR7InventoryEdit` |

## Out of scope (not in requirements)
Accounts/login (single local user), separate equipment slots, item stats.
