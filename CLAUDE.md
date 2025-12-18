# Development Notes

## Python Version Compatibility

### datetime.fromisoformat() (Python 3.10)

Python 3.10's `fromisoformat()` is stricter than 3.11+:
- **Fails**: `+0000` timezone format
- **Works**: `+00:00` timezone format

When parsing timestamps (e.g., from git), convert timezone:
```python
# Convert +0000 to +00:00
if len(tz_part) == 5 and tz_part[0] in "+-":
    tz_part = tz_part[:3] + ":" + tz_part[3:]
```

## Test Environment

- `tests/conftest.py` sets `COLUMNS=200` to prevent Rich terminal wrapping
- Always normalize whitespace in output assertions when checking error messages
