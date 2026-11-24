"""Paper-sync lint of a mirror (argv[1]): labels, refs, cites and non-ASCII across sections."""

import collections
import pathlib
import re
import sys

CITE = (
    r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|nocite)\*?"
    r"(?:\[[^\]]*\])*\{([^}]*)\}"
)

root = pathlib.Path(sys.argv[1])
files = sorted((root / "sections").glob("*.tex"))
main = root / "main.tex"


def strip_comments(t):
    return re.sub(r"(?<!\\)%.*", "", t)


envs = collections.Counter()
macros = collections.Counter()
labels = {}
refs = collections.defaultdict(list)
cites = collections.defaultdict(list)
nonascii = collections.defaultdict(collections.Counter)
for f in files:
    raw = f.read_text(encoding="utf-8")
    t = strip_comments(raw)
    for m in re.finditer(r"\\begin\{([^}]*)\}", t):
        envs[m.group(1)] += 1
    for m in re.finditer(r"\\([a-zA-Z@]+)", t):
        macros[m.group(1)] += 1
    for m in re.finditer(r"\\label\{([^}]*)\}", t):
        labels.setdefault(m.group(1), []).append(f.name)
    for m in re.finditer(r"\\(?:ref|cref|Cref|autoref|pageref|eqref|nameref)\{([^}]*)\}", t):
        for k in m.group(1).split(","):
            refs[k.strip()].append(f.name)
    for m in re.finditer(CITE, t):
        for k in m.group(1).split(","):
            cites[k.strip()].append(f.name)
    for line in t.splitlines():
        for ch in line:
            if ord(ch) > 127:
                nonascii[f.name][f"U+{ord(ch):04X} {ch}"] += 1

print("ENVS", dict(envs))
print("MACROS", sorted(macros.items(), key=lambda x: -x[1]))
print("LABELS", len(labels))
for k, v in sorted(labels.items()):
    print("  L", k, v)
dup = {k: v for k, v in labels.items() if len(v) > 1}
print("DUP LABELS", dup)
print("REFS")
for k, v in sorted(refs.items()):
    print("  R", k, sorted(set(v)), "" if k in labels else "  <<< UNDEFINED")
bib = (root / "reverseapoc.bib").read_text(encoding="utf-8")
keys = re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib)
kc = collections.Counter(keys)
print("BIB keys", len(keys), "dups", [k for k, c in kc.items() if c > 1])
print("CITES", len(cites))
for k, v in sorted(cites.items()):
    if k not in kc:
        print("  UNDEFINED CITE", k, sorted(set(v)))
print("NONASCII")
for f, c in nonascii.items():
    print("  ", f, dict(c))
