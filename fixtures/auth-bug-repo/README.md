# auth-bug-repo (vertical-slice fixture)

Intentional authentication bug for the Alama local demo.

## Bug

`authenticate()` treats `None`, `""`, and whitespace tokens as authenticated.

## Expected fix

Reject missing/blank tokens with `ValueError("missing token")`.

## Run tests (before fix)

```bash
cd fixtures/auth-bug-repo
pip install pytest
pytest
```
