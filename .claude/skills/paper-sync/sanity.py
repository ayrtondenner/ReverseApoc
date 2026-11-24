"""Paper-sync lint of a mirror (argv[1]), per .tex file: braces, environments, stray & _ ^ #,
dashes and non-ASCII."""

import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
files = sorted((root / "sections").glob("*.tex")) + [root / "main.tex"]
TABLE_ENVS = {"tabular", "tabularx", "tabular*", "array", "align", "longtable"}


def code_part(line):
    # return (code, comment_start_index or None)
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            return line[:i], i
        i += 1
    return line, None


for f in files:
    lines = f.read_text(encoding="utf-8").splitlines()
    depth = 0
    stack = []
    issues = []
    for n, line in enumerate(lines, 1):
        code, ci = code_part(line)
        if ci is not None and code.strip():
            issues.append((n, "inline %", line.strip()[:120]))
        # braces
        j = 0
        while j < len(code):
            c = code[j]
            if c == "\\":
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth < 0:
                    issues.append((n, "brace below zero", code.strip()[:120]))
                    depth = 0
            j += 1
        for m in re.finditer(r"\\(begin|end)\{([^}]*)\}", code):
            kind, env = m.groups()
            if kind == "begin":
                stack.append((env, n))
            else:
                if not stack or stack[-1][0] != env:
                    open_env = stack[-1] if stack else None
                    issues.append((n, f"end{{{env}}} mismatched, open={open_env}", ""))
                else:
                    stack.pop()
        in_table = any(e in TABLE_ENVS for e, _ in stack)
        stripped = re.sub(r"\\&", "", code)
        if "&" in stripped and not in_table and not re.search(r"\\begin\{(tabular|tabularx)", code):
            issues.append((n, "& outside table", code.strip()[:120]))
        if "--" in code:
            issues.append((n, "--", code.strip()[:140]))
        if "\u2014" in code or "\u2013" in code:
            issues.append((n, "unicode dash", code.strip()[:120]))
        if "---" in code:
            issues.append((n, "em dash ---", code.strip()[:120]))
        if any(ord(ch) > 127 for ch in code):
            issues.append((n, "non-ascii", "".join(sorted({ch for ch in code if ord(ch) > 127}))))
        # unescaped _ ^ # outside math, url, label/ref/cite args
        code = code.replace("\\$", "")
        t = re.sub(r"\\(url|label|ref|cite[pt]?|input|bibliography\w*)\{[^}]*\}", "", code)
        t = re.sub(r"\$[^$]*\$", "", t)
        t = re.sub(r"\\\[.*?\\\]", "", t)
        for ch in "_^#":
            if re.search(r"(?<!\\)" + re.escape(ch), t):
                issues.append((n, f"raw {ch}", code.strip()[:120]))
        if t.count("$") % 2:
            issues.append((n, "odd $", code.strip()[:120]))
    if depth != 0:
        issues.append(("EOF", f"brace depth {depth}", ""))
    if stack:
        issues.append(("EOF", f"unclosed envs {stack}", ""))
    print(f"== {f.name}: {len(issues)} issue(s)")
    for i in issues:
        print("  ", *i)
