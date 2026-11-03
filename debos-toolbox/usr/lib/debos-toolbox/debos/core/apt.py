"""Read-only package queries. Everything here works without root."""

import glob
import os
import re

from .util import run

NOLOCK = ["-o", "Debug::NoLocking=1"]


def installed():
    """{package: version} for packages in state 'ii' (architecture suffix removed)."""
    code, text = run(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\t${Version}\n"], timeout=30)
    result = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].startswith("ii"):
            result[parts[0]] = parts[2]
    return result


def installed_sizes(packages):
    """{package: installed size in bytes}."""
    pkgs = [p for p in packages if p]
    if not pkgs:
        return {}
    code, text = run(["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\n"] + pkgs, timeout=30)
    sizes = {}
    for line in text.splitlines():
        name, _, size = line.partition("\t")
        if size.strip().isdigit():
            sizes[name] = int(size) * 1024
    return sizes


def candidates(packages):
    """{package: candidate version or None} using `apt-cache policy` (batched)."""
    result = {}
    pkgs = sorted({p for p in packages if p})
    for i in range(0, len(pkgs), 150):
        chunk = pkgs[i:i + 150]
        code, text = run(["apt-cache", "policy"] + chunk, timeout=60)
        current = None
        for line in text.splitlines():
            if line and not line.startswith(" ") and line.endswith(":"):
                current = line[:-1].split(":")[0]
                result.setdefault(current, None)
            elif current and line.strip().startswith("Candidate:"):
                cand = line.split(":", 1)[1].strip()
                result[current] = None if cand in ("(none)", "") else cand
    for p in pkgs:
        result.setdefault(p, None)
    return result


_INST = re.compile(r"^Inst (\S+) (?:\[(\S+)\] )?\((\S+) (.*?)\)")


def simulate_upgrade(full=True):
    """List of dicts {name, old, new, origin, security} that an upgrade would install."""
    action = "dist-upgrade" if full else "upgrade"
    code, text = run(["apt-get", "-s"] + NOLOCK + [action], timeout=120)
    items = []
    for line in text.splitlines():
        m = _INST.match(line)
        if m:
            name, old, new, origin = m.groups()
            items.append({"name": name, "old": old or "", "new": new, "origin": origin,
                          "security": "security" in origin.lower()})
    return items, code == 0


def autoremovable():
    code, text = run(["apt-get", "-s"] + NOLOCK + ["autoremove", "--purge"], timeout=60)
    return [m.group(1) for m in (re.match(r"^(?:Purg|Remv) (\S+)", l) for l in text.splitlines()) if m]


def residual_configs():
    code, text = run(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\n"], timeout=30)
    return [l.split("\t")[0] for l in text.splitlines() if "\t" in l and l.split("\t")[1].startswith("rc")]


def held():
    return run(["apt-mark", "showhold"], timeout=20)[1].split()


def broken():
    """Output of `dpkg --audit` (empty when everything is fine)."""
    return run(["dpkg", "--audit"], timeout=30)[1].strip()


def local_packages():
    """Installed packages that no configured repository provides (obsolete or manually installed)."""
    code, text = run(["apt", "list", "--installed"], timeout=60)
    return [l.split("/", 1)[0] for l in text.splitlines() if ",local]" in l or "[installed,local]" in l]


def lists_age():
    """Seconds since the package lists were last refreshed (None if never)."""
    import time
    files = glob.glob("/var/lib/apt/lists/*_Release") + glob.glob("/var/lib/apt/lists/*_InRelease")
    if not files:
        return None
    newest = max(os.path.getmtime(f) for f in files)
    return max(0, time.time() - newest)


def search(query, limit=80):
    if not query or len(query) < 2:
        return []
    code, text = run(["apt-cache", "search", "--names-only", "--", query], timeout=30)
    res = []
    for line in text.splitlines():
        name, _, desc = line.partition(" - ")
        if name:
            res.append((name.strip(), desc.strip()))
    res.sort(key=lambda r: (not r[0].startswith(query.lower()), len(r[0]), r[0]))
    return res[:limit]


def show(pkg):
    code, text = run(["apt-cache", "show", "--no-all-versions", pkg], timeout=20)
    fields, key = {}, None
    for line in text.splitlines():
        if line.startswith(" ") and key:
            fields[key] += "\n" + line.strip()
        elif ":" in line:
            key, val = line.split(":", 1)
            fields[key] = val.strip()
    return fields


def foreign_architectures():
    return run(["dpkg", "--print-foreign-architectures"], timeout=10)[1].split()


def apt_cache_size():
    total = 0
    for f in glob.glob("/var/cache/apt/archives/*.deb") + glob.glob("/var/cache/apt/archives/partial/*"):
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
    return total
