# RPG Character Tracker

A small web app for keeping track of your RPG characters in one place. You can create characters with a name and class, track their health, strength, defense and level, edit or delete them, and manage each character's inventory.

Written in Python using only the standard library (no installs needed).

## Run

```
python app.py
```

Then open http://localhost:8000. Set the `PORT` environment variable to use a different port. Characters are saved to `characters.jsonl` next to `app.py` (override with `DATA_FILE`).

## Test

```
python -m unittest -v
```

Test names start with the requirement ID they check (e.g. `test_R3_lists_all_characters`). See `spec.md` for how each requirement is met.
