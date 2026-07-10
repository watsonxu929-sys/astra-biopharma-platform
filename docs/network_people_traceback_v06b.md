# /network/people traceback record for v0.6B

Current run: no active traceback reproduced. TestClient and HTTP checks returned 200 for /network/people.

Received WorkBuddy record: the previous 500 was caused by passing `name=name` into the platform `render()` helper, conflicting with the helper parameter `name` used for the Jinja template name. WorkBuddy fixed it by renaming the filter context to `name_filter` in `app/routes_platform.py` and `app/templates/platform/people_discovery.html`.

v0.6B follow-up fix: `app/services/platform_service.py` no longer treats `current_user_id` as a `Person.id` in recommendation logic. It resolves the approved User-Person link first, and falls back to public recommendations when the user has no Person profile.
