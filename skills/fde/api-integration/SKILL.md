---
name: api-integration
description: Procedure for building and debugging third-party API integrations - contract, auth, failure modes, idempotency and webhooks
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fde, api, integration, webhooks, http]
    category: fde
---

# API Integration

A procedure for the work that fills most FDE weeks: making two systems you only
half control talk to each other, and finding out why they stopped.

## When to Use

Use this when the problem sits on a boundary you do not own both sides of: a
third-party REST or GraphQL API, a webhook that stopped arriving, an OAuth flow
that fails for one tenant, a sync that drifts. Pair it with `fde-methodology`
when something is broken — that skill supplies the investigative discipline,
this one supplies what to look at.

## The Non-Negotiable Rules

1. **The contract is the vendor's documentation plus what the endpoint actually
   returns — and where they disagree, the endpoint wins.** Record both.
2. **Never log a credential, a bearer token, an API key or a full
   `Authorization` header.** Redact before writing, not after noticing. Request
   and response bodies routinely carry tokens too.
3. **Never test destructive operations against production.** If there is no
   sandbox, say so and get explicit written authorisation naming the specific
   operation.
4. **A retry without idempotency is a duplication bug you have not hit yet.**

## Procedure

### Establish the contract

1. **Get the specification.** OpenAPI/GraphQL schema if it exists, the
   documentation if not. Record the version and the date you read it.
2. **Call the simplest read endpoint by hand** — `curl`, with `-i` so you see
   the status line and headers. Do this before writing any client code. It
   establishes reachability, auth, and the actual response shape in one step.
3. **Diff the documented shape against the observed shape.** Field names,
   nullability, date formats, numeric types (a string `"12.30"` where the docs
   say number is a real and common trap), pagination envelope. Record every
   divergence as a FACT with the response that showed it.
4. **Establish identity and authorisation.** Which credential, which scopes,
   which tenant, whose account. Most "the API is broken" reports are a scope or
   a tenant, not a bug.

### Map the failure modes before you need them

5. **Enumerate the error taxonomy.** For each: what the API returns, what it
   means, and what the correct response is.
   - `400` — your payload. Never retry unchanged.
   - `401` / `403` — credential vs permission. These are different bugs; do not
     conflate them in the code or in the report.
   - `404` — absent, or hidden by permissions. Some APIs return 404 for
     forbidden objects deliberately.
   - `409` — state conflict. Usually means re-read then re-decide, not retry.
   - `422` — semantically invalid. Never retry unchanged.
   - `429` — rate limited. Read `Retry-After`; honour it rather than guessing.
   - `5xx` — theirs. Retry with backoff and a cap.
   - Timeout with no response — **the ambiguous case**. The request may have
     succeeded. Only idempotency makes this safe.
6. **Find the limits.** Rate limits, page sizes, payload size caps, request
   timeout, concurrency limits. Record where each is documented, and whether
   the header actually reflects it.

### Build it

7. **Make writes idempotent.** An idempotency key on every write the API
   supports one for; a natural dedupe key where it does not. This is the single
   highest-value decision in an integration.
8. **Retry only what is safe to retry:** `429` and `5xx`, exponential backoff
   with jitter, a bounded attempt count, and a hard ceiling on total time. Never
   retry `4xx` other than `429`. Never retry a non-idempotent write on a
   timeout without a dedupe key.
9. **Set explicit timeouts** — connect and read, separately. A client with no
   timeout does not fail, it hangs, and a hang is far harder to diagnose than
   an error.
10. **Handle pagination completely**, including the empty last page and the
    cursor that stops changing. Cap the loop; an unbounded paginator against a
    misbehaving API is an outage you caused.
11. **Store the correlation id** the API returns (`X-Request-Id` or similar) on
    every call. It is what vendor support will ask for, and it cannot be
    recovered later.
12. **Keep credentials in the environment**, referenced by name, never in code,
    config committed to a repository, or a log line.

### Webhooks

13. **Verify the signature before parsing the body**, using the raw bytes. Any
    framework that hands you a re-serialised body has already broken the
    signature.
14. **Respond `2xx` immediately, process asynchronously.** Slow handlers get
    retried, and retries arrive concurrently with the original.
15. **Assume at-least-once delivery and out-of-order arrival.** Deduplicate on
    the event id; never assume the event you received is the latest state — re-
    read if it matters.
16. **Log every received event id and its outcome.** "The webhook never arrived"
    is answerable in seconds with that log and unanswerable without it.

### Debugging an integration that broke

17. **Establish when it last worked**, precisely, with timezones. Then find what
    changed in that window on *both* sides: your deploys, and their changelog
    and status page.
18. **Reproduce with `curl` outside your application.** This splits the problem
    in half: their API versus your client. Do it before reading any of your own
    code.
19. **Compare a working call to a failing one** field by field, headers
    included. The difference is usually in a header nobody was looking at.
20. **Check the boring causes explicitly:** expired credential, rotated secret,
    exhausted quota, clock skew breaking signature validation, an IP allowlist,
    a certificate expiry, a silent API version bump, a trailing whitespace in an
    environment variable.

## Output Template

```
## Integration
<vendor> <api> <version> — docs read <YYYY-MM-DD>
Auth: <scheme>, scopes <list>, credential from $<ENV_VAR>

## Contract as observed
- FACT: <endpoint> returns <shape> — source: response captured <YYYY-MM-DD>
- FACT: documentation says <x>, endpoint returns <y> — divergence, source: <both>

## Failure modes handled
| Status | Meaning here | Response | Retry? |
|---|---|---|---|
| 429 | rate limited | honour Retry-After | yes, backoff, max N |

## Idempotency
<key used, where it comes from, what happens on a duplicate>

## Limits
- <limit> = <value> — source: <header or doc> — checked <YYYY-MM-DD>

## Diagnosis (when debugging)
FACT: last succeeded <timestamp TZ> — source: <log/correlation id>
CONCLUSION: <cause> — established by <the curl that isolates it>

## Not determined
- <what remains unknown, and what access would settle it>
```

## Pitfalls

- Trusting the documentation over the observed response.
- Retrying a non-idempotent write after a timeout.
- Logging the request headers "just for debugging" and shipping it.
- Treating `401` and `403` as one case.
- Testing against production because the sandbox was inconvenient.
- Parsing a webhook body before verifying its signature.
- Assuming webhook events arrive once, in order.
- No timeout on the HTTP client.
- Building a client before making one successful `curl` call.
- Reporting "their API is down" without checking the status page and the
  correlation id.

## Verification

Before delivering, check: every claim about the API's behaviour cites a captured
response or a doc URL with a date; no credential appears in any log line, code
sample or output; every write path states its idempotency key; every retry path
states what it will not retry; the timeout is explicit.
