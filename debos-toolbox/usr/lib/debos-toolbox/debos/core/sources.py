"""APT sources parsing, analysis and editing (one-line .list and deb822 .sources).

The parser is deliberately tolerant: it never raises on malformed input and
keeps enough position information to edit files in place without touching
lines it does not understand.  It is shared by the GUI (read-only analysis)
and by the root helper (fixes).
"""

import glob
import os
import re

SOURCES_LIST = "/etc/apt/sources.list"
SOURCES_DIR = "/etc/apt/sources.list.d"
LEGACY_KEYRING = "/etc/apt/trusted.gpg"
KEYRING_DIRS = ("/etc/apt/keyrings", "/etc/apt/trusted.gpg.d", "/usr/share/keyrings", "/var/lib/extrepo/keys")
# trixie and later ship .pgp keyrings (the .gpg names are kept for compatibility)
DEBIAN_KEYRING = next((k for k in ("/usr/share/keyrings/debian-archive-keyring.pgp",
                                   "/usr/share/keyrings/debian-archive-keyring.gpg") if os.path.exists(k)),
                      "/usr/share/keyrings/debian-archive-keyring.gpg")
DEBIAN_MIRROR = "http://deb.debian.org/debian"
DEBIAN_SECURITY = "http://security.debian.org/debian-security"
DEBIAN_SUITES = {"oldoldstable", "oldstable", "stable", "testing", "unstable", "sid", "experimental",
                 "bullseye", "bookworm", "trixie", "forky", "duke", "rc-buggy"}
SUITE_SUFFIXES = ("-updates", "-security", "-backports-sloppy", "-backports", "-proposed-updates", "-fasttrack",
                  "-backports-staging")
DISABLED_MARK = "# disabled by Debos: "


class Entry:
    """One repository definition: a .list line or one deb822 stanza."""

    __slots__ = ("file", "fmt", "index", "types", "uris", "suites", "components", "options",
                 "enabled", "raw", "start", "end")

    def __init__(self, file, fmt, index, types, uris, suites, components, options, enabled, raw, start, end):
        self.file, self.fmt, self.index = file, fmt, index
        self.types, self.uris, self.suites, self.components = types, uris, suites, components
        self.options, self.enabled, self.raw = options, enabled, raw
        self.start, self.end = start, end   # line range [start, end) inside the file

    @property
    def signed_by(self):
        return self.options.get("signed-by", "").strip()

    @property
    def uri(self):
        return self.uris[0] if self.uris else ""

    @property
    def host(self):
        m = re.match(r"^[a-z0-9+.-]+://(?:[^@/]*@)?([^/:]+)", self.uri, re.I)
        return m.group(1).lower() if m else ""

    def keys(self):
        """(type, normalized uri, suite) tuples this entry defines."""
        for t in self.types:
            for u in self.uris:
                for s in self.suites:
                    yield (t, normalize_uri(u), s.rstrip("/") if s != "/" else s)

    def is_official_debian(self):
        if "debian-archive-keyring" in self.signed_by:
            return True
        for u in self.uris:
            h = re.sub(r"^[a-z0-9+.-]+://", "", u.lower())
            host = h.split("/", 1)[0]
            if host.endswith("debian.org") and not host.startswith(("fasttrack.", "extrepo")) and "/debian" in "/" + h.split("/", 1)[-1]:
                return True
        # local mirrors such as http://mirror.example/debian with Debian suites and "main";
        # vendors that copy that layout (repo.jellyfin.org/debian ...) bring their own Signed-By
        if self.signed_by:
            return False
        base = {suite_base(s) for s in self.suites}
        return bool(base & DEBIAN_SUITES) and "main" in self.components and any(
            re.search(r"/debian(-security)?/?$", u) for u in self.uris)

    def is_cdrom(self):
        return any(u.lower().startswith("cdrom:") for u in self.uris)

    def label(self):
        return f"{os.path.basename(self.file)}: {' '.join(self.types)} {self.uri} {' '.join(self.suites)} {' '.join(self.components)}".strip()

    def __repr__(self):
        return f"<Entry {self.label()} enabled={self.enabled}>"


def normalize_uri(uri):
    uri = uri.strip()
    uri = re.sub(r"^(https?)://", lambda m: m.group(1).lower() + "://", uri, flags=re.I)
    return uri.rstrip("/")


def suite_base(suite):
    for suf in SUITE_SUFFIXES:
        if suite.endswith(suf):
            return suite[: -len(suf)]
    return suite


def source_files():
    files = []
    if os.path.isfile(SOURCES_LIST):
        files.append(SOURCES_LIST)
    files += sorted(glob.glob(os.path.join(SOURCES_DIR, "*.list")))
    files += sorted(glob.glob(os.path.join(SOURCES_DIR, "*.sources")))
    return files


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


_LIST_RE = re.compile(r"^\s*(deb|deb-src)\s+(?:\[([^\]]*)\]\s+)?(\S+)\s+(\S+)\s*(.*?)\s*$")


def parse_list_file(path, text=None):
    text = _read(path) if text is None else text
    entries = []
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        enabled = True
        body = stripped
        if stripped.startswith("#"):
            enabled = False
            body = stripped.lstrip("#").strip()
            if body.startswith(DISABLED_MARK.lstrip("# ").strip()):
                body = body[len(DISABLED_MARK.lstrip("# ").strip()):].strip()
        m = _LIST_RE.match(body)
        if not m:
            continue
        typ, opts, uri, suite, comps = m.groups()
        comps = comps.split("#", 1)[0]  # trailing comment
        options = {}
        for opt in (opts or "").split():
            if "=" in opt:
                k, v = opt.split("=", 1)
                options[k.strip().lower()] = v.strip()
        entries.append(Entry(path, "list", i, [typ], [uri], [suite], comps.split(), options, enabled, line, i, i + 1))
    return entries


def parse_deb822_file(path, text=None):
    text = _read(path) if text is None else text
    lines = text.splitlines()
    entries, stanza, start, index = [], [], None, 0

    def flush(end):
        nonlocal stanza, start, index
        if stanza:
            fields, key = {}, None
            for _ln, raw in stanza:
                if raw.startswith("#"):
                    continue
                if raw[:1] in (" ", "\t") and key:
                    fields[key] += "\n" + raw.strip()
                    continue
                if ":" in raw:
                    key, val = raw.split(":", 1)
                    key = key.strip().lower()
                    fields[key] = val.strip()
            if fields.get("types") or fields.get("uris"):
                options = {k: v for k, v in fields.items() if k not in ("types", "uris", "suites", "components", "enabled")}
                enabled = fields.get("enabled", "yes").strip().lower() not in ("no", "false", "0")
                raw_text = "\n".join(r for _l, r in stanza)
                entries.append(Entry(path, "deb822", index, fields.get("types", "").split(), fields.get("uris", "").split(),
                                     fields.get("suites", "").split(), fields.get("components", "").split(), options,
                                     enabled, raw_text, start, end))
                index += 1
        stanza, start = [], None

    for i, line in enumerate(lines):
        if not line.strip():
            flush(i)
            continue
        if start is None:
            if line.lstrip().startswith("#"):
                continue  # comment lines between stanzas
            start = i
        stanza.append((i, line))
    flush(len(lines))
    return entries


def parse_file(path, text=None):
    if path.endswith(".sources"):
        return parse_deb822_file(path, text)
    return parse_list_file(path, text)


def parse_all(files=None):
    entries = []
    for path in files if files is not None else source_files():
        entries += parse_file(path)
    return entries


# ---------------------------------------------------------------------------
# Keyrings
# ---------------------------------------------------------------------------
def keyring_files():
    found = []
    for d in KEYRING_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*"))):
            if os.path.isfile(path) and path.endswith((".gpg", ".asc", ".pgp", ".key")):
                found.append(path)
    if os.path.isfile(LEGACY_KEYRING) and os.path.getsize(LEGACY_KEYRING) > 0:
        found.append(LEGACY_KEYRING)
    return found


def parse_gpg_colons(text):
    """Parse `gpg --with-colons` output into a list of key dicts."""
    keys, cur = [], None
    for line in text.splitlines():
        f = line.split(":")
        if f[0] == "pub":
            cur = {"keyid": f[4] if len(f) > 4 else "", "created": f[5] if len(f) > 5 else "",
                   "expires": f[6] if len(f) > 6 else "", "validity": f[1] if len(f) > 1 else "",
                   "fingerprint": "", "uid": "", "subkeys": []}
            keys.append(cur)
        elif f[0] == "fpr" and cur is not None and not cur["fingerprint"]:
            cur["fingerprint"] = f[9] if len(f) > 9 else ""
        elif f[0] == "uid" and cur is not None and not cur["uid"]:
            cur["uid"] = f[9] if len(f) > 9 else ""
        elif f[0] == "sub" and cur is not None:
            cur["subkeys"].append({"keyid": f[4] if len(f) > 4 else "", "expires": f[6] if len(f) > 6 else "",
                                   "validity": f[1] if len(f) > 1 else ""})
    return keys


def entry_issues(entries, debian_codename=None, branch=None, existing=os.path.exists):
    """Static analysis of parsed entries.  Returns a list of issue dicts:
    {id, severity, title, detail, entries: [Entry], fix}
    fix is a machine readable action understood by the root helper.
    """
    issues = []
    active = [e for e in entries if e.enabled]

    for e in active:
        if e.is_cdrom():
            issues.append({"id": "cdrom", "severity": "error", "title": "Installation DVD/CD repository is enabled",
                           "detail": "apt update fails when the installation medium is not inserted.",
                           "entries": [e], "fix": "disable"})

    # duplicates and conflicting Signed-By
    seen = {}
    for e in active:
        for key in e.keys():
            seen.setdefault(key, []).append(e)
    reported = set()
    for key, group in seen.items():
        uniq = []
        for e in group:
            if all(e is not u for u in uniq):
                uniq.append(e)
        if len(uniq) < 2:
            continue
        ident = tuple(sorted((u.file, u.index) for u in uniq))
        if ident in reported:
            continue
        reported.add(ident)
        signed = {u.signed_by for u in uniq}
        if len(signed) > 1:
            issues.append({"id": "conflict-signed-by", "severity": "error",
                           "title": f"Conflicting Signed-By for {key[1]} {key[2]}",
                           "detail": "The same repository is defined more than once with different keys. "
                                     "apt refuses to update until only one definition is left.",
                           "entries": uniq, "fix": "dedupe"})
        else:
            issues.append({"id": "duplicate", "severity": "warning", "title": f"Duplicate repository {key[1]} {key[2]}",
                           "detail": "Defined in: " + ", ".join(sorted({os.path.basename(u.file) for u in uniq})),
                           "entries": uniq, "fix": "dedupe"})

    for e in active:
        sb = e.signed_by
        if sb and sb.startswith("/") and "\n" not in sb and not existing(sb):
            issues.append({"id": "missing-key", "severity": "error", "title": f"Key file missing for {e.host or e.uri}",
                           "detail": f"{sb} does not exist, so this repository cannot be verified.",
                           "entries": [e], "fix": "fetch-key"})

    if debian_codename and branch in ("oldoldstable", "oldstable", "stable", "testing", "sid"):
        official = [e for e in active if e.is_official_debian() and not e.is_cdrom()]
        bases = {suite_base(s) for e in official for s in e.suites}
        expected = {"sid": {"sid", "unstable", "experimental", "rc-buggy"},
                    "testing": {"testing", debian_codename},
                    "stable": {"stable", debian_codename},
                    "oldstable": {"oldstable", debian_codename},
                    "oldoldstable": {"oldoldstable", debian_codename}}[branch]
        foreign = sorted(b for b in bases if b not in expected and b in DEBIAN_SUITES)
        if foreign:
            issues.append({"id": "mixed-suites", "severity": "warning",
                           "title": "Debian repositories from different releases are mixed",
                           "detail": f"This system is {branch} ({debian_codename}) but also uses: {', '.join(foreign)}. "
                                     "Mixing releases (\"FrankenDebian\") can break upgrades.",
                           "entries": [e for e in official if any(suite_base(s) in foreign for s in e.suites)],
                           "fix": "review"})
        comps = {c for e in official for c in e.components}
        if official and "non-free" in comps and "non-free-firmware" not in comps and debian_codename not in ("bullseye",):
            issues.append({"id": "nonfree-firmware", "severity": "info",
                           "title": "non-free-firmware component is not enabled",
                           "detail": "Since Debian 12 firmware lives in non-free-firmware. Wi-Fi, GPU and CPU microcode updates need it.",
                           "entries": official, "fix": "components"})
        if not official:
            issues.append({"id": "no-official", "severity": "error", "title": "No official Debian repository is enabled",
                           "detail": "Security updates and most software come from the official Debian archive.",
                           "entries": [], "fix": "official"})

    for e in active:
        if e.options.get("trusted", "").lower() == "yes":
            issues.append({"id": "trusted-yes", "severity": "warning", "title": f"Unsigned repository allowed: {e.host}",
                           "detail": "trusted=yes disables signature checks for this repository.",
                           "entries": [e], "fix": "review"})
    return issues


# ---------------------------------------------------------------------------
# Editing (used by the root helper; functions return new file text)
# ---------------------------------------------------------------------------
def disable_in_text(text, entry):
    lines = text.splitlines()
    if entry.fmt == "list":
        if entry.start < len(lines) and not lines[entry.start].lstrip().startswith("#"):
            lines[entry.start] = DISABLED_MARK + lines[entry.start]
    else:
        lines = _set_field(lines, entry, "Enabled", "no")
    return "\n".join(lines) + "\n"


def enable_in_text(text, entry):
    lines = text.splitlines()
    if entry.fmt == "list":
        line = lines[entry.start]
        if line.startswith(DISABLED_MARK):
            lines[entry.start] = line[len(DISABLED_MARK):]
        else:
            lines[entry.start] = re.sub(r"^\s*#+\s*", "", line)
    else:
        lines = _set_field(lines, entry, "Enabled", "yes")
    return "\n".join(lines) + "\n"


def remove_from_text(text, entry):
    lines = text.splitlines()
    del lines[entry.start:entry.end]
    # collapse double blank lines left behind in deb822 files
    out = []
    for line in lines:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def set_signed_by_in_text(text, entry, keyfile):
    """Point the entry at keyfile; an empty keyfile removes the Signed-By option."""
    lines = text.splitlines()
    if entry.fmt == "deb822":
        if keyfile:
            lines = _set_field(lines, entry, "Signed-By", keyfile)
        else:
            lines = _del_field(lines, entry, "Signed-By")
        return "\n".join(lines) + "\n"
    line = lines[entry.start]
    m = re.match(r"^(\s*(?:#\s*)?(?:deb|deb-src))\s+(?:\[([^\]]*)\]\s+)?(.*)$", line)
    if not m:
        return text
    prefix, opts, rest = m.groups()
    parts = [o for o in (opts or "").split() if not o.lower().startswith("signed-by=")]
    if keyfile:
        parts.append(f"signed-by={keyfile}")
    lines[entry.start] = f"{prefix} [{' '.join(parts)}] {rest}" if parts else f"{prefix} {rest}"
    return "\n".join(lines) + "\n"


_LIST_HEAD_RE = re.compile(r"^(\s*(?:#\s*)?(?:deb|deb-src)\s+(?:\[[^\]]*\]\s+)?\S+\s+\S+)([^#]*)(#.*)?$")


def set_components_in_text(text, entry, components):
    lines = text.splitlines()
    if entry.fmt == "deb822":
        lines = _set_field(lines, entry, "Components", " ".join(components))
    else:
        m = _LIST_HEAD_RE.match(lines[entry.start])
        if not m:
            return text
        tail = f" {m.group(3)}" if m.group(3) else ""
        lines[entry.start] = f"{m.group(1)} {' '.join(components)}{tail}".rstrip()
    return "\n".join(lines) + "\n"


def _set_field(lines, entry, field, value):
    """Set or add a deb822 field inside the entry's stanza (case-insensitive)."""
    start, end = entry.start, entry.end
    i = start
    while i < end:
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key = line.split(":", 1)[0].strip()
            if key.lower() == field.lower():
                j = i + 1
                while j < end and lines[j][:1] in (" ", "\t"):
                    j += 1
                lines[i:j] = [f"{field}: {value}"]
                return lines
        i += 1
    lines.insert(end, f"{field}: {value}")
    return lines


def _del_field(lines, entry, field):
    """Remove a deb822 field (and its continuation lines) from the entry's stanza."""
    i = entry.start
    while i < min(entry.end, len(lines)):
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t", "#")) and line.split(":", 1)[0].strip().lower() == field.lower():
            j = i + 1
            while j < entry.end and lines[j][:1] in (" ", "\t"):
                j += 1
            del lines[i:j]
            return lines
        i += 1
    return lines


def render_deb822(types, uris, suites, components, signed_by=None, extra=None, comment=None):
    out = []
    if comment:
        out += [f"# {line}" for line in comment.splitlines()]
    out += [f"Types: {' '.join(types)}", f"URIs: {' '.join(uris)}", f"Suites: {' '.join(suites)}",
            f"Components: {' '.join(components)}"]
    if signed_by:
        out.append(f"Signed-By: {signed_by}")
    for k, v in (extra or {}).items():
        out.append(f"{k}: {v}")
    return "\n".join(out) + "\n"


def official_sources_text(branch, stable_codename, testing_codename, *, use_alias=False, components=None,
                          deb_src=False, backports=False, mirror=DEBIAN_MIRROR, security=DEBIAN_SECURITY,
                          app_label="Debos - Toolbox"):
    """Generate a complete debian.sources for stable/testing/sid (and oldstable)."""
    components = components or ["main", "contrib", "non-free", "non-free-firmware"]
    types = ["deb", "deb-src"] if deb_src else ["deb"]
    if branch == "sid":
        stanzas = [render_deb822(types, [mirror], ["sid"], components, DEBIAN_KEYRING,
                                 comment=f"Debian unstable (sid) - generated by {app_label}")]
        return "\n".join(stanzas)
    if branch == "testing":
        name = "testing" if use_alias else testing_codename
    elif branch == "oldstable":
        name = "oldstable" if use_alias else stable_codename
    else:
        name = "stable" if use_alias else stable_codename
    suites = [name, f"{name}-updates"]
    if backports and branch in ("stable", "oldstable"):
        suites.append(f"{name}-backports")
    label = {"testing": "testing", "oldstable": "oldstable"}.get(branch, "stable")
    stanzas = [
        render_deb822(types, [mirror], suites, components, DEBIAN_KEYRING,
                      comment=f"Debian {label} ({name}) - generated by {app_label}"),
        render_deb822(types, [security], [f"{name}-security"], components, DEBIAN_KEYRING),
    ]
    return "\n".join(stanzas)
