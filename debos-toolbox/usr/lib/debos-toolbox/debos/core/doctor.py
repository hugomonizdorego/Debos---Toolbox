"""Repository Doctor and other root-side repairs.

Everything in here is called by the debos-helper entry point, which runs as
root inside a task script.  Functions print what they do (that output is
what the user sees in the console) and return True/False.
"""

import glob
import os
import re
import shutil
import subprocess
import tempfile
import time

from . import sources as S

BACKUP_ROOT = "/var/backups/debos-toolbox"
KEYRING_DIR = "/etc/apt/keyrings"
TRUSTED_DIR = "/etc/apt/trusted.gpg.d"
KEYSERVERS = ("hkps://keyserver.ubuntu.com", "hkps://keys.openpgp.org", "hkp://keyserver.ubuntu.com:80")

# Canonical key locations of well known vendors (used to repair missing/expired keys).
VENDOR_KEYS = {
    "download.docker.com": "https://download.docker.com/linux/debian/gpg",
    "packages.microsoft.com": "https://packages.microsoft.com/keys/microsoft.asc",
    "dl.google.com": "https://dl.google.com/linux/linux_signing_key.pub",
    "brave-browser-apt-release.s3.brave.com": "https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg",
    "packages.mozilla.org": "https://packages.mozilla.org/apt/repo-signing-key.gpg",
    "repo.vivaldi.com": "https://repo.vivaldi.com/archive/linux_signing_key.pub",
    "deb.opera.com": "https://deb.opera.com/archive.key",
    "download.vscodium.com": "https://gitlab.com/paulcarroty/vscodium-deb-rpm-repo/raw/master/pub.gpg",
    "dl.winehq.org": "https://dl.winehq.org/wine-builds/winehq.key",
    "deb.xanmod.org": "https://dl.xanmod.org/archive.key",
    "liquorix.net": "https://liquorix.net/liquorix-keyring.gpg",
    "download.virtualbox.org": "https://www.virtualbox.org/download/oracle_vbox_2016.asc",
    "ppa.floorp.app": "https://ppa.floorp.app/KEY.gpg",
    "download.onlyoffice.com": "https://download.onlyoffice.com/GPG-KEY-ONLYOFFICE",
    "updates.signal.org": "https://updates.signal.org/desktop/apt/keys.asc",
    "packages.element.io": "https://packages.element.io/debian/element-io-archive-keyring.gpg",
    "repo.jellyfin.org": "https://repo.jellyfin.org/jellyfin_team.gpg.key",
    "apt.syncthing.net": "https://syncthing.net/release-key.gpg",
}
KEYRING_PACKAGES = {   # host -> (package, keyring it installs)
    "deb.debian.org": ("debian-archive-keyring", S.DEBIAN_KEYRING),
    "security.debian.org": ("debian-archive-keyring", S.DEBIAN_KEYRING),
    "ftp.debian.org": ("debian-archive-keyring", S.DEBIAN_KEYRING),
    "fasttrack.debian.net": ("fasttrack-archive-keyring", "/usr/share/keyrings/fasttrack-archive-keyring.gpg"),
}


def say(msg=""):
    print(msg, flush=True)


def atomic_write(path, text, mode=0o644):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".debos-", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def backup(paths, tag):
    dest = os.path.join(BACKUP_ROOT, f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(dest, exist_ok=True)
    for p in paths:
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(dest, os.path.basename(p)))
    return dest


def edit_entry(entry, action, value=None):
    """Apply one edit to the file containing entry. action: disable|enable|remove|signed-by|components."""
    text = S._read(entry.file)
    if action == "disable":
        new = S.disable_in_text(text, entry)
    elif action == "enable":
        new = S.enable_in_text(text, entry)
    elif action == "remove":
        new = S.remove_from_text(text, entry)
    elif action == "signed-by":
        new = S.set_signed_by_in_text(text, entry, value)
    elif action == "components":
        new = S.set_components_in_text(text, entry, value)
    else:
        raise ValueError(action)
    if new != text:
        atomic_write(entry.file, new)
    return new != text


def reparse(entry):
    """Find the current version of entry (files change while we edit them)."""
    for e in S.parse_file(entry.file):
        if e.index == entry.index:
            return e
    return None


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
def enable_components(wanted):
    wanted = [c for c in wanted if re.match(r"^[a-z-]+$", c)]
    changed = 0
    for path in S.source_files():
        text = S._read(path)
        new_lines = text.splitlines()
        entries = [e for e in S.parse_file(path, text) if e.enabled and e.is_official_debian() and not e.is_cdrom()]
        if not entries:
            continue
        for e in sorted(entries, key=lambda x: -x.start):
            comps = list(e.components)
            for c in wanted:
                if c == "non-free-firmware" and any(s.startswith("bullseye") for s in e.suites):
                    continue  # does not exist before Debian 12
                if c not in comps:
                    comps.append(c)
            if comps == e.components:
                continue
            if e.fmt == "list":
                line = new_lines[e.start]
                m = re.match(r"^(\s*(?:deb|deb-src)\s+(?:\[[^\]]*\]\s+)?\S+\s+\S+)(.*)$", line)
                if m:
                    new_lines[e.start] = f"{m.group(1)} {' '.join(comps)}"
            else:
                new_lines = S._set_field(new_lines, e, "Components", " ".join(comps))
            changed += 1
        new_text = "\n".join(new_lines) + "\n"
        if new_text != text:
            atomic_write(path, new_text)
            say(f"  updated {path}")
    say(f"Components {' '.join(wanted)} enabled on {changed} official Debian entr{'y' if changed == 1 else 'ies'}.")
    return True


def set_component(component, enabled):
    """Add or remove one component on every official Debian entry."""
    if enabled:
        return enable_components([component])
    for path in S.source_files():
        text = S._read(path)
        lines = text.splitlines()
        entries = [e for e in S.parse_file(path, text) if e.enabled and e.is_official_debian()]
        for e in sorted(entries, key=lambda x: -x.start):
            comps = [c for c in e.components if c != component]
            if comps == e.components or not comps:
                continue
            if e.fmt == "list":
                m = re.match(r"^(\s*(?:deb|deb-src)\s+(?:\[[^\]]*\]\s+)?\S+\s+\S+)(.*)$", lines[e.start])
                if m:
                    lines[e.start] = f"{m.group(1)} {' '.join(comps)}"
            else:
                lines = S._set_field(lines, e, "Components", " ".join(comps))
        new = "\n".join(lines) + "\n"
        if new != text:
            atomic_write(path, new)
            say(f"  updated {path}")
    say(f"Component {component} disabled.")
    return True


# ---------------------------------------------------------------------------
# Official Debian sources
# ---------------------------------------------------------------------------
def write_official(text, keep_files=()):
    """Write /etc/apt/sources.list.d/debian.sources and disable official Debian
    entries everywhere else.  Third-party repositories are never touched."""
    target = os.path.join(S.SOURCES_DIR, "debian.sources")
    backup(S.source_files(), "sources")
    for path in S.source_files():
        if path == target or path in keep_files:
            continue
        for e in sorted(S.parse_file(path), key=lambda x: -x.start):
            if e.enabled and e.is_official_debian():
                edit_entry(e, "disable")
                say(f"  disabled old entry: {e.label()}")
    atomic_write(target, text)
    say(f"Wrote {target}")
    return True


def set_extra_repo(name, enabled, text=None):
    path = os.path.join(S.SOURCES_DIR, f"{name}.sources")
    if enabled:
        atomic_write(path, text)
        say(f"Wrote {path}")
    elif os.path.exists(path):
        os.remove(path)
        say(f"Removed {path}")
    return True


def set_entry(path, index, action):
    if not path.startswith("/etc/apt/") or ".." in path:
        say("Refusing to edit files outside /etc/apt")
        return False
    for e in S.parse_file(path):
        if e.index == index:
            edit_entry(e, action)
            say(f"{action}: {e.label()}")
            return True
    say("Entry not found (the file changed?)")
    return False


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------
def _gpg(args, home, timeout=60, input_bytes=None):
    env = dict(os.environ, GNUPGHOME=home, LANG="C", LC_ALL="C")
    try:
        r = subprocess.run(["gpg", "--batch", "--quiet", "--no-tty"] + args, env=env, capture_output=True,
                           timeout=timeout, input=input_bytes)
        return r.returncode, r.stdout, r.stderr
    except Exception as exc:
        return 127, b"", str(exc).encode()


def _download(url, dest):
    r = subprocess.run(["curl", "-fsSL", "--retry", "2", "--connect-timeout", "20", "-o", dest, url],
                       capture_output=True, timeout=120)
    return r.returncode == 0 and os.path.getsize(dest) > 0


def key_ids(path):
    """Long key IDs (and subkey IDs) contained in a keyring/armored key file."""
    with tempfile.TemporaryDirectory() as home:
        code, out, _err = _gpg(["--show-keys", "--with-colons", path], home)
    ids = set()
    for line in out.decode(errors="replace").splitlines():
        f = line.split(":")
        if f[0] in ("pub", "sub") and len(f) > 4:
            ids.add(f[4].upper())
        if f[0] == "fpr" and len(f) > 9:
            ids.add(f[9][-16:].upper())
    return ids


def install_keyring(dest, key_material_paths, armored=None):
    """Merge one or more key files into dest (binary unless dest ends with .asc)."""
    with tempfile.TemporaryDirectory() as home:
        for p in key_material_paths:
            if os.path.exists(p):
                _gpg(["--import", p], home)
        code, data, _ = _gpg(["--export"] + (["--armor"] if (armored or dest.endswith(".asc")) else []), home)
    if code != 0 or not data:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest), prefix=".debos-key-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(tmp, 0o644)
    os.replace(tmp, dest)
    return True


def fetch_key_from_keyservers(keyid, out_path):
    with tempfile.TemporaryDirectory() as home:
        for ks in KEYSERVERS:
            code, _o, _e = _gpg(["--keyserver", ks, "--recv-keys", keyid], home, timeout=60)
            if code == 0:
                code, data, _ = _gpg(["--export", keyid], home)
                if code == 0 and data:
                    with open(out_path, "wb") as fh:
                        fh.write(data)
                    say(f"  fetched {keyid} from {ks}")
                    return True
    return False


def safe_name(text):
    return re.sub(r"[^a-z0-9.-]+", "-", text.lower()).strip("-")[:60] or "repo"


def find_local_keyring(keyid, exclude=()):
    """A keyring file on this system that already contains keyid (or None)."""
    keyid = keyid.upper()[-16:]
    # keyrings maintained by packages first: they are updated when the vendor rotates keys
    order = ("/usr/share/keyrings/", "/var/lib/extrepo/keys/", "/etc/apt/keyrings/", "/etc/apt/trusted.gpg.d/")
    files = sorted(S.keyring_files(), key=lambda p: next((i for i, d in enumerate(order) if p.startswith(d)), len(order)))
    for path in files:
        if path == S.LEGACY_KEYRING or path in exclude or "removed-keys" in path:
            continue
        if any(k.endswith(keyid) for k in key_ids(path)):
            return path
    return None


def repair_entry_key(entry, keyid=None, expired=False):
    """Make sure the key for entry is present and current.  Returns True if fixed."""
    host = entry.host
    sb = entry.signed_by if entry.signed_by.startswith("/") else ""
    # 1. Debian-maintained keyring packages
    if host in KEYRING_PACKAGES or entry.is_official_debian():
        pkg, keyring = KEYRING_PACKAGES.get(host, KEYRING_PACKAGES["deb.debian.org"])
        say(f"  reinstalling {pkg} for {host}")
        r = subprocess.run(["apt-get", "install", "--reinstall", "-y", pkg])
        broken = not sb or not os.path.exists(sb) or (keyid and not any(k.endswith(keyid.upper()[-16:]) for k in key_ids(sb)))
        if broken and os.path.exists(keyring) and sb != keyring:
            fresh = reparse(entry)
            if fresh is not None and edit_entry(fresh, "signed-by", keyring):
                say(f"  Signed-By of {os.path.basename(entry.file)} now points to {keyring}")
                return True
        return r.returncode == 0 and not broken
    # 2. extrepo-managed repositories
    m = re.search(r"/var/lib/extrepo/keys/([^/]+)\.asc$", sb)
    if m and shutil.which("extrepo"):
        say(f"  refreshing extrepo key for {m.group(1)}")
        r = subprocess.run(["extrepo", "update", m.group(1)])
        return r.returncode == 0
    # 3. a missing key that is already on this system (Signed-By points to the wrong file)
    if keyid and not expired:
        local = find_local_keyring(keyid, exclude=(sb,))
        if local:
            fresh = reparse(entry)
            if fresh is not None:
                edit_entry(fresh, "signed-by", local)
                say(f"  key {keyid} found in {local}; Signed-By of {os.path.basename(entry.file)} updated")
                return True
    with tempfile.TemporaryDirectory() as tmp:
        material = []
        url = VENDOR_KEYS.get(host)
        if url:
            dl = os.path.join(tmp, "vendor.key")
            if _download(url, dl):
                say(f"  downloaded current vendor key from {url}")
                material.append(dl)
        if keyid and not material:
            ks = os.path.join(tmp, "ks.gpg")
            if fetch_key_from_keyservers(keyid, ks):
                material.append(ks)
        if not material:
            say(f"  could not find a key for {host or entry.uri}")
            return False
        if sb and not sb.startswith("/usr/share/keyrings/"):
            dest = sb
        else:
            # never rewrite files that belong to keyring packages; use our own file instead
            dest = os.path.join(KEYRING_DIR, f"debos-{safe_name(host or 'repo')}.gpg")
        # merge with the keys already trusted for this repository so nothing is lost
        old = [sb] if sb and os.path.exists(sb) else []
        if not install_keyring(dest, old + material):
            say("  failed to store the key")
            return False
        say(f"  key stored in {dest}")
        if entry.signed_by != dest:
            fresh = reparse(entry)
            if fresh is not None:
                edit_entry(fresh, "signed-by", dest)
                say(f"  Signed-By of {os.path.basename(entry.file)} now points to {dest}")
        return True


def migrate_legacy_keyring():
    legacy = S.LEGACY_KEYRING
    if not os.path.isfile(legacy) or os.path.getsize(legacy) == 0:
        return True
    say("Migrating keys out of the deprecated /etc/apt/trusted.gpg keyring...")
    with tempfile.TemporaryDirectory() as home:
        code, out, _ = _gpg(["--no-default-keyring", "--keyring", legacy, "--list-keys", "--with-colons"], home)
        ids = [l.split(":")[4] for l in out.decode(errors="replace").splitlines() if l.startswith("pub:")]
        for kid in ids:
            code, data, _ = _gpg(["--no-default-keyring", "--keyring", legacy, "--export", kid], home)
            if code == 0 and data:
                dest = os.path.join(TRUSTED_DIR, f"debos-legacy-{kid.lower()}.gpg")
                with open(dest, "wb") as fh:
                    fh.write(data)
                os.chmod(dest, 0o644)
                say(f"  {kid} -> {dest}")
    dest = backup([legacy], "trusted-gpg")
    os.remove(legacy)
    for extra in (legacy + "~",):
        if os.path.exists(extra):
            os.remove(extra)
    say(f"Legacy keyring moved to {dest}. The 'stored in legacy trusted.gpg keyring' warnings are gone.")
    return True


# ---------------------------------------------------------------------------
# Repository Doctor
# ---------------------------------------------------------------------------
def _score(e):
    """How good a definition is when several define the same repository."""
    s = 0
    if e.signed_by:
        s += 1
        if not e.signed_by.startswith("/") or os.path.exists(e.signed_by):
            s += 3
    if e.fmt == "deb822":
        s += 2
    if os.path.basename(e.file).startswith(("debian.sources", "extrepo_")):
        s += 1
    return s


def dedupe(entries):
    """Resolve repositories that are defined more than once, without losing anything.

    APT refuses to work when two definitions of the same (type, URI, suite)
    disagree on Signed-By, and warns about targets configured twice.  For each
    such group the best definition wins (_score).  A losing definition that only
    repeats what the winners define is merged into them (its components are
    added) and disabled.  A definition that also provides suites or types
    nobody else has is kept, with its Signed-By aligned to the winner's.
    """
    active = [e for e in entries if e.enabled and not e.is_cdrom()]
    groups = {}
    for e in active:
        for k in set(e.keys()):
            group = groups.setdefault(k, [])
            if all(e is not o for o in group):
                group.append(e)
    winner = {k: max(g, key=_score) for k, g in groups.items() if len(g) > 1}
    disabled = aligned = 0
    for e in sorted(active, key=lambda x: (x.file, x.start)):
        keys = set(e.keys())
        dup = {k for k in keys if k in winner and winner[k] is not e}
        if not dup:
            continue
        rivals = []
        for k in sorted(dup):
            if all(winner[k] is not r for r in rivals):
                rivals.append(winner[k])
        if dup == keys:
            # everything e defines is defined by better entries: merge its components, then disable it
            merged = True
            for w in rivals:
                fresh_w = reparse(w)
                if fresh_w is None:
                    merged = False
                    continue
                extra = [c for c in e.components if c not in fresh_w.components]
                if extra and edit_entry(fresh_w, "components", fresh_w.components + extra):
                    say(f"  added {' '.join(extra)} to {fresh_w.label()}")
            fresh = reparse(e)
            if merged and fresh is not None and edit_entry(fresh, "disable"):
                disabled += 1
                say(f"  disabled duplicate: {e.label()}")
            continue
        # e also provides something unique: keep it but make Signed-By agree with the winner(s)
        wanted = {r.signed_by for r in rivals}
        target = next(iter(wanted))
        if len(wanted) != 1 or "\n" in target or target == e.signed_by:
            continue
        fresh = reparse(e)
        if fresh is not None and edit_entry(fresh, "signed-by", target):
            aligned += 1
            say(f"  {os.path.basename(e.file)}: Signed-By set to {target or '(none)'} to match {os.path.basename(rivals[0].file)}")
    say(f"Duplicates: {disabled} merged and disabled, {aligned} aligned")
    return disabled + aligned


# apt < 3 prints "GPG error: URI SUITE InRelease: ...", apt >= 3 (trixie and later)
# "OpenPGP signature verification failed: URI SUITE InRelease: ..."; with the sqv
# verifier (Debian's default since trixie) the reason reads "Missing key ID, which is
# needed to verify signature" or "Signing key on ID is not bound/alive".
_SIG = r"(?:GPG error|OpenPGP signature verification failed): (\S+) (\S+) (?:In)?Release:"
APT_PATTERNS = {
    "nopubkey": re.compile(_SIG + r".*?(?:NO_PUBKEY |Missing key )([0-9A-F]{8,40})"),
    "expkeysig": re.compile(_SIG + r".*?(?:EXPKEYSIG |REVKEYSIG |Signing key on )([0-9A-F]{8,40})"),
    "no_release": re.compile(r"The repository '(\S+) (\S+) Release' does not have a Release file"),
    "not_signed": re.compile(r"The repository '(\S+) (\S+) (?:In)?Release' is not signed"),
    "releaseinfo": re.compile(r"Repository '(\S+) (\S+) (?:In)?Release' changed its '(\w+)' value"),
    "not_valid_yet": re.compile(r"Release file for (\S+) is not valid yet"),
    "arch_skip": re.compile(r"Skipping acquire of configured file '[^']+/binary-(\w+)/Packages' as repository '(\S+) (\S+) InRelease' doesn't support architecture"),
    "legacy": re.compile(r"Key is stored in legacy trusted\.gpg keyring"),
    "conflict": re.compile(r"Conflicting values set for option Signed-By regarding source (\S+) (\S+):"),
}


def run_apt_update(extra=()):
    env = dict(os.environ, LANG="C", LC_ALL="C")
    say("$ apt-get update " + " ".join(extra))
    proc = subprocess.Popen(["apt-get", "update"] + list(extra), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, text=True)
    lines = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        lines.append(line.rstrip("\n"))
    proc.wait()
    return proc.returncode, lines


def analyse_apt_output(lines):
    found = {k: [] for k in APT_PATTERNS}
    for line in lines:
        for k, rx in APT_PATTERNS.items():
            m = rx.search(line)
            if m:
                found[k].append(m.groups())
    return found


def find_entries(uri, suite):
    uri_n = S.normalize_uri(uri)
    res = []
    for e in S.parse_all():
        if not e.enabled:
            continue
        if any(S.normalize_uri(u) == uri_n or uri_n.startswith(S.normalize_uri(u)) for u in e.uris) and \
                (suite in e.suites or suite.rstrip("/") in [s.rstrip("/") for s in e.suites]):
            res.append(e)
    return res


def doctor(fix=True, update=True, disable_dead=True):
    say("Repository Doctor - scanning APT configuration")
    files = S.source_files()
    if fix:
        backup(files + [S.LEGACY_KEYRING], "doctor")
    entries = S.parse_all(files)
    issues = S.entry_issues(entries)
    for issue in issues:
        say(f"[{issue['severity']}] {issue['title']}")
    if not fix:
        return not issues
    # static fixes
    for e in entries:
        if e.enabled and e.is_cdrom():
            fresh = reparse(e)
            if fresh is not None:
                edit_entry(fresh, "disable")
                say(f"  disabled CD/DVD entry in {e.file}")
    dedupe(S.parse_all())
    for issue in S.entry_issues(S.parse_all()):
        if issue["id"] == "missing-key":
            for e in issue["entries"]:
                repair_entry_key(e)
    migrate_legacy_keyring()
    if not update:
        return True
    # dynamic fixes driven by apt-get update output
    rc, lines = run_apt_update()
    found = analyse_apt_output(lines)
    changed = False
    if found["releaseinfo"]:
        say("A repository changed its release information (normal after a new Debian release); accepting it.")
        rc, lines = run_apt_update(["--allow-releaseinfo-change"])
        found = analyse_apt_output(lines)
    if found["not_valid_yet"]:
        say("The system clock seems wrong. Enabling network time synchronisation (timedatectl set-ntp true).")
        subprocess.run(["timedatectl", "set-ntp", "true"])
    repaired = set()
    for kind in ("nopubkey", "expkeysig"):
        for uri, suite, keyid in dict.fromkeys(found[kind]):
            say(f"{'Missing' if kind == 'nopubkey' else 'Expired or rejected'} key {keyid} for {uri} {suite}")
            for e in find_entries(uri, suite):
                if repair_entry_key(e, keyid=keyid, expired=kind == "expkeysig"):
                    repaired.add((S.normalize_uri(uri), suite))
                    changed = True
    for uri, suite in found["conflict"]:
        say(f"Conflicting Signed-By for {uri} {suite}: removing duplicates")
        changed |= dedupe(S.parse_all()) > 0
    for arch, uri, suite in found["arch_skip"]:
        native = subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True).stdout.strip()
        for e in find_entries(uri, suite):
            if e.fmt == "deb822" and "architectures" not in e.options:
                text = S._read(e.file)
                lines2 = S._set_field(text.splitlines(), e, "Architectures", native)
                atomic_write(e.file, "\n".join(lines2) + "\n")
                say(f"  limited {os.path.basename(e.file)} to {native} (repository has no {arch} packages)")
                changed = True
            elif e.fmt == "list" and "arch" not in e.options:
                text = S._read(e.file).splitlines()
                line = text[e.start]
                mm = re.match(r"^(\s*(?:deb|deb-src))\s+(?:\[([^\]]*)\]\s+)?(.*)$", line)
                if mm:
                    opts = (mm.group(2) or "").split() + [f"arch={native}"]
                    text[e.start] = f"{mm.group(1)} [{' '.join(opts)}] {mm.group(3)}"
                    atomic_write(e.file, "\n".join(text) + "\n")
                    say(f"  limited {os.path.basename(e.file)} to {native}")
                    changed = True
    if disable_dead:
        for kind in ("no_release", "not_signed"):
            for uri, suite in dict.fromkeys(found[kind]):
                if (S.normalize_uri(uri), suite) in repaired:
                    continue  # its key was just repaired; the next update shows whether it works now
                for e in find_entries(uri, suite):
                    if e.is_official_debian():
                        say(f"  official Debian entry {uri} {suite} " + ("has no Release file - check the suite name "
                            "(Updates & Release page)" if kind == "no_release" else "cannot be verified - reinstall debian-archive-keyring"))
                        continue
                    fresh = reparse(e)
                    if fresh is not None and edit_entry(fresh, "disable"):
                        say(f"  disabled {'dead or unsupported' if kind == 'no_release' else 'unverifiable (no usable signing key)'}"
                            f" repository: {e.label()}")
                        changed = True
    if found["legacy"]:
        migrate_legacy_keyring()
        changed = True
    if changed:
        rc, lines = run_apt_update()
        found = analyse_apt_output(lines)
    remaining = sum(len(v) for k, v in found.items() if k not in ("releaseinfo",))
    if rc == 0 and remaining == 0:
        say("Repository Doctor: APT is healthy.")
        return True
    say(f"Repository Doctor finished; {remaining} problem(s) need manual attention (see above).")
    return rc == 0


# ---------------------------------------------------------------------------
# Kernels installed outside dpkg (e.g. "make install" builds from Debos < 0.5)
# ---------------------------------------------------------------------------
def owned_by_dpkg(path):
    r = subprocess.run(["dpkg-query", "-S", path], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def remove_kernel_files(versions):
    running = os.uname().release
    ok = True
    for ver in versions:
        if not re.match(r"^[0-9][A-Za-z0-9._+~-]*$", ver):
            say(f"Invalid kernel version: {ver}")
            ok = False
            continue
        if ver == running:
            say(f"Refusing to remove the running kernel {ver}")
            ok = False
            continue
        files = [f"/boot/{n}-{ver}" for n in ("vmlinuz", "initrd.img", "System.map", "config")]
        files += [f"/boot/{n}-{ver}.old" for n in ("vmlinuz", "initrd.img")]
        if any(owned_by_dpkg(f) for f in files if os.path.exists(f)) or owned_by_dpkg(f"/lib/modules/{ver}") \
                or owned_by_dpkg(f"/usr/lib/modules/{ver}"):
            say(f"{ver} is managed by a package - remove it with APT instead")
            ok = False
            continue
        for f in files:
            if os.path.lexists(f):
                os.remove(f)
                say(f"  removed {f}")
        for d in (f"/lib/modules/{ver}", f"/usr/lib/modules/{ver}", f"/var/lib/initramfs-tools/{ver}"):
            if os.path.isdir(d) and not os.path.islink(d):
                shutil.rmtree(d, ignore_errors=True)
                say(f"  removed {d}")
            elif os.path.isfile(d):
                os.remove(d)
                say(f"  removed {d}")
        for dkms_dir in glob.glob(f"/var/lib/dkms/*/*/{ver}"):
            shutil.rmtree(dkms_dir, ignore_errors=True)
            say(f"  removed DKMS build {dkms_dir}")
        say(f"Kernel {ver} removed.")
    if shutil.which("update-grub"):
        subprocess.run(["update-grub"])
    return ok
