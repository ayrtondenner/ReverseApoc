"""The wrapper broker of a Codex session (owner ruling 2026-11-11): inside Codex's sandbox the
attempt wrapper only queues its request; the driver runs the real wrapper for it outside.

No test runs Docker or uv: the broker's wrapper is tests/fakewrapper.py, a real child process.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

from reverseapoc import attempt, broker, cli, hooks
from reverseapoc.attempt import AttemptError
from reverseapoc.fileio import write_atomic

HERE = Path(__file__).resolve().parent
WRAPPER = (sys.executable, str(HERE / "fakewrapper.py"))
MATCHING, READABILITY = hooks.SESSION_KINDS[0], hooks.SESSION_KINDS[1]
_WAIT_S = 60  # how long a test waits for the broker's response or the wrapper's start


def _attempt(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A made-up attempt dir with its broker dir, and the session env a Codex session gets
    (this process's own minus every REVERSEAPOC_ variable, plus the claim's dir, the ledger
    outside the attempt dir, the broker dir and the fake wrapper's record)."""
    attempt_dir = tmp_path / "attempt-1"
    (attempt_dir / broker.BROKER_DIR).mkdir(parents=True)
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_bytes(b"")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("REVERSEAPOC_")}
    env.update({attempt.DIR_ENV: str(attempt_dir), attempt.WRAPPER_LEDGER_ENV: str(ledger),
                broker.BROKER_ENV: str(attempt_dir / broker.BROKER_DIR),
                hooks.SESSION_KIND_ENV: MATCHING,
                "FAKEWRAPPER_RECORD": str(tmp_path / "wrapper.jsonl")})  # fmt: skip
    return attempt_dir, env


def _serving(attempt_dir: Path, env: dict, **over) -> broker.Broker:
    values = {"wrapper": WRAPPER, "env": env, "cwd": attempt_dir, "kind": MATCHING, **over}
    return broker.Broker(attempt_dir / broker.BROKER_DIR, **values)


def _records(tmp_path: Path) -> list[dict]:
    path = tmp_path / "wrapper.jsonl"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return [json.loads(line) for line in text.splitlines()]


def _queue(attempt_dir: Path, ident: str, data: bytes) -> str:
    """A request as the client writes it (atomically), named by `ident`; returns the name of
    its response."""
    write_atomic(attempt_dir / broker.BROKER_DIR / f"{ident}{broker.REQUEST_SUFFIX}", data)
    return f"{ident}{broker.RESPONSE_SUFFIX}"


def _response(attempt_dir: Path, name: str) -> dict:
    path = attempt_dir / broker.BROKER_DIR / name
    deadline = time.monotonic() + _WAIT_S
    while not path.is_file():
        assert time.monotonic() < deadline, f"no response {name}"
        time.sleep(0.05)
    return json.loads(path.read_text(encoding="utf-8"))


def _until(predicate) -> None:
    deadline = time.monotonic() + _WAIT_S
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_request_runs_the_real_wrapper_outside_and_relays_its_reply(tmp_path):
    """The client writes one request and gets back the wrapper's stdout, stderr and exit code;
    the driver ran the wrapper with exactly the session's environment minus the broker
    variable, in the attempt dir, so the wrapper's ledger append works there. The request is
    consumed, the response is the driver's file (Broker.files holds its sha256), and a file
    in the broker dir that is no request is never touched."""
    attempt_dir, env = _attempt(tmp_path)
    other = attempt_dir / broker.BROKER_DIR / "notes.txt"
    other.write_text("made up\n", encoding="utf-8")
    with _serving(attempt_dir, env) as served:
        reply = broker.request(["context"], env)
    assert reply == broker.Reply(0, "fake wrapper: context\n", "fake wrapper stderr\n")
    [record] = _records(tmp_path)
    assert record["args"] == ["context"]
    assert Path(record["cwd"]).resolve() == attempt_dir.resolve()
    names = {name.casefold() for name in record["env"]}
    assert names == {name.casefold() for name in env} - {broker.BROKER_ENV.casefold()}
    ledger = Path(env[attempt.WRAPPER_LEDGER_ENV]).read_text(encoding="utf-8")
    assert json.loads(ledger) == {"path": "context.md", "sha256": _sha(attempt_dir / "context.md")}
    left = sorted(p.name for p in (attempt_dir / broker.BROKER_DIR).iterdir())
    [response] = [name for name in left if name != "notes.txt"]
    assert response.endswith(broker.RESPONSE_SUFFIX) and other.is_file()
    assert served.files == {response: _sha(attempt_dir / broker.BROKER_DIR / response)}
    assert served.problems == []


def test_a_check_relays_the_wrappers_exit_code(tmp_path):
    """A check the wrapper logs as a mismatch (exit 1) is exit 1 for the session too."""
    attempt_dir, env = _attempt(tmp_path)
    line = {"n": 1, "exit": 1, "sweep": False, "best_percent": 90.0, "reloc_ok": False,
            "bytes_ok": False, "splice_ok": True, "sweep_hit": None, "source": "checks/0001.c",
            "note": "checks/0001.note.json"}  # fmt: skip
    env["FAKEWRAPPER_CHECK"] = json.dumps(line)
    with _serving(attempt_dir, env):
        reply = broker.request(["check"], env)
    assert (reply.exit, reply.stdout) == (1, "fake wrapper: check\n")
    assert json.loads((attempt_dir / attempt.CHECK_LOG).read_text(encoding="utf-8")) == line


@pytest.mark.parametrize("data", [
    json.dumps({"args": ["check", "--src", "x"]}).encode(),
    json.dumps({"args": ["ls"]}).encode(),
    json.dumps({"args": []}).encode(),
    json.dumps({"args": ["asm", "../orig/UFO2P.EXE"]}).encode(),
    json.dumps({"args": "check"}).encode(),
    json.dumps({"args": ["check"], "env": {"REVERSEAPOC_CLAIM": "tacp/x"}}).encode(),
    json.dumps(["check"]).encode(),
    b"not json",
    b"\xff\xfe",
    json.dumps({"args": ["check"] + ["x" * 64] * 100}).encode(),
])  # fmt: skip
def test_the_broker_refuses_anything_but_an_exact_wrapper_form(tmp_path, data):
    """The driver checks each request against the exact forms the hook allows (no looser
    parser): any other argument list, any other shape, an oversized or undecodable request is
    answered exit 2 naming the refusal, and the wrapper never runs."""
    attempt_dir, env = _attempt(tmp_path)
    with _serving(attempt_dir, env):
        doc = _response(attempt_dir, _queue(attempt_dir, "00000000000000a1", data))
    assert doc["exit"] == attempt.EXIT_TOOL and doc["stdout"] == ""
    assert "the broker refused the request" in doc["stderr"], doc
    assert _records(tmp_path) == []


def test_a_readability_session_gets_no_matching_only_form(tmp_path):
    """The forms are the session kind's (hooks.forms_for): a readability session's giveup is
    refused, its check runs."""
    attempt_dir, env = _attempt(tmp_path)
    with _serving(attempt_dir, env, kind=READABILITY):
        refused = _response(attempt_dir, _queue(attempt_dir, "00000000000000b1",
                                                json.dumps({"args": ["giveup"]}).encode()))
        ran = _response(attempt_dir, _queue(attempt_dir, "00000000000000b2",
                                            json.dumps({"args": ["check"]}).encode()))
    assert refused["exit"] == attempt.EXIT_TOOL and "accepts only" in refused["stderr"]
    assert ran["exit"] == 0
    assert [r["args"] for r in _records(tmp_path)] == [["check"]]


def test_the_wait_covers_the_wrappers_longest_run():
    """A check may run its container for CHECK_TIMEOUT and remove it for RM_TIMEOUT (the Bash
    tool's CHECK_TIMEOUT_MS covers both); the broker's own bound on one wrapper run covers
    that, and the client waits longer than the broker's bound."""
    longest = attempt.CHECK_TIMEOUT + attempt.RM_TIMEOUT
    assert broker.RUN_TIMEOUT_S >= hooks.CHECK_TIMEOUT_MS / 1000 > longest
    assert broker.WAIT_S > broker.RUN_TIMEOUT_S


def test_the_client_gives_up_with_exit_2_after_its_bounded_wait(tmp_path, monkeypatch, capsys):
    """No broker serving: the client stops waiting after WAIT_S and the wrapper exits 2 naming
    the wait (never a hang, never a pass)."""
    attempt_dir, env = _attempt(tmp_path)
    ticks = iter(range(0, 10**6, 100))
    with pytest.raises(AttemptError, match="no response from the driver's broker"):
        broker.request(["check"], env, clock=lambda: next(ticks), sleep=lambda s: None)
    for name in [k for k in os.environ if k.upper().startswith("REVERSEAPOC_")]:
        monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(broker, "WAIT_S", 0.3)
    assert cli.main(["attempt", "context"]) == attempt.EXIT_TOOL
    assert "no response from the driver's broker" in capsys.readouterr().err


@pytest.mark.parametrize("where", ["elsewhere", "attempt-1", "attempt-1/broker/x", None])
def test_the_client_refuses_any_broker_dir_but_its_attempts(tmp_path, where):
    """REVERSEAPOC_WRAPPER_BROKER must name the existing <attempt dir>/broker; anything else
    (another dir, the attempt dir itself, a dir below it, a broker dir that does not exist)
    is refused before any request is written."""
    attempt_dir, env = _attempt(tmp_path)
    if where is None:
        (attempt_dir / broker.BROKER_DIR).rmdir()
    else:
        env[broker.BROKER_ENV] = str(tmp_path / where)
        (tmp_path / where).mkdir(parents=True, exist_ok=True)
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    with pytest.raises(AttemptError, match=broker.BROKER_ENV):
        broker.request(["context"], env)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == before


def _session_env(monkeypatch, env: dict) -> None:
    for name in [k for k in os.environ if k.upper().startswith("REVERSEAPOC_")]:
        monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def test_the_attempt_verb_forwards_to_the_broker(tmp_path, monkeypatch, capsys):
    """`reverseapoc attempt <form>` with the broker variable set queues the request and prints
    the reply (the env names no claim, so the wrapper could not have run in this process)."""
    attempt_dir, env = _attempt(tmp_path)
    _session_env(monkeypatch, env)
    with _serving(attempt_dir, env):
        code = cli.main(["attempt", "asm", "func_00010010"])
    out, err = capsys.readouterr()
    assert (code, out, err) == (0, "fake wrapper: asm func_00010010\n", "fake wrapper stderr\n")
    assert [r["args"] for r in _records(tmp_path)] == [["asm", "func_00010010"]]


def test_the_attempt_verb_refuses_a_non_form_before_queueing(tmp_path, monkeypatch, capsys):
    """The client's own form check still runs first: a readability session's giveup exits 2
    and writes no request."""
    attempt_dir, env = _attempt(tmp_path)
    env[hooks.SESSION_KIND_ENV] = READABILITY
    _session_env(monkeypatch, env)
    assert cli.main(["attempt", "giveup"]) == attempt.EXIT_TOOL
    assert "accepts only" in capsys.readouterr().err
    assert list((attempt_dir / broker.BROKER_DIR).iterdir()) == []


def test_stop_kills_the_running_wrapper_and_answers_every_request(tmp_path):
    """When the session ends the broker stops: the wrapper still running is killed (as the
    session's own tree would be) and answered exit 2, a request still queued is answered exit
    2 without running, and every response is a recorded driver file."""
    attempt_dir, env = _attempt(tmp_path)
    env["FAKEWRAPPER_SLEEP"] = "60"
    served = _serving(attempt_dir, env)
    with served:
        first = _queue(attempt_dir, "00000000000000c1", json.dumps({"args": ["check"]}).encode())
        _until(lambda: len(_records(tmp_path)) == 1)
        second = _queue(attempt_dir, "00000000000000c2", json.dumps({"args": ["check"]}).encode())
        start = time.monotonic()
    assert time.monotonic() - start < 30
    killed, ended = _response(attempt_dir, first), _response(attempt_dir, second)
    assert killed["exit"] == ended["exit"] == attempt.EXIT_TOOL
    assert "the session ended" in killed["stderr"] and "the session ended" in ended["stderr"]
    assert len(_records(tmp_path)) == 1
    assert set(served.files) == {first, second}


def test_a_wrapper_over_the_brokers_bound_is_killed(tmp_path):
    """A wrapper run longer than the broker's bound is killed and answered exit 2."""
    attempt_dir, env = _attempt(tmp_path)
    env["FAKEWRAPPER_SLEEP"] = "60"
    start = time.monotonic()
    with _serving(attempt_dir, env, timeout_s=1):
        reply = broker.request(["check"], env)
    assert time.monotonic() - start < 30
    assert reply.exit == attempt.EXIT_TOOL and "ran longer than 1 s" in reply.stderr


def test_a_wrapper_that_cannot_start_is_exit_2(tmp_path):
    """A wrapper executable that is not there is a tool error the session sees (exit 2)."""
    attempt_dir, env = _attempt(tmp_path)
    with _serving(attempt_dir, env, wrapper=(str(tmp_path / "no-such-uv.exe"),)):
        reply = broker.request(["context"], env)
    assert reply.exit == attempt.EXIT_TOOL and "could not start the wrapper" in reply.stderr
