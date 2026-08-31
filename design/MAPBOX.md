# Mapbox — the published style and its credentials

Supplied by the owner on 2026-08-31, completing the package (README.md
shipped the style URL but no token). Used by the public surface only —
see `frontend/src/features/public/mapCore.ts` and the amendment in
`DECISIONS.md` (c).

## Map configuration

| Key | Value |
| --- | --- |
| Style URL | `mapbox://styles/chargeworthy/cmtcw48t4002401s146owc0tv` |
| Style name | Dark 2D (built on Mapbox Standard) |
| Access token | `pk.…` public token — **not stored in git**; see below |
| Map library | Mapbox GL JS |
| Library version | 3.27.0 (pinned in `frontend/package.json`) |

The style's saved camera (centre `[2.2937, 48.8583]`, zoom 14, bearing
−12.8) is Mapbox Studio's Paris default and is ignored — every map in the
app sets its own centre and zoom.

## Where the token lives (not here)

`pk.` tokens are Mapbox's client-side tokens: they ship in the served
JavaScript bundle and are visible in any visitor's network tab, so keeping
the value out of git changes nothing about its real exposure. Its control is
**URL restriction**, not secrecy. It is kept out of git only so GitHub's
secret scanner does not block the push — the value is injected at build time
from an env var instead:

| Where | How |
| --- | --- |
| Local dev | `frontend/.env.local` → `VITE_MAPBOX_TOKEN=pk.…` (gitignored; copy `frontend/.env.example`) |
| HF Space | a Space **Variable** named `VITE_MAPBOX_TOKEN` (Settings → Variables, *not* Secrets — it is public). The Dockerfile reads it as a build ARG. |

The owner holds the token value. `frontend/src/features/public/mapCore.ts`
reads it via `import.meta.env.VITE_MAPBOX_TOKEN`; absent, maps render an
empty panel and the page still works.

**Owner action, before traffic arrives:** in the Mapbox console
(Account → Tokens), restrict the token to:

- `https://talk-to-nitara.hf.space/*`
- `http://localhost:*` (development)

Rotating the token means changing the env value in the two places above —
never in git.

## Cost

Map loads are metered per session on the Mapbox account (free tier:
50,000 loads/month as of 2026). Browser-side loads cannot write
`api_usage_events` rows (AGENTS.md rule 10) — the Mapbox dashboard is the
meter for this one spend, accepted in `DECISIONS.md` (c), amended.
The geocoding API is deliberately NOT used: search is navigation-only
Nominatim, and the confirmation card uses this repo's own resolver.
