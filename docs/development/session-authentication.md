# Browser session API

Use relative URLs under `/api/v1/auth/` from the React app. Serve React and Django under one browser origin, including through a development proxy when needed.

| Request | JSON contract |
|---|---|
| `GET /csrf/` | Returns `200` and `{"ok":true}`. Django sets the `csrftoken` cookie. |
| `POST /login/` | Send `application/json` with string fields `username` and `password`. Success returns `200` with `{"authenticated":true,"user":{"id":7,"username":"member"}}`. Unknown usernames, wrong passwords and inactive accounts return the same `400` and `{"detail":"Invalid username or password."}`. Invalid payloads return `400` and unsupported content types return `415`. |
| `GET /session/` | Returns `200` with the same authenticated response shape or `{"authenticated":false,"user":null}`. Use it to restore authentication state after a page refresh. |
| `POST /logout/` | Requires an authenticated session. Success invalidates the session and returns `200` and `{"authenticated":false,"user":null}`. Anonymous requests receive `403`. |

Keep cookies enabled. Read the CSRF cookie and send its value in `X-CSRFToken` on login, logout and other unsafe requests. **Read the cookie again after successful login.** Django rotates the CSRF token on login. Missing or invalid CSRF receives Django's standard `403` response, which may be HTML. Handle the HTTP status before attempting JSON parsing.

The session cookie is managed by the browser. The session response contains only the current user's ID and username. Metadata authorization uses the separately configured access policy. Signing in leaves role and membership assignments untouched.
