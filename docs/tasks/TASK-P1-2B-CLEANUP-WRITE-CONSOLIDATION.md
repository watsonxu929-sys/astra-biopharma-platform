# Task: P1.2-B Cleanup & Write Consolidation

## Overview

This task covers approved archive operations and write path consolidation for membership and resource creation.

## Scope

### Archive Operations
- Remove __pycache__ and .pyc files
- Archive approved backup/patch directories
- Create archive manifest

### Write Consolidation
- Unify membership write paths through UnifiedIdentityService
- Unify resource write paths through UnifiedResourceService
- Mark legacy entrypoints as deprecated
- Add tests for consolidation

## Changes Made

### Services Created
- `app/services/unified_identity_service.py` - Unified identity service for User-Person-Membership binding

### Services Updated
- `app/services/unified_resource_service.py` - Already exists, used as canonical resource service

### Routes Updated
- `app/v04f_operations.py` - User bind/unbind routes now call UnifiedIdentityService
- `app/v04f_operations.py` - Need/offering creation now calls UnifiedResourceService
- `app/v05d_member_portal.py` - Link request route now calls UnifiedIdentityService
- `app/api/v1/membership_user_link.py` - API routes now call UnifiedIdentityService

### Documentation Added
- `docs/LEGACY_WRITE_ENTRYPOINTS.md` - Legacy entrypoint catalog
- `docs/P1_FINAL_ACCEPTANCE.md` - P1 final acceptance report
- `docs/audit/P1_2_ARCHIVE_MANIFEST.csv` - Archive manifest

### Tests Added
- `tests/test_write_consolidation.py` - Write consolidation tests

## Verification

Run these commands in order:

```bash
python -m compileall app scripts tests
python scripts/check_source_encoding.py
python scripts/check_mojibake.py
python scripts/verify_p0_baseline.py
python scripts/verify_p0_stability_v1.py
python scripts/verify_p1_domain_unification.py
python scripts/verify_domain_consolidation_v1.py
python -m pytest -q
```

## Rollback

If issues are found:

1. Restore archived directories from `../biopharma-intelligence-archive/p1-2/`
2. Revert changes to route handlers
3. Revert to using original membership_user_link_service functions
4. Revert resource creation back to direct INSERTs

## Dependencies

- No new dependencies added
- Uses existing services and patterns