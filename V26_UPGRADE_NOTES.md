
# V26 Upgrade Notes

## Frontend / navigation
- Added role-based landing redirect after login via `/api/auth/landing`
- Admin users land on `/admin.html`
- Users can land on `/animation-studio.html` when permission default project is animation
- Added separate sub-account permissions page: `/admin-permissions.html`

## Admin center
- Added permissions APIs backed by JSON store:
  - `GET /api/admin/user-permissions`
  - `GET /api/admin/user-permissions/{user_id}`
  - `PUT /api/admin/user-permissions/{user_id}`
- Added admin password reset endpoint:
  - `POST /api/admin/users/{user_id}/reset-password`
- Upgraded admin UI with summary cards, search, permissions shortcut, reset password action

## Auth
- Added:
  - `GET /api/auth/me/permissions`
  - `GET /api/auth/landing`
