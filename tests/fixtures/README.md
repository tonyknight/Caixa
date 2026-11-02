# Caixa test fixtures

Caixa's tests use the same synthetic fixture family as Chattr. The builders live with Chattr, so
Chattr can run its own tests on its own:

- **Builders and documentation:** [`tools/chattr/tests/fixtures/`](../../tools/chattr/tests/fixtures/README.md)
- **Entry point:** `fixtures.build_all(out_dir)` (also available as the `fixture_family` pytest
  fixture in `tools/chattr/tests/conftest.py`)

Caixa-specific fixtures, such as master-database scenarios, go in this folder as later tickets
need them. Never add real personal data.
