# Legacy Write Entrypoints

## Overview

This document lists legacy write entrypoints that have been consolidated into unified services.

## Member Write Entrypoints

### User Membership Binding

| Old Entrypoint | Location | Status | Formal Replacement | Accepts Writes |
|---|---|---|---|---|
| `bind_user(membership_id, user_id, reason, actor)` | app/services/membership_user_link_service.py | Deprecated | UnifiedIdentityService.bind_user_to_membership() | Yes (compatibility) |
| `unbind_user(membership_id, reason, actor)` | app/services/membership_user_link_service.py | Deprecated | UnifiedIdentityService.unbind_user_from_membership() | Yes (compatibility) |
| `request_membership_link(user_id, membership_id, reason)` | app/services/membership_user_link_service.py | Deprecated | UnifiedIdentityService.request_membership_link() | Yes (compatibility) |
| `approve_membership_link(request_id, reviewer)` | app/services/membership_user_link_service.py | Deprecated | UnifiedIdentityService.approve_membership_link() | Yes (compatibility) |
| `reject_membership_link(request_id, reason, reviewer)` | app/services/membership_user_link_service.py | Deprecated | UnifiedIdentityService.reject_membership_link() | Yes (compatibility) |

### Route-level Bind/Unbind

| Old Entrypoint | Location | Status | Formal Replacement | Accepts Writes |
|---|---|---|---|---|
| POST /club/members/{member_id}/user-link | app/v04f_operations.py | Updated | Same URL (now uses UnifiedIdentityService) | Yes |
| POST /club/members/{member_id}/user-unlink | app/v04f_operations.py | Updated | Same URL (now uses UnifiedIdentityService) | Yes |
| POST /member/request-membership-link | app/v05d_member_portal.py | Updated | Same URL (now uses UnifiedIdentityService) | Yes |
| POST /api/v1/memberships/{id}/user-link | app/api/v1/membership_user_link.py | Updated | Same URL (now uses UnifiedIdentityService) | Yes |
| DELETE /api/v1/memberships/{id}/user-link | app/api/v1/membership_user_link.py | Updated | Same URL (now uses UnifiedIdentityService) | Yes |

## Resource Write Entrypoints

### Supply/Demand Creation

| Old Entrypoint | Location | Status | Formal Replacement | Accepts Writes |
|---|---|---|---|---|
| POST /club/members/{member_id}/needs | app/v04f_operations.py | Updated | Same URL (now uses UnifiedResourceService) | Yes |
| POST /club/members/{member_id}/offerings | app/v04f_operations.py | Updated | Same URL (now uses UnifiedResourceService) | Yes |
| Direct INSERT to v04f_club_needs | app/v04f_operations.py | Disabled | UnifiedResourceService.create(direction="demand") | No |
| Direct INSERT to v04f_club_offerings | app/v04f_operations.py | Disabled | UnifiedResourceService.create(direction="supply") | No |

## Guidelines

### For Developers

1. **New code must call unified services**, not legacy functions directly.
2. **Route handlers should use unified services** or maintain compatibility by delegating to them.
3. **Legacy functions are kept for backward compatibility** but should not be extended.

### Deprecation Status

- **Deprecated**: Function still works but has a formal replacement. Use the replacement for new code.
- **Disabled**: Function no longer writes to old tables. Calls are routed to unified services.
- **Updated**: Route handler now delegates to unified service internally.

### Removal Timeline

| Entrypoint | Removal Stage | Precondition |
|---|---|---|
| membership_user_link_service.py functions | P2 | All callers migrated to UnifiedIdentityService |
| v04f_club_needs direct writes | P2 | No active code paths writing to this table |
| v04f_club_offerings direct writes | P2 | No active code paths writing to this table |

### Compliance

All writes now go through:
- `UnifiedIdentityService` for User-Person-Membership relationships
- `UnifiedResourceService` for resource creation (demand/supply)

This ensures:
- Single source of truth
- Transactional integrity
- Audit logging
- Legacy ID mapping preservation