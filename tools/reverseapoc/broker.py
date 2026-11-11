# SPDX-License-Identifier: GPL-3.0-or-later
"""The wrapper broker of a Codex session (owner ruling 2026-11-11, spike 012).

Codex runs every command of a session in its Windows sandbox (workspace-write rooted at the
attempt dir, network off), which refuses the attempt wrapper's ledger append (the ledger lies
outside the workspace, by design) and Docker's pipe, so `attempt check` could never compile
there. The sandbox stays as it is; instead, inside a Codex session the wrapper only queues its
request and the driver, outside the sandbox, runs the real wrapper for it:

- the client (`request`, reached from `reverseapoc attempt <form>` when REVERSEAPOC_WRAPPER_BROKER
  is set, only in a Codex session) writes one request, `<id>.request.json` holding
  {"args": [...]}, atomically into the session's broker dir <attempt dir>/broker, then waits
  for `<id>.response.json` ({"exit", "stdout", "stderr"}) at most WAIT_S and hands it back;
- the driver serves that dir while the session runs (`Broker`, one request at a time): it
  consumes each request, checks it against the exact forms the hook allows (attempt.form_allowed,
  hooks.forms_for of the session's kind; anything else is answered exit 2), runs the real
  wrapper outside the sandbox with the session's environment minus the broker variable and
  cwd the attempt dir (so the wrapper's ledger append and Docker work there), bounded by
  RUN_TIMEOUT_S, and writes the response atomically. It records every response it writes
  (`files`: name and sha256), which the audit takes for the driver's own files. When the
  session ends the broker stops: a wrapper still running is killed (as the session's own tree
  is) and every request left is answered exit 2 without running.

The model never runs Docker or anything but the wrapper forms; a request the model forged
with its edit tool is still only one of those forms, and the audit flags that write.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import attempt
from .attempt import DIR_ENV, AttemptError
from .check import EXIT_TOOL
from .fileio import is_link, write_atomic
from .hooks import CHECK_TIMEOUT_MS
from .session import _group_options, kill_tree

BROKER_ENV = "REVERSEAPOC_WRAPPER_BROKER"  # set by the driver for a Codex session only
BROKER_DIR = "broker"  # <attempt dir>/broker: inside the workspace, so the sandbox can write it
REQUEST_SUFFIX = ".request.json"
RESPONSE_SUFFIX = ".response.json"
_ID_BYTES = 8  # a request's id: 16 hex digits
_REQUEST_NAME = re.compile(rf"[0-9a-f]{{{2 * _ID_BYTES}}}{re.escape(REQUEST_SUFFIX)}")
REQUEST_CAP = 4096  # bytes; the longest wrapper form is a few dozen
# The bound on one wrapper run: the Bash tool's cap a Claude session's wrapper runs under, which
# covers a check's container run and its removal (attempt.CHECK_TIMEOUT + RM_TIMEOUT).
RUN_TIMEOUT_S = CHECK_TIMEOUT_MS / 1000
WAIT_S = RUN_TIMEOUT_S + 60  # the client's wait: one run, its kill and the response write
POLL_S = 0.2  # how often the client and the broker look for a file
_REAP_S = 10.0  # after a kill, how long to wait for the wrapper's output
_ERROR = "reverseapoc attempt: error: "
_ENDED = f"{_ERROR}the session ended before the broker could answer\n"


@dataclass(frozen=True)
class Reply:
    """What the real wrapper left: its exit code, stdout and stderr."""

    exit: int
    stdout: str
    stderr: str

    def to_bytes(self) -> bytes:
        doc = {"exit": self.exit, "stdout": self.stdout, "stderr": self.stderr}
        return json.dumps(doc, sort_keys=True).encode("utf-8")


def _refusal(why: str) -> Reply:
    return Reply(EXIT_TOOL, "", f"{_ERROR}the broker refused the request: {why}\n")


# ---- the client: inside the session's sandbox ----


def broker_dir(env: Mapping[str, str]) -> Path:
    """REVERSEAPOC_WRAPPER_BROKER, which must name the existing <attempt dir>/broker of
    REVERSEAPOC_ATTEMPT_DIR (resolved: a link there resolves elsewhere and is refused)."""
    value = env.get(BROKER_ENV) or ""
    home = env.get(DIR_ENV) or ""
    path = Path(value).resolve() if value else None
    if not home or path is None or path != Path(home).resolve() / BROKER_DIR or not path.is_dir():
        raise AttemptError(f"{BROKER_ENV} {value!r} is not the existing directory {BROKER_DIR}/ "
                           f"of {DIR_ENV} {home!r}")  # fmt: skip
    return path


def _reply(data: bytes, path: Path) -> Reply:
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError
        raise AttemptError(f"the broker's response {path} is not UTF-8 JSON: {exc}") from exc
    shape = isinstance(doc, dict) and set(doc) == {"exit", "stdout", "stderr"}
    if not (shape and type(doc["exit"]) is int and isinstance(doc["stdout"], str)
            and isinstance(doc["stderr"], str)):  # fmt: skip
        raise AttemptError(f"the broker's response {path} is not "
                           '{"exit": int, "stdout": str, "stderr": str}')  # fmt: skip
    return Reply(doc["exit"], doc["stdout"], doc["stderr"])


def request(args: Sequence[str], env: Mapping[str, str], *,
            clock: Callable[[], float] = time.monotonic,
            sleep: Callable[[float], None] = time.sleep) -> Reply:  # fmt: skip
    """Queue `args` (what follows `attempt`) for the driver's broker and wait for its reply, at
    most WAIT_S on `clock`. A broker dir that is not the attempt's, no response in time or a
    malformed one is an AttemptError (the CLI's exit 2)."""
    directory = broker_dir(env)
    ident = secrets.token_hex(_ID_BYTES)
    write_atomic(directory / f"{ident}{REQUEST_SUFFIX}",
                 json.dumps({"args": list(args)}).encode("utf-8"))  # fmt: skip
    response = directory / f"{ident}{RESPONSE_SUFFIX}"
    wait = WAIT_S
    deadline = clock() + wait
    while not response.is_file():
        if clock() >= deadline:
            raise AttemptError(f"no response from the driver's broker in {wait:g} s "
                               f"({response})")  # fmt: skip
        sleep(POLL_S)
    return _reply(response.read_bytes(), response)


# ---- the server: the driver, outside the sandbox ----


def _parse_request(data: bytes) -> list[str]:
    """A request's argument list; ValueError naming why it is not one."""
    if len(data) > REQUEST_CAP:
        raise ValueError(f"more than {REQUEST_CAP} bytes")
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError
        raise ValueError(f"not UTF-8 JSON ({exc})") from exc
    if not isinstance(doc, dict) or set(doc) != {"args"}:
        raise ValueError('not {"args": [...]}')
    args = doc["args"]
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("args is not a list of strings")
    return args


def _mtime(path: Path) -> tuple[int, str]:
    return path.stat().st_mtime_ns, path.name


class Broker:
    """Serves the broker dir `directory` of one Codex session while it runs (a context
    manager: entering starts serving, leaving stops it). `wrapper` is the real wrapper's argv
    prefix (the resolved `uv run --frozen reverseapoc attempt`), `env` the session's
    environment (the broker variable is dropped), `cwd` the attempt dir and `kind` the session
    kind whose forms are allowed. `files` maps each response written to its sha256;
    `problems` names each failure the broker hit (never silent: the driver reports them)."""

    def __init__(self, directory: Path, *, wrapper: Sequence[str], env: Mapping[str, str],
                 cwd: Path, kind: str, timeout_s: float = RUN_TIMEOUT_S) -> None:  # fmt: skip
        self.directory = directory
        self.files: dict[str, str] = {}
        self.problems: list[str] = []
        self._wrapper = tuple(wrapper)
        self._env = {name: value for name, value in env.items() if name != BROKER_ENV}
        self._cwd = cwd
        self._kind = kind
        self._timeout_s = timeout_s
        self._done: set[str] = set()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> Broker:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def stop(self) -> None:
        """Stop serving: kill a wrapper still running, then answer every request left exit 2
        without running it."""
        self._stop.set()
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                kill_tree(self._proc.pid)
        self._thread.join()
        self._pass(ended=True)

    def _problem(self, text: str) -> None:
        if text not in self.problems:
            self.problems.append(text)

    def _serve(self) -> None:
        while not self._stop.is_set():
            self._pass(ended=False)
            self._stop.wait(POLL_S)

    def _requests(self) -> list[Path]:
        """The requests not yet answered, oldest first: regular files (never a link) named as
        the client names them; nothing when the broker dir is a link."""
        if is_link(self.directory) or not self.directory.is_dir():
            return []
        found = [path for path in self.directory.iterdir()
                 if _REQUEST_NAME.fullmatch(path.name) and path.name not in self._done
                 and not is_link(path) and path.is_file()]  # fmt: skip
        return sorted(found, key=_mtime)

    def _pass(self, *, ended: bool) -> None:
        try:
            pending = self._requests()
        except OSError as exc:
            self._problem(f"the broker dir {self.directory}: {type(exc).__name__}: {exc}")
            return
        for path in pending:
            if self._stop.is_set() and not ended:
                return  # stop() answers the rest
            try:
                self._answer(path, ended=ended)
            except Exception as exc:  # noqa: BLE001 - recorded, the driver reports it
                self._problem(f"{path.name}: {type(exc).__name__}: {exc}")

    def _answer(self, path: Path, *, ended: bool) -> None:
        """Consume the request at `path`, then write its response (exit 2 when `ended`)."""
        self._done.add(path.name)
        with path.open("rb") as fh:
            data = fh.read(REQUEST_CAP + 1)
        path.unlink()
        reply = Reply(EXIT_TOOL, "", _ENDED) if ended else self._reply_for(data)
        if is_link(self.directory):
            raise OSError(f"the broker dir {self.directory} became a link")
        name = path.name.removesuffix(REQUEST_SUFFIX) + RESPONSE_SUFFIX
        body = reply.to_bytes()
        write_atomic(self.directory / name, body)
        self.files[name] = hashlib.sha256(body).hexdigest()

    def _reply_for(self, data: bytes) -> Reply:
        try:
            args = _parse_request(data)
        except ValueError as exc:
            return _refusal(str(exc))
        if not attempt.form_allowed(args, self._kind):
            return _refusal(f"accepts only: {attempt.forms_text(self._kind)}")
        return self._run(args)

    def _run(self, args: Sequence[str]) -> Reply:
        """The real wrapper for `args`, outside the sandbox, at most `timeout_s`; its whole
        tree is killed past that or when the broker stops."""
        argv = [*self._wrapper, *args]
        try:
            proc = subprocess.Popen(argv, cwd=self._cwd, env=self._env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                    errors="replace", **_group_options())  # fmt: skip
        except OSError as exc:
            return Reply(EXIT_TOOL, "", f"{_ERROR}the broker could not start the wrapper "
                                        f"{argv[0]}: {exc}\n")  # fmt: skip
        with self._lock:
            self._proc = proc
            if self._stop.is_set():
                kill_tree(proc.pid)
        late = ""
        try:
            out, err = proc.communicate(timeout=self._timeout_s)
        except subprocess.TimeoutExpired:
            kill_tree(proc.pid)
            out, err = _reaped(proc)
            late = f"{_ERROR}the wrapper ran longer than {self._timeout_s:g} s and was stopped\n"
        finally:
            with self._lock:
                self._proc = None
        if self._stop.is_set():
            return Reply(EXIT_TOOL, out, err + _ENDED)
        if late:
            return Reply(EXIT_TOOL, out, err + late)
        return Reply(proc.returncode, out, err)


def _reaped(proc: subprocess.Popen) -> tuple[str, str]:
    """A killed wrapper's output; none when a survivor still holds its pipes after _REAP_S."""
    try:
        return proc.communicate(timeout=_REAP_S)
    except subprocess.TimeoutExpired:
        return "", f"{_ERROR}the killed wrapper's output was not collected\n"
