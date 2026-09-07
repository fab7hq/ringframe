"""`ringframe` command line. Every command prints one JSON object with --json; exit codes:
0 ok, 1 usage, 2 refused by a rule, 3 needs input, 4 internal."""

import argparse
import json
import sys
import tarfile
from pathlib import Path

from ringframe import __version__, ask, config, deltas, evaluate, profiles, seal, sessions, store, workspace
from ringframe.ask import NeedsInput
from ringframe.seal import Refused
from ringframe.store import LedgerError


def _json_arg(text: str):
    """Inline JSON or @file."""
    if text.startswith("@"):
        text = Path(text[1:]).read_text(encoding="utf-8")
    return json.loads(text)


def _emit(obj, as_json=True):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    elif isinstance(obj, str):
        print(obj, end="" if obj.endswith("\n") else "\n")
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))


def _actor(text: str | None, authority: str) -> dict:
    kind, _, ident = (text or "human:local-user").partition(":")
    return {"kind": kind, "id": ident or "local-user", "authority": authority}


def _links(items):
    out = []
    for item in items or []:
        rel, _, target = item.partition(":")
        out.append({"rel": rel, "id": target})
    return out


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors exit 1, not argparse's default 2
        self.print_usage(sys.stderr)
        print(f"ringframe: error: {message}", file=sys.stderr)
        raise SystemExit(1)


GLOBAL_FLAGS = {"--json": 0, "--workspace": 1, "--actor": 1, "--authority": 1}


def _hoist_globals(argv):
    """Allow global options anywhere on the line (argparse only accepts them before the subcommand)."""
    front, rest, i = [], [], 0
    while i < len(argv):
        n = GLOBAL_FLAGS.get(argv[i])
        if n is None:
            rest.append(argv[i]); i += 1
        else:
            front += argv[i:i + 1 + n]; i += 1 + n
    return front + rest


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="ringframe", description=__doc__)
    p.add_argument("--version", action="version", version=f"ringframe {__version__}")
    p.add_argument("--workspace", type=Path, help="workspace root (default: git worktree root or cwd)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--actor", help="kind:id, default human:local-user")
    p.add_argument("--authority", choices=["interactive", "preauthorized"], default="interactive")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    prof = sub.add_parser("profile").add_subparsers(dest="sub", required=True)
    ps = prof.add_parser("show")
    ps.add_argument("--host", required=True)
    ps.add_argument("--version", dest="host_version", default="")

    a = sub.add_parser("ask").add_subparsers(dest="sub", required=True)
    c = a.add_parser("compile")
    c.add_argument("--staged", required=True, type=Path)
    c.add_argument("--title", required=True)
    c.add_argument("--capability", required=True)
    c.add_argument("--classification", required=True)
    c.add_argument("--route", required=True)
    c.add_argument("--host", required=True)
    c.add_argument("--link", action="append", help="revises:<ask_id> | remediates:<evl_id>")
    c.add_argument("--limitation", action="append")
    cf = a.add_parser("confirm")
    cf.add_argument("--ask", required=True)
    cn = a.add_parser("cancel")
    cn.add_argument("--ask", required=True)
    cn.add_argument("--reason")
    cn.add_argument("--attributed", action="store_true", help="recorded later by the person, not by the skill during the Ask turn")
    sm = a.add_parser("submitted")
    sm.add_argument("--ask", required=True)
    sm.add_argument("--as-modified", action="store_true")
    cp = a.add_parser("copy")
    cp.add_argument("--ask", required=True)
    d = a.add_parser("delivery")
    d.add_argument("--from-hook", action="store_true")
    d.add_argument("--ask")
    d.add_argument("--handoff", action="store_true")
    d.add_argument("--state", choices=["delivery_failed", "unavailable"])
    d.add_argument("--reason", default="")
    s = a.add_parser("show")
    s.add_argument("--ask")
    s.add_argument("--session")
    r = a.add_parser("resolve")
    r.add_argument("--session")
    r.add_argument("--kind", default="ask")

    e = sub.add_parser("eval").add_subparsers(dest="sub", required=True)
    f = e.add_parser("freeze")
    f.add_argument("--ask")
    f.add_argument("--contract")
    f.add_argument("--subject-kind", required=True, choices=evaluate.KINDS)
    f.add_argument("--subject-ref", required=True)
    f.add_argument("--definition", required=True, help="inline JSON or @file")
    rn = e.add_parser("run")
    rn.add_argument("--eval", required=True)
    rn.add_argument("--definition-sha256")
    rn.add_argument("--observation", action="append", help="inline JSON or @file")

    se = sub.add_parser("seal").add_subparsers(dest="sub", required=True)
    sc = se.add_parser("create")
    sc.add_argument("--eval", required=True)
    sc.add_argument("--disposition", required=True, choices=seal.DISPOSITIONS)
    sc.add_argument("--acknowledge", action="append")
    ck = se.add_parser("check")
    ck.add_argument("--seal", required=True)

    sub.add_parser("ledger").add_subparsers(dest="sub", required=True).add_parser("verify")

    dl = sub.add_parser("deltas").add_subparsers(dest="sub", required=True)
    ls = dl.add_parser("list")
    ls.add_argument("--host")
    ls.add_argument("--capability")
    ls.add_argument("--effective", action="store_true", help="merged practice deltas with the layer each came from")
    ls.add_argument("--domain", default=deltas.DEFAULT_DOMAIN)
    rd = dl.add_parser("render")
    rd.add_argument("--host", required=True)
    rd.add_argument("--host-version", default="")
    rd.add_argument("--capability", required=True)
    rd.add_argument("--classification", required=True)
    rd.add_argument("--statuses", default="qualified", help="comma list, e.g. qualified,candidate (evaluation runs)")

    ss = sub.add_parser("sessions").add_subparsers(dest="sub", required=True)
    cap = ss.add_parser("capture")
    cap.add_argument("--host", required=True)
    cap.add_argument("--host-version", default=None, help="e.g. the output of `claude --version`, supplied by the hook")
    pr = ss.add_parser("prune")
    pr.add_argument("--older-than", required=True, help="e.g. 7d or 36h")

    ex = sub.add_parser("export")
    ex.add_argument("--ask", required=True)
    ex.add_argument("--out", required=True, type=Path)
    return p


def _session_of(rec):
    return rec.get("session_id")


def _dispatch(ns, ws) -> tuple[int, object]:
    actor = _actor(ns.actor, ns.authority)
    if ns.cmd == "init":
        ws.ensure()
        return 0, {"rf_dir": str(ws.rf_dir), **ws.describe()}
    if ns.cmd == "profile":
        prof = profiles.for_host({"name": ns.host, "version": ns.host_version})
        name = prof["profile_id"].split("@")[0] if prof["host"] else "unknown"
        return 0, {**prof, "sha256": profiles.sha256(name)}
    if ns.cmd == "ask":
        if ns.sub == "compile":
            return 0, ask.compile(ws, staged=ns.staged, title=ns.title, capability=ns.capability, classification=_json_arg(ns.classification),
                                  route=_json_arg(ns.route), host=_json_arg(ns.host), links=_links(ns.link), limitations=ns.limitation or [], actor=actor)
        if ns.sub == "confirm":
            return 0, ask.confirm(ws, ns.ask, actor=actor)
        if ns.sub == "cancel":
            return 0, ask.cancel(ws, ns.ask, reason=ns.reason, actor=actor, attributed=ns.attributed)
        if ns.sub == "submitted":
            return 0, ask.submitted(ws, ns.ask, as_modified=ns.as_modified, actor=actor)
        if ns.sub == "copy":
            return 0, ask.prompt_text(ws, ns.ask)
        if ns.sub == "delivery":
            if ns.from_hook:
                try:
                    rec = ask.delivery_from_hook(ws, json.load(sys.stdin))
                except Exception as exc:  # a hook must never fail the host turn
                    return 0, {"recorded": False, "error": str(exc)}
                return 0, {"recorded": rec is not None, **(rec or {})}
            if not ns.ask:
                build_parser().error("--ask is required unless --from-hook")
            if ns.handoff:
                text, rec = ask.delivery_handoff(ws, ns.ask)
                return 0, rec if ns.json else text
            if not ns.state:
                build_parser().error("--handoff or --state is required")
            return 0, ask.delivery_state(ws, ns.ask, ns.state, ns.reason)
        if ns.sub == "show":
            return 0, ask.show(ws, ask_id=ns.ask, session=ns.session)
        return 0, ask.resolve(ws, session=ns.session, kind=ns.kind)
    if ns.cmd == "deltas":
        if ns.sub == "list":
            if ns.effective:
                return 0, deltas.effective(ws, ns.domain)
            hosts = [ns.host] if ns.host else deltas.host_catalog_names()
            entries = [e for h in hosts for e in deltas.load_host_catalog(h)["entries"] if not ns.capability or e["capability"] == ns.capability]
            return 0, {"host": entries, "practice": deltas.load_practice_catalog(ns.domain)["entries"]}
        prof = profiles.for_host({"name": ns.host, "version": ns.host_version})
        rendered = deltas.render(ws, prof, ns.capability, _json_arg(ns.classification), statuses=tuple(ns.statuses.split(",")))
        return 0, rendered if ns.json else rendered["text"]
    if ns.cmd == "eval":
        if ns.sub == "freeze":
            contract = _json_arg(ns.contract) if ns.contract else None
            return 0, evaluate.freeze(ws, subject_kind=ns.subject_kind, subject_ref=ns.subject_ref, definition=_json_arg(ns.definition), ask_id=ns.ask, contract=contract)
        return 0, evaluate.run(ws, ns.eval, observations=[_json_arg(o) for o in ns.observation or []], definition_sha256=ns.definition_sha256)
    if ns.cmd == "seal":
        if ns.sub == "create":
            return 0, seal.create(ws, ns.eval, ns.disposition, acknowledge=ns.acknowledge, actor=actor)
        result = seal.check(ws, ns.seal)
        return (0 if result["fresh"] else 2), result
    if ns.cmd == "ledger":
        findings = store.verify(ws)
        return (0 if not findings else 2), {"findings": findings, "clean": not findings}
    if ns.cmd == "sessions":
        if ns.sub == "capture":
            rec = sessions.capture(ws, ns.host, json.load(sys.stdin), host_version=ns.host_version)
            submission = None
            if rec and "prompt" not in rec:
                try:
                    submission = ask.submission_from_capture(ws, ns.host, _session_of(rec), rec["sha256"])
                except Exception:  # a hook must never fail the host turn
                    submission = None
            return 0, {"captured": rec is not None, **(rec or {}), "submission": submission}
        return 0, {"removed": sessions.prune(ws, ns.older_than)}
    if ns.cmd == "export":
        return 0, _export(ws, ns.ask, ns.out)
    raise AssertionError(ns.cmd)


def _export(ws, ask_id, out: Path) -> dict:
    lines = [store.canonical(e) + b"\n" for e in store.events(ws) if e["id"] == ask_id]
    if not lines:
        raise LedgerError("ask.not_found", ask_id)
    files = 0
    with tarfile.open(out, "w") as tar:
        for p in sorted((ws.rf_dir / "asks" / ask_id).iterdir()):
            tar.add(p, arcname=f"{ask_id}/{p.name}")
            files += 1
        data = b"".join(lines)
        info = tarfile.TarInfo(f"{ask_id}/ledger.jsonl")
        info.size = len(data)
        import io
        tar.addfile(info, io.BytesIO(data))
        files += 1
    return {"ask_id": ask_id, "out": str(out), "files": files}


def main(argv=None) -> int:
    parser = build_parser()
    ns = parser.parse_args(_hoist_globals(list(sys.argv[1:] if argv is None else argv)))
    ws = workspace.resolve(explicit=ns.workspace)
    try:
        code, result = _dispatch(ns, ws)
    except (json.JSONDecodeError, ValueError, FileNotFoundError) as exc:
        _emit({"error": "usage", "detail": str(exc)}, ns.json)
        return 1
    except NeedsInput as exc:
        _emit({"needs_input": exc.reason, "candidates": exc.candidates}, ns.json)
        return 3
    except Refused as exc:
        _emit({"error": "seal.refused", "refusal_codes": exc.codes}, ns.json)
        return 2
    except LedgerError as exc:
        _emit({"error": exc.code, "detail": exc.detail}, ns.json)
        return 2
    except config.ConfigError as exc:
        _emit({"error": "config", "detail": str(exc)}, ns.json)
        return 2
    except Exception as exc:  # pragma: no cover - internal
        print(f"ringframe: internal error: {exc!r}", file=sys.stderr)
        return 4
    if ns.cmd == "ask" and getattr(ns, "sub", None) == "copy":
        sys.stdout.write(str(result))
        return code
    _emit(result, ns.json)
    return code
