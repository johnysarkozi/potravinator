# foodmania-frontend — how to run and test it

Onboarding notes for `https://gitlab.com/snorchel/foodmania-frontend.git`, the
frontend of **Potravinátor** (Czech grocery price comparator, `potravinator.cz`).

Verified end-to-end against the **production API** on 2026-08-23:
`pnpm install` → `pnpm dev` → real shops, categories, product search and CDN
images; `pnpm build` passes.

> Read this before the repo's own `README.md`. That file is the unmodified
> **BoroBazar** template documentation the project was forked from. Several of
> its instructions are wrong for this fork — see [Where the README lies](#where-the-readme-lies).

---

## 1. Quick start

```bash
git clone https://gitlab.com/snorchel/foodmania-frontend.git
cd foodmania-frontend

# Env file is NOT in the repo and NOT templated there. Create it:
cp <this-repo>/docs/foodmania.env.local.template .env.local

pnpm install
pnpm dev            # http://localhost:3000
```

Requirements: Node >= 18.17 (verified on Node 22), pnpm (verified on 10.x).

There is also a Docker path (`makefile` + `docker-compose.yaml`): `make install`
then `make run`. It mounts `~/.ssh` and expects a macOS-style SSH-agent socket
(`/run/host-services/ssh-auth.sock`), so on Linux plain `pnpm dev` is smoother.

---

## 2. The env file is the whole problem

This is the only genuinely hard part of onboarding, so it is worth being
explicit. Everything else is a stock Next.js app.

`.env.local` is gitignored and **no template ships in the repo**, so a fresh
clone starts with zero API configuration and fails silently — components render
their loading skeletons forever with no obvious error.

The values are in `docs/foodmania.env.local.template` next to this file. Two
things about them are non-obvious enough to call out:

**Two API base URLs, both required.** The codebase has two axios instances that
grew up at different times and read *different* env vars:

| File | Env var | Used by |
| --- | --- | --- |
| `src/framework/basic-rest/utils/endpoints.ts` | `NEXT_PUBLIC_REST_ENDPOINT` | the live code paths (shops, shopping lists, categories, product variants) |
| `src/framework/basic-rest/utils/http.ts` | `NEXT_PUBLIC_REST_API_ENDPOINT` | older/legacy hooks |

Set both to `https://backend.potravinator.cz`. Setting only one leaves half the
hooks pointing at a relative URL.

**Leave `NEXT_PUBLIC_BASE_AUTH` and `NEXT_PUBLIC_THUMBOR_SECURITY_KEY` empty.**
Both are optional, and a wrong value is worse than no value:

- `NEXT_PUBLIC_BASE_AUTH` is turned into an `Authorization: Basic …` header by
  the `endpoints.ts` interceptor. The API host does not need it. What *is*
  behind nginx basic auth is the **frontend** vhost `www.potravinator.cz`
  (`WWW-Authenticate: Basic realm="Restricted Access"`) — a different host that
  the API client never talks to. Easy to conflate: if you hit
  `www.potravinator.cz` in a browser and get a password prompt, that is the
  staging lock on the site, not the API.
- `NEXT_PUBLIC_THUMBOR_SECURITY_KEY` empty makes `thumbor-client` emit
  `/unsafe/...` URLs, which `images.potravinator.cz` accepts. A wrong key
  produces signed URLs that fail on every image.

---

## 3. Which host is the production API

`backend.potravinator.cz`. Worth writing down, because there are four
plausible-looking hosts and only one works:

| Host | Reality |
| --- | --- |
| `backend.potravinator.cz` | **The API.** API Platform, `application/ld+json`, open for reads. |
| `www.potravinator.cz` | The frontend. Behind nginx basic auth (401). Not an API. |
| `api.potravinator.cz` | Resolves to a *different* IP and 404s on every path. Not the API. |
| `foodmania-backend.inovent.sk` | Legacy vhost on the same box as prod. TLS cert no longer covers it, so it fails cert validation. Stale — it appears in old config. |

Sanity check that does not need the app:

```bash
curl -s "https://backend.potravinator.cz/countries/1/categories?page=1&itemsPerPage=3"
curl -s -o /dev/null -w '%{http_code}\n' https://backend.potravinator.cz/countries/1/shops   # 200
```

The API is API-Platform style: collections are JSON-LD (`@context`, `member`),
and IDs are **numeric** — `/categories/2`, not `/categories/mlecne-a-chlazene`.
Country `1` is the one the app hardcodes, and it returns Czech data (`/countries`
itself is not exposed, so the ID is not discoverable from the API root).
`POST /users` and `POST /shopping_lists` accept
`Content-Type: application/json` and return `201`.

---

## 4. Testing a new frontend feature

`pnpm dev` has hot reload, so the normal loop is just editing and watching the
browser. The flow that exercises most of the data layer:

1. `http://localhost:3000` → click **Vyzkoušet**.
   Fires `GET /countries/1/shops`, `POST /users` (anonymous user, 201),
   `POST /shopping_lists` (201), then routes to `/shopping-list/<uuid>`.
2. Pick a shop (Billa / Albert / Rohlik / Košík / Tesco) → **Začít vytvářet seznam**.
   Fires `GET /countries/1/categories?...&exists[parent]=false`.
3. Type in the search box, e.g. `mléko`.
   Fires `GET /product_variants?page=1&itemsPerPage=48&shop.id=1&fulltext=mléko`
   plus thumbor image requests.
4. Category browsing: `/category/2` (numeric ID — a slug 404s).

Useful checks:

```bash
pnpm build          # passes
pnpm lint
pnpm check-types    # FAILS - see below, this is pre-existing
pnpm format         # prettier --write, husky + lint-staged run this on commit
```

There is **no test framework** in this project — no Jest/Vitest/Playwright, and
`pnpm test-all` is just `check-format && lint && check-types && build`. Testing
a feature means driving it in the browser.

### `pnpm check-types` is already broken

58 pre-existing TypeScript errors on a clean `main`. Do not treat this as
something you broke. It does not block a build, because `next.config.js` sets
`typescript.ignoreBuildErrors` and `eslint.ignoreDuringBuilds` when
`NODE_ENV === 'production'` — so **type and lint errors never fail the
production build**. Nothing is enforcing type safety in CI; keep an eye on your
own diff rather than the aggregate count.

---

## 5. Where the README lies

The repo `README.md` / `DOCUMENTATION.md` are the upstream BoroBazar template
docs. Specifically wrong for this fork:

- **"rename `.env.local.template` to `.env.local`"** — no such file exists.
  That is why this guide ships one.
- **"we fetch data from public json, no real REST integration"** — false. There
  is a real API (§3).
- Documented env var names (`NEXT_PUBLIC_REST_API_ENDPOINT` only) are
  incomplete; the live var is `NEXT_PUBLIC_REST_ENDPOINT` (§2).
- `vercel.json` still contains stock template values pointing at
  `borobazar.vercel.app` with `"Put your stripe public key here"` placeholders.
  It is dead config — production deploys via pm2, not Vercel (see
  `ecosystem.config.js`: pm2 to `159.65.124.249`, pulling
  `.env.production.local` from a `shared/` dir on the server).
- The BoroBazar folder tour is broadly still accurate; the data-fetching section
  is not.

---

## 6. Things worth knowing before you touch code

- **A lot of the tree is unused template code.** The BoroBazar demo components
  (wishlist, orders, signin/signup, shops pages, Stripe checkout) still build
  and appear in the route list, but are not part of the Potravinátor flow.
  Check whether a component is actually reachable from `src/app` before
  "fixing" it.
- **`src/framework/basic-rest/category/get-all-categories.tsx` has a hardcoded
  `http://localhost/countries/...` URL** (line 26). Because it is an *absolute*
  URL, axios ignores the configured `baseURL`, so this hook can never reach a
  real API. It is currently harmless — the components that call it
  (`category-grid-block`, `hero-banner-with-category`, `category-filter`, …) are
  all unreachable template leftovers, and the one live component that imports it
  (`category-small-menu-mobile`) imports it without calling it. Live category
  data comes from `api-shopping-list.tsx` instead. Treat it as a landmine: wire
  up any of those components and you get requests to the developer's own
  machine. Fix it to a relative URL if you ever need it.
- The same file caches categories in `localStorage` **with no expiry**. If
  category data looks stale while developing, clear site data.
- `middleware.js` has had its i18n redirect removed, so there is no `/{lang}`
  prefix in URLs even though the i18n plumbing is still present.
- Commits run husky + lint-staged (prettier + eslint on staged files).

---

## 7. Note on the git history

A `.env.production` file was committed to this repo's history and later removed.
It is worth knowing it is there, but it is **not** a credential leak: the
`NEXT_PUBLIC_GOOGLE_API_KEY` and `NEXT_PUBLIC_STRIPE_PUBLIC_KEY` values in it are
Slovak-language placeholders ("Vaš …"), not real keys. Nothing needs rotating.

Its only real content is endpoints, and they are stale:
`foodmania-backend.inovent.sk` and `foodmania.inovent.sk`. Both still resolve to
the production box (`159.65.124.249`) but the TLS cert no longer covers those
names, so they fail cert validation. If you find those hostnames anywhere, they
are leftovers — the current API is `backend.potravinator.cz` (§3).

The live production secrets are not in git at all: `ecosystem.config.js` copies
`.env.production.local` from a `shared/` directory on the deploy host.
