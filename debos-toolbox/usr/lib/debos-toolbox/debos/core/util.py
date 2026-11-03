"""Small helpers shared by the GUI and the root helper.

Nothing in here imports GTK, so the module is safe to use from the root
helper and from unit tests.
"""

import getpass
import json
import os
import pwd
import re
import shutil
import subprocess

from .. import APP_SLUG

# /usr/lib/debos-toolbox when installed, the source tree when run from git.
LIBDIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATADIR = os.path.abspath(os.path.join(LIBDIR, "..", "..", "share", APP_SLUG))
SHELL_LIB = os.path.join(LIBDIR, "lib.sh")
LAUNCHER = os.path.join(LIBDIR, "debos-launch")
ROOT_RUNNER = os.path.join(LIBDIR, "debos-root")
HELPER = os.path.join(LIBDIR, "debos-helper")

ROOT_LOG = "/var/log/debos-toolbox/tasks.log"
BACKUP_DIR = "/var/backups/debos-toolbox"


def run(args, timeout=15, shell=False, env=None, input_text=None):
    """Run a command and return (returncode, stdout). Never raises."""
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                             shell=shell, env=env, input=input_text)
        return res.returncode, res.stdout
    except Exception:
        return 127, ""


def out(args, timeout=15, shell=False):
    """stdout of a command, stripped ('' on any failure)."""
    return run(args, timeout=timeout, shell=shell)[1].strip()


def read_file(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return default


def which(name):
    return shutil.which(name) is not None


def human_size(num, digits=1):
    num = float(num or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024 or unit == "TB":
            if unit == "B":
                return f"{num:.0f} B"
            return f"{num:.{digits}f} {unit}"
        num /= 1024.0
    return f"{num:.{digits}f} TB"


def path_size(path, limit_files=200000):
    """Apparent size of a file or directory tree without following symlinks."""
    try:
        st = os.lstat(path)
    except OSError:
        return 0
    if not os.path.isdir(path) or os.path.islink(path):
        return st.st_size
    total, seen = 0, 0
    for base, dirs, files in os.walk(path, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in files:
            seen += 1
            if seen > limit_files:
                return total
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def desktop_user():
    """(name, uid, home) of the person using the desktop, even under sudo/pkexec."""
    candidates = [os.environ.get("SUDO_USER"), os.environ.get("PKEXEC_UID")]
    for cand in candidates:
        if not cand:
            continue
        try:
            ent = pwd.getpwuid(int(cand)) if cand.isdigit() else pwd.getpwnam(cand)
            return ent.pw_name, ent.pw_uid, ent.pw_dir
        except (KeyError, ValueError):
            continue
    try:
        ent = pwd.getpwuid(os.getuid())
        return ent.pw_name, ent.pw_uid, ent.pw_dir
    except KeyError:
        return getpass.getuser(), os.getuid(), os.path.expanduser("~")


def user_groups(name):
    code, text = run(["id", "-nG", name])
    return set(text.split()) if code == 0 else set()


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_SLUG)


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, APP_SLUG)


def runtime_dir():
    """Private per-user directory for generated task scripts (0700)."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base and os.path.isdir(base) and os.access(base, os.W_OK):
        path = os.path.join(base, APP_SLUG)
    else:
        path = f"/tmp/{APP_SLUG}-{os.getuid()}"
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


class Settings:
    """Tiny JSON settings store in ~/.config/debos-toolbox/settings.json."""

    DEFAULTS = {
        "language": "en",
        "theme": "system",
        "ignored_recommendations": [],
        "privilege": "auto",
        "console_font_size": 10,
        "show_hints": True,
    }

    def __init__(self):
        self.path = os.path.join(config_dir(), "settings.json")
        self.data = dict(self.DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass

    def get(self, key):
        return self.data.get(key, self.DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass


_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:~-]*$")


def safe_pkg(name):
    """True if name looks like a Debian package name (optionally with :arch)."""
    return bool(name) and bool(_SAFE_NAME.match(name)) and len(name) < 120


def shq(value):
    """shlex.quote without importing shlex everywhere."""
    import shlex
    return shlex.quote(str(value))
