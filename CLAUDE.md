# Rules

- Python standard library only. Do not add third-party dependencies.
- The app must start with one command: `python app.py`.
- `problem.md` is the source of truth for requirements. Do not change it unless asked.
- Every requirement ID in `problem.md` must be covered in `spec.md` and by at least one test.
- Name each test `test_R<N>_<description>` (inside a class named for the requirement) so it maps to the requirement it checks.
- Update `spec.md` and `README.md` whenever behavior, routes, or commands change.
- Run tests with `python -m unittest -v` and make sure they pass before finishing.
- Escape all user-provided text in HTML output.
- Never commit `.venv/`, `__pycache__/`, or `*.jsonl` files.
- If a request or requirement is ambiguous, ask before writing code.
