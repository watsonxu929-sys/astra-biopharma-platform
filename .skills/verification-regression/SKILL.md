---
name: verification-regression
description: Verification and regression workflow for this biopharma intelligence system. Use when adding checks, running or planning validation, connecting feature-specific verify scripts to verify_all_windows.bat, or proving a change did not pollute the formal SQLite database.
---

# Verification Regression

Use this Skill for validation work. Read `AGENTS.md` and existing verification scripts before adding or reporting checks.

## Inputs

- Feature or behavior to verify.
- Changed files or planned change.
- Existing verification scripts in `scripts/` and Windows wrappers.

## Workflow

1. Locate relevant scripts with targeted searches:
   - orchestrator: `verify_all_windows.bat`, `scripts/verify_all.py`
   - latest feature checks: `scripts/verify_v05c.py`, `scripts/verify_v05d.py`, `scripts/verify_v05e.py`
   - historical checks: `scripts/verify_v04*.py`, `tools/windows/archive/`
2. Prefer a dedicated verify script for new feature surfaces.
3. Use temporary SQLite databases or copied databases for destructive or write-heavy tests.
4. Keep formal `data/app.db` free of synthetic verification records.
5. Make Windows wrappers double-click friendly: clear title, visible errors, no instant close on failure, logs where useful.
6. Connect stable feature checks into `verify_all_windows.bat` through `scripts/verify_all.py` when they should become baseline regression.
7. Output pass, fail and skipped counts or an equally explicit summary.
8. Do not claim a test passed unless it actually ran.

## Safety Rules

- Never delete or rebuild the formal database as part of verification.
- Do not fabricate missing fixtures, test users or results.
- Avoid hidden network dependencies unless the feature is explicitly about collection or monitoring.
- Keep auth bypass such as `APP_AUTH_DISABLED=1` limited to local automation and document it when used.

## Existing Commands

```bat
verify_all_windows.bat
project_tools_windows.bat
run_windows.bat
```

Feature scripts can also be run directly with Python when appropriate, for example `python scripts\verify_v05e.py`.

## Completion Reply

Report which scripts ran, pass/fail/skipped summary, whether a temporary database was used, whether `data/app.db` stayed untouched, and any checks not run.

## Failure Handling

If verification fails, preserve the failing command and key error. If the failure is environmental, state the missing dependency or setup step and avoid changing business code just to make the test green.
