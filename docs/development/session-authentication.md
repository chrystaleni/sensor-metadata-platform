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

## Login attempt limits

Apply the security migrations before serving login, and point all application workers at the same PostgreSQL database. `LOGIN_FAILURE_LIMIT` defaults to `5` and `LOGIN_FAILURE_WINDOW_SECONDS` defaults to `900`. Use the same settings, clock synchronization and Django secret across workers.

The first rejected credential check starts a fixed window for the client address. After five failures, subsequent login requests return `429` with `{"detail":"Too many login attempts. Try again later."}` and a `Retry-After` header in whole seconds. Successful credentials below the limit leave the failure budget intact. A blocked login leaves any existing session usable. CSRF and payload checks still run first. The limiter stores one keyed address hash per client, with an indexed expiry. Failed attempts prune expired windows in bounded batches. Expired rows never block login.

The limiter tries to acquire a per-client PostgreSQL transaction lock without waiting. A busy lock or unavailable throttling infrastructure returns `503` with `{"detail":"Login is temporarily unavailable."}` and `Retry-After: 1`. A busy request skips credential verification and leaves the failure budget intact. A database failure rolls back any pending counter changes and prevents a new login session. A `429` means the failure budget is exhausted and gives the remaining window. A `503` is a temporary service failure. Respect the retry delay and keep an existing session intact. The lock is released when the transaction ends, though the request holding it still uses a worker and a database connection during password verification.

The client key uses the server-provided `REMOTE_ADDR`. The application ignores forwarded IP headers. Behind a reverse proxy, configure the serving infrastructure to derive `REMOTE_ADDR` only from trusted proxy hops and prevent direct access that would bypass that boundary. Otherwise users sharing a proxy or NAT address also share one budget. A missing or invalid peer address, or a non-PostgreSQL backend, makes login return `503`. Address-based limits cover username switching from one client. Distributed attacks across many addresses require additional controls at the edge.
