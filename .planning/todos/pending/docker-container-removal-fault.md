---
title: A Docker container that cannot be removed stops the drive
created: 2026-11-17
area: driver
files: tools/reverseapoc/driver.py
source: run 20261116-fable-ab, 16:56 STOPPED tool (recurrence of night 20261107-030004)
---

# `docker rm -f` failed and the whole drive stopped

Run 20261116-fable-ab stopped with `containers not removed: DriverError: docker rm -f
reverseapoc-attempt-dcb11fb9-0003 failed: exit 1 ... could not kill container: tried to kill
container, but did not receive an exit event`, with about 30 sessions running at once. Four
more attempt containers were left in state Created. The same kind of removal race stopped
night 20261107-030004 at 57 of 100 sessions. Both times the container went away on its own
moments later.

**Do (test first):** retry a failed removal a few times with a short backoff before calling it
a tool failure, and remove an attempt's leftover Created containers by name at the attempt's
reset. Keep the stop when a container still exists after the retries. Note the concurrency in
docs/model-routing.md if the fault tracks the number of parallel sessions.

**Done when:** a fake docker that fails `rm -f` once then succeeds no longer stops a night, and
one that keeps failing still does.
