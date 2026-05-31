# Tests

Validation and workflow tests for the follow-up assistant ops workspace.

## Running Tests

```bash
python -m pytest tests/
```

## Planned Test Coverage

Tests will be added alongside each implementation plan:

| Plan | Tests |
|------|-------|
| 0002 | Client config schema validation — valid config passes, invalid config fails clearly |
| 0003 | Lead hub — create lead, transition statuses, reject malformed records |
| 0004 | Intake adapters — website payload → normalized lead, manual lead entry |
| 0005 | Prompt rendering — prompts produce non-empty output given fixture data |
| 0006 | Classification — known fixtures map to expected classifications |

## Fixtures

Test fixtures will live in `tests/fixtures/` and must contain only fictional
data. Do not use real leads, real client details, or real tokens in tests.
