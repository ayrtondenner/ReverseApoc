# Build image

Ubuntu 24.04 (pinned by digest), x86-64 only. Every tool version is pinned in `Dockerfile`.

## In the image

- uv 0.12.23 and Python 3.14.5 (installed by uv into `/opt/uv-python`)
- ninja, GNU binutils (as, ld, objdump), clang-format, clangd, git, curl, xz-utils, unzip
- wibo 1.2.0 (runs Win32 console programs such as the Watcom compiler)
- objdiff-cli v3.8.2 (sha256-verified)
- Open Watcom v2 (2026-10-01 snapshot) in `/opt/watcom-v2`; only `wdis`, `wlink`, `wlib` are on PATH. Its compiler is not used for matching.
- Non-root user `dev` (uid 1000), working directory `/work`

Not in the image: the Watcom 10.x compiler, the game files, the project source.

## Mounted at runtime

| Host | Container | Mode |
|---|---|---|
| `.` (repo) | `/work` | rw |
| `./orig` | `/work/orig` | ro (your game executables) |
| `./third_party/watcom` | `/work/watcom` | ro (your Watcom 10.x install) |
| `.env` | environment | optional |

`orig/` and `third_party/watcom/` are gitignored. Create them yourself before the first run
(`mkdir -p orig third_party/watcom`); otherwise Docker creates them as root-owned empty directories.
The Python venv (`/opt/venv`) and uv cache are named volumes, so no Linux venv appears in the checkout.

## Run

From the repo root:

```sh
docker compose build
docker compose run --rm build            # interactive bash in /work
docker compose run --rm build uv sync --locked
docker compose run --rm test             # uv sync --locked && uv run pytest -q
```
