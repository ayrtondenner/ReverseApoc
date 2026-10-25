## Deferred Items

- 06-16 Task 3: five tests/test_hooks.py tests (plan 06-12) fail in the container. Owner: 06-12 fix round.
  status: open
  **What:** `docker compose run --rm -T build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."`
  gives 5 failed, 2300 passed, 2 skipped (build/gate/06-seed/07-container.log). The host suite passes.
  **Cause 1 (2 tests: test_main_tracks_headers_with_git, test_matching_entry_point_end_to_end):** inside the
  container /work belongs to uid 0 (the Docker Desktop bind mount) and the tests run as `dev` (uid 1000). git
  refuses the repository: `fatal: detected dubious ownership in repository at '/work'` (exit 128). So
  `hooks._git_tracked` raises HookError, and the matching hook blocks with exit 2.
  **Cause 2 (3 tests: test_settings_commands_fail_closed_through_the_hook_shell[0..2]):** `_session_env` drops every
  `UV_*` variable, including the image's `UV_PROJECT_ENVIRONMENT=/opt/venv`. `uv run --frozen --project /work`
  then tries to replace /work/.venv, which is the host's Windows venv on the bind mount, and fails with
  `error: failed to remove directory /work/.venv/Scripts: I/O error (os error 5)`. The handler's `|| exit 2` path
  is taken where the test expects exit 0 with a deny.
  **Not fixed in 06-16:** Task 3 changes no tracked file, and the plan says the fix belongs to the plan that owns
  the file. Possible fixes: make the 06-12 tests container-aware without a skip (the container allows no skip but
  the msvcrt one, ruling F2), have hooks.py pass a scoped `-c safe.directory=<checkout>` to its git call, or add
  `safe.directory /work` in the image. The image is a build-infrastructure change, so it needs the owner's call.
