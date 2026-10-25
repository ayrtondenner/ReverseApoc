## Deferred Items

- 06-16 Task 3: five tests/test_hooks.py tests (plan 06-12) failed in the container.
  status: resolved
  **Resolved by:** `f9222ad` fix(06-16), orchestrator ruling F2b. These were test-environment defects, fixed in
  tests/test_hooks.py only; hooks.py, the image, compose, the Dockerfile and the build scripts are unchanged.
  After the fix, build/gate/06-seed/07b-container.log gives 2305 passed, 2 skipped (msvcrt only), ruff clean,
  `exit=0`.
  **What:** `docker compose run --rm -T build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."`
  gave 5 failed, 2300 passed, 2 skipped (build/gate/06-seed/07-container.log). The host suite passed.
  **Cause 1 (2 tests: test_main_tracks_headers_with_git, test_matching_entry_point_end_to_end):** inside the
  container /work belongs to uid 0 (the Docker Desktop bind mount) and the tests run as `dev` (uid 1000). git
  refused the repository: `fatal: detected dubious ownership in repository at '/work'` (exit 128). So
  `hooks._git_tracked` raised HookError, and the matching hook blocked with exit 2. Fix: both tests give their
  git `safe.directory=*` through GIT_CONFIG_COUNT/KEY_0/VALUE_0 in the environment (monkeypatch.setenv, or the
  subprocess env), as tests/test_githooks.py does. The hook itself still fails closed when git refuses.
  **Cause 2 (3 tests: test_settings_commands_fail_closed_through_the_hook_shell[0..2]):** `_session_env` dropped
  every `UV_*` variable, including the image's `UV_PROJECT_ENVIRONMENT=/opt/venv`. `uv run --frozen --project /work`
  then tried to replace /work/.venv, the host's Windows venv on the bind mount, and failed with
  `error: failed to remove directory /work/.venv/Scripts: I/O error (os error 5)`. Fix: `_session_env` keeps
  UV_PROJECT_ENVIRONMENT when it is set, and still drops every other UV_* variable.
