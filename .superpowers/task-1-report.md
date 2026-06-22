# Task 1 Report: pdfplumber dependency + preprocessor config settings

## Status
DONE

## Commits Made
- `f5468c4` chore(dep): add pdfplumber and preprocessor config settings

## Changes Summary

### 1. Dependency added
- `pyproject.toml`: Added `pdfplumber>=0.10.0` to project dependencies (MIT license)

### 2. Config settings added (6 fields in `app/core/config.py`)
| Field | Type | Default |
|---|---|---|
| `preprocessor_enabled` | bool | `True` |
| `preprocessor_pdf_images` | bool | `True` |
| `preprocessor_pdf_tables` | bool | `True` |
| `preprocessor_pdf_max_pages` | int | `100` |
| `preprocessor_pdf_image_dir` | str | `"./uploads/images"` |
| `preprocessor_pdf_dpi` | int | `150` |

### 3. Environment files updated
- `.env.example`: Added 6 commented-out preprocessor variables
- `.env.docker`: Added 6 preprocessor variables with Docker-appropriate defaults (e.g. `/app/uploads/images` for image dir)

### 4. Tests written (`tests/unit/core/test_preprocessor_config.py`)
- 10 tests total: 6 default-value tests + 4 env-override tests
- All 10 pass

### 5. Test Results
```
tests/unit/core/test_preprocessor_config.py .............. 10 passed in 0.06s
```

All 10 new tests pass. Existing core tests: 18 passed, 2 pre-existing failures in `test_llm_factory.py` (OpenAI API key missing -- unrelated to this change).

## Concerns
- None for this task. The Settings class uses `pydantic_settings.BaseSettings` which natively supports boolean env var parsing (`"false"` -> `False`), so the env override tests work correctly without any custom logic.
