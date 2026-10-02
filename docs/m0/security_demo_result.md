# Security demonstration result

The local UAT server requires M0_LOCAL_UAT=1, binds loopback, restricts Host/Origin, and accepts
only predefined synthetic personas. It provides an opaque HttpOnly SameSite=Strict cookie,
one-hour expiry, rotation, logout revocation and no-store responses. A separate public identity
key is returned; the authentication token never appears in the session JSON. Client tenant,
permission, org/project and scope headers are not trusted.

The adapter injects existing RepositoryContext from server-owned fixture pointers. Existing
backend repositories, scope resolver and retrieval hard filters enforce access before returning
evidence. The frontend never receives forbidden items and never performs permission filtering
after reception. Persona A/B fixtures have separate tenants, projects, snapshots, policies,
published versions and permissions. Each also has a secret:read version excluded from its
read:internal query. Fixtures contain synthetic Generic text and are labelled as such in the UI;
they are not official legislation or demo legal answers.

Executed assertions include: no-session 401; unknown persona 403; extra login tenant_id 422;
forged tenant header has no effect; cross-origin/public Host 403; authorized A retrieval returns
only allowed version; secret:read version is absent from the HTTP response; B cannot query A's
project or read A's saved run (404); logout invalidates the cookie. Browser switching cancels
requests, removes A results, and renders B results with a disjoint tenant/version set.

Org/department data is null in the available synthetic identity, rather than fabricated. Full
production authentication and organization-policy rollout are integration requirements, not
implemented identity services. This adapter must not be deployed publicly or used for real data.
