# v0.6B Platform Capability Mapping

| Legacy feature | Legacy route | New entry | Permission | Reuse | Migration note |
| --- | --- | --- | --- | --- | --- |
| Q-BAY club home | /club | /club | view_internal | yes | Reuses v04f club portal and counts. |
| Member management | /club/members | /platform workspace, /api/v1/me/club-context | manage_club | yes | Reuses v04f_club_memberships and User-Membership links. |
| Member import | /club/import | /platform workspace | manage_club | yes | Reuses v05b import workflow. |
| Club events | /club/events | /platform workspace | manage_club | yes | Reuses v05c event workflow. |
| Member portal | /member | /api/v1/me/membership-context | membership.view_self | yes | Kept as legacy web entry. |
| Identity link | /me/industry-profile | /platform workspace, /api/v1/me/person-link | identity.view_self | yes | Reuses identity_link_requests. |
| Organization access | /network/organizations | /api/v1/me/organization-context | organization.view_self | yes | Reuses organization access services. |
| People discovery | /network/people | /api/v1/network/people | view_internal | yes | Reuses platform_service discovery and tags. |
| Intelligence | /intelligence | /api/v1/intelligence | view_internal | yes | Reuses v06 intelligence tables/services. |
| Resources | /resources | /api/v1/resources (planned facade) | view_internal | yes | Web reuses v06 resources services. |
| Opportunities | /opportunities | /api/v1/client/bootstrap summaries | view_internal | yes | Web reuses v06 opportunity services. |
| Leads | /leads | /platform workspace | view_internal | yes | Reuses v04f lead operations. |
| Recommendations | /recommendations | /platform workspace | use_recommendations | yes | Reuses v04h recommendations. |
| System admin | /system/operations | /api/v1/system | manage_users | yes | Stays in admin/ops surface. |
