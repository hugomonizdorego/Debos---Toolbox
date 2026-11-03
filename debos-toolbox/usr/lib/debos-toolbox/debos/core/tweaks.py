"""Desktop tweaks (ideas from Ubuntu Tweak), applied with the user's own rights.

Backends:
  gsettings - GNOME, Budgie, Cinnamon, MATE (through Gio.Settings, only keys that exist)
  xfconf    - Xfce (xfconf-query)
"""

import glob
import os
import re
import shutil

from .util import run

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):  # unit tests without GI
    Gio = GLib = None


def theme_choices(kind):
    """Installed GTK themes ('gtk'), icon themes ('icons') or cursor themes ('cursors')."""
    home = os.path.expanduser("~")
    found = set()
    if kind == "gtk":
        for base in ("/usr/share/themes", os.path.join(home, ".themes"), os.path.join(home, ".local/share/themes")):
            for d in glob.glob(os.path.join(base, "*")):
                if os.path.isdir(os.path.join(d, "gtk-3.0")) or os.path.isdir(os.path.join(d, "gtk-4.0")):
                    found.add(os.path.basename(d))
        found.add("Adwaita")
        found.add("Adwaita-dark")
    elif kind == "xfwm":
        for base in ("/usr/share/themes", os.path.join(home, ".themes"), os.path.join(home, ".local/share/themes")):
            for d in glob.glob(os.path.join(base, "*")):
                if os.path.isdir(os.path.join(d, "xfwm4")):
                    found.add(os.path.basename(d))
    else:
        for base in ("/usr/share/icons", os.path.join(home, ".icons"), os.path.join(home, ".local/share/icons")):
            for d in glob.glob(os.path.join(base, "*")):
                name = os.path.basename(d)
                if kind == "cursors":
                    if os.path.isdir(os.path.join(d, "cursors")):
                        found.add(name)
                elif os.path.isfile(os.path.join(d, "index.theme")) and name not in ("hicolor", "default", "locolor") and \
                        any(os.path.isdir(os.path.join(d, s)) for s in os.listdir(d) if s not in ("cursors",)):
                    if not (os.path.isdir(os.path.join(d, "cursors")) and len(os.listdir(d)) <= 3):
                        found.add(name)
    return sorted(found, key=str.lower)


BUTTON_LAYOUTS = [
    ("appmenu:minimize,maximize,close", "Right: minimize, maximize, close"),
    ("appmenu:close", "Right: close only (GNOME default)"),
    ("close,minimize,maximize:appmenu", "Left: close, minimize, maximize (macOS style)"),
    ("appmenu:maximize,close", "Right: maximize, close"),
]
ACCENTS = [(c, c.capitalize()) for c in ("blue", "teal", "green", "yellow", "orange", "red", "pink", "purple", "slate")]

# (section, title, description, backend, schema/channel, key/property, kind, options)
GNOME = [
    ("Appearance", "Style", "Light or dark style for apps that support it.", "gsettings", "org.gnome.desktop.interface", "color-scheme", "enum",
     [("default", "Default"), ("prefer-light", "Light"), ("prefer-dark", "Dark")]),
    ("Appearance", "Accent colour", "Colour of buttons, switches and selections (GNOME 47+).", "gsettings", "org.gnome.desktop.interface",
     "accent-color", "enum", ACCENTS),
    ("Appearance", "Application theme (GTK 3)", "Theme for legacy GTK 3 applications.", "gsettings", "org.gnome.desktop.interface", "gtk-theme", "choice", "gtk"),
    ("Appearance", "Icon theme", None, "gsettings", "org.gnome.desktop.interface", "icon-theme", "choice", "icons"),
    ("Appearance", "Cursor theme", None, "gsettings", "org.gnome.desktop.interface", "cursor-theme", "choice", "cursors"),
    ("Appearance", "Cursor size", None, "gsettings", "org.gnome.desktop.interface", "cursor-size", "enum",
     [(24, "Default (24)"), (32, "Medium (32)"), (48, "Large (48)"), (64, "Larger (64)")]),
    ("Fonts", "Text scaling", "Make all text larger or smaller without changing the resolution.", "gsettings", "org.gnome.desktop.interface",
     "text-scaling-factor", "enum", [(0.9, "90%"), (1.0, "100%"), (1.1, "110%"), (1.15, "115%"), (1.25, "125%"), (1.5, "150%")]),
    ("Fonts", "Antialiasing", None, "gsettings", "org.gnome.desktop.interface", "font-antialiasing", "enum",
     [("grayscale", "Grayscale (standard)"), ("rgba", "Subpixel (LCD)"), ("none", "None")]),
    ("Fonts", "Hinting", None, "gsettings", "org.gnome.desktop.interface", "font-hinting", "enum",
     [("slight", "Slight"), ("medium", "Medium"), ("full", "Full"), ("none", "None")]),
    ("Top bar", "Show weekday", None, "gsettings", "org.gnome.desktop.interface", "clock-show-weekday", "bool", None),
    ("Top bar", "Show date", None, "gsettings", "org.gnome.desktop.interface", "clock-show-date", "bool", None),
    ("Top bar", "Show seconds", None, "gsettings", "org.gnome.desktop.interface", "clock-show-seconds", "bool", None),
    ("Top bar", "Clock format", None, "gsettings", "org.gnome.desktop.interface", "clock-format", "enum", [("24h", "24-hour"), ("12h", "12-hour")]),
    ("Top bar", "Battery percentage", None, "gsettings", "org.gnome.desktop.interface", "show-battery-percentage", "bool", None),
    ("Top bar", "Hot corner", "Open the overview by pushing the pointer to the top-left corner.", "gsettings", "org.gnome.desktop.interface",
     "enable-hot-corners", "bool", None),
    ("Behaviour", "Animations", "Disable for a snappier feel on slow hardware.", "gsettings", "org.gnome.desktop.interface", "enable-animations", "bool", None),
    ("Behaviour", "Overlay scrollbars", "Hide scrollbars until you scroll.", "gsettings", "org.gnome.desktop.interface", "overlay-scrolling", "bool", None),
    ("Behaviour", "Locate pointer with Ctrl", None, "gsettings", "org.gnome.desktop.interface", "locate-pointer", "bool", None),
    ("Windows", "Titlebar buttons", None, "gsettings", "org.gnome.desktop.wm.preferences", "button-layout", "enum", BUTTON_LAYOUTS),
    ("Windows", "Double-click on titlebar", None, "gsettings", "org.gnome.desktop.wm.preferences", "action-double-click-titlebar", "enum",
     [("toggle-maximize", "Maximize"), ("minimize", "Minimize"), ("toggle-shade", "Shade"), ("none", "Nothing"), ("menu", "Window menu")]),
    ("Windows", "Focus mode", None, "gsettings", "org.gnome.desktop.wm.preferences", "focus-mode", "enum",
     [("click", "Click to focus"), ("sloppy", "Focus on hover"), ("mouse", "Focus follows mouse")]),
    ("Windows", "Center new windows", None, "gsettings", "org.gnome.mutter", "center-new-windows", "bool", None),
    ("Windows", "Attach modal dialogs", None, "gsettings", "org.gnome.mutter", "attach-modal-dialogs", "bool", None),
    ("Windows", "Edge tiling", "Snap windows to the screen halves.", "gsettings", "org.gnome.mutter", "edge-tiling", "bool", None),
    ("Windows", "Resize with right mouse button", None, "gsettings", "org.gnome.desktop.wm.preferences", "resize-with-right-button", "bool", None),
    ("Workspaces", "Dynamic workspaces", None, "gsettings", "org.gnome.mutter", "dynamic-workspaces", "bool", None),
    ("Workspaces", "Number of workspaces", "Used when dynamic workspaces are off.", "gsettings", "org.gnome.desktop.wm.preferences",
     "num-workspaces", "enum", [(n, str(n)) for n in range(1, 11)]),
    ("Workspaces", "Workspaces on primary display only", None, "gsettings", "org.gnome.mutter", "workspaces-only-on-primary", "bool", None),
    ("Mouse & touchpad", "Tap to click", None, "gsettings", "org.gnome.desktop.peripherals.touchpad", "tap-to-click", "bool", None),
    ("Mouse & touchpad", "Natural scrolling (touchpad)", None, "gsettings", "org.gnome.desktop.peripherals.touchpad", "natural-scroll", "bool", None),
    ("Mouse & touchpad", "Disable touchpad while typing", None, "gsettings", "org.gnome.desktop.peripherals.touchpad", "disable-while-typing", "bool", None),
    ("Mouse & touchpad", "Mouse acceleration", None, "gsettings", "org.gnome.desktop.peripherals.mouse", "accel-profile", "enum",
     [("default", "Default"), ("flat", "Flat (gaming)"), ("adaptive", "Adaptive")]),
    ("Mouse & touchpad", "Natural scrolling (mouse)", None, "gsettings", "org.gnome.desktop.peripherals.mouse", "natural-scroll", "bool", None),
    ("Power", "Blank screen after", None, "gsettings", "org.gnome.desktop.session", "idle-delay", "enum",
     [(0, "Never"), (60, "1 minute"), (300, "5 minutes"), (600, "10 minutes"), (900, "15 minutes")]),
    ("Power", "Power button", None, "gsettings", "org.gnome.settings-daemon.plugins.power", "power-button-action", "enum",
     [("interactive", "Ask"), ("suspend", "Suspend"), ("hibernate", "Hibernate"), ("nothing", "Nothing")]),
    ("Power", "Automatic suspend on AC", None, "gsettings", "org.gnome.settings-daemon.plugins.power", "sleep-inactive-ac-type", "enum",
     [("suspend", "Suspend"), ("nothing", "Never")]),
    ("Files", "Show hidden files", "In file dialogs of GTK 4 and GTK 3 apps.", "gsettings", "org.gtk.gtk4.Settings.FileChooser", "show-hidden", "bool", None),
    ("Files", "Show hidden files (GTK 3 dialogs)", None, "gsettings", "org.gtk.Settings.FileChooser", "show-hidden", "bool", None),
    ("Files", "Folders before files", None, "gsettings", "org.gtk.gtk4.Settings.FileChooser", "sort-directories-first", "bool", None),
    ("Files", "Files: default view", None, "gsettings", "org.gnome.nautilus.preferences", "default-folder-viewer", "enum",
     [("icon-view", "Icons"), ("list-view", "List")]),
    ("Files", "Files: 'Delete permanently' option", None, "gsettings", "org.gnome.nautilus.preferences", "show-delete-permanently", "bool", None),
    ("Files", "Files: 'Create link' option", None, "gsettings", "org.gnome.nautilus.preferences", "show-create-link", "bool", None),
    ("Privacy", "Remember recent files", None, "gsettings", "org.gnome.desktop.privacy", "remember-recent-files", "bool", None),
    ("Privacy", "Empty Trash automatically", "Remove trashed files after the age below.", "gsettings", "org.gnome.desktop.privacy",
     "remove-old-trash-files", "bool", None),
    ("Privacy", "Delete old temporary files automatically", None, "gsettings", "org.gnome.desktop.privacy", "remove-old-temp-files", "bool", None),
    ("Privacy", "Age for automatic deletion", None, "gsettings", "org.gnome.desktop.privacy", "old-files-age", "enum",
     [(1, "1 day"), (7, "7 days"), (14, "14 days"), (30, "30 days")]),
    ("Display", "Night light", "Warmer colours in the evening.", "gsettings", "org.gnome.settings-daemon.plugins.color", "night-light-enabled", "bool", None),
    ("Sound", "Allow volume above 100%", None, "gsettings", "org.gnome.desktop.sound", "allow-volume-above-100-percent", "bool", None),
    ("Sound", "Event sounds", None, "gsettings", "org.gnome.desktop.sound", "event-sounds", "bool", None),
]

CINNAMON = [
    ("Appearance", "Application theme", None, "gsettings", "org.cinnamon.desktop.interface", "gtk-theme", "choice", "gtk"),
    ("Appearance", "Icon theme", None, "gsettings", "org.cinnamon.desktop.interface", "icon-theme", "choice", "icons"),
    ("Appearance", "Cursor theme", None, "gsettings", "org.cinnamon.desktop.interface", "cursor-theme", "choice", "cursors"),
    ("Fonts", "Text scaling", None, "gsettings", "org.cinnamon.desktop.interface", "text-scaling-factor", "enum",
     [(0.9, "90%"), (1.0, "100%"), (1.1, "110%"), (1.25, "125%"), (1.5, "150%")]),
    ("Top bar", "Show date in clock", None, "gsettings", "org.cinnamon.desktop.interface", "clock-show-date", "bool", None),
    ("Top bar", "Show seconds", None, "gsettings", "org.cinnamon.desktop.interface", "clock-show-seconds", "bool", None),
    ("Windows", "Titlebar buttons", None, "gsettings", "org.cinnamon.desktop.wm.preferences", "button-layout", "enum",
     [(":minimize,maximize,close", "Right: minimize, maximize, close"), ("close,minimize,maximize:", "Left (macOS style)")]),
    ("Windows", "Focus mode", None, "gsettings", "org.cinnamon.desktop.wm.preferences", "focus-mode", "enum",
     [("click", "Click to focus"), ("sloppy", "Focus on hover"), ("mouse", "Focus follows mouse")]),
    ("Behaviour", "Desktop effects", None, "gsettings", "org.cinnamon", "desktop-effects-workspace", "bool", None),
    ("Mouse & touchpad", "Tap to click", None, "gsettings", "org.cinnamon.desktop.peripherals.touchpad", "tap-to-click", "bool", None),
    ("Files", "Nemo: show hidden files", None, "gsettings", "org.nemo.preferences", "show-hidden-files", "bool", None),
]

MATE = [
    ("Appearance", "Application theme", None, "gsettings", "org.mate.interface", "gtk-theme", "choice", "gtk"),
    ("Appearance", "Icon theme", None, "gsettings", "org.mate.interface", "icon-theme", "choice", "icons"),
    ("Appearance", "Cursor theme", None, "gsettings", "org.mate.peripherals-mouse", "cursor-theme", "choice", "cursors"),
    ("Windows", "Titlebar buttons", None, "gsettings", "org.mate.Marco.general", "button-layout", "enum",
     [("menu:minimize,maximize,close", "Right: minimize, maximize, close"), ("close,minimize,maximize:menu", "Left (macOS style)")]),
    ("Windows", "Compositing", "Shadows and transparency.", "gsettings", "org.mate.Marco.general", "compositing-manager", "bool", None),
    ("Mouse & touchpad", "Tap to click", None, "gsettings", "org.mate.peripherals-touchpad", "tap-to-click", "bool", None),
    ("Files", "Caja: show hidden files", None, "gsettings", "org.mate.caja.preferences", "show-hidden-files", "bool", None),
]

XFCE = [
    ("Appearance", "Application theme", None, "xfconf", "xsettings", "/Net/ThemeName", "choice", "gtk"),
    ("Appearance", "Icon theme", None, "xfconf", "xsettings", "/Net/IconThemeName", "choice", "icons"),
    ("Appearance", "Cursor theme", None, "xfconf", "xsettings", "/Gtk/CursorThemeName", "choice", "cursors"),
    ("Fonts", "Screen DPI", "Higher values make text larger.", "xfconf", "xsettings", "/Xft/DPI", "enum",
     [(96, "96 (100%)"), (108, "108 (112%)"), (120, "120 (125%)"), (144, "144 (150%)"), (192, "192 (200%)")]),
    ("Windows", "Window theme", None, "xfconf", "xfwm4", "/general/theme", "choice", "xfwm"),
    ("Windows", "Titlebar buttons", None, "xfconf", "xfwm4", "/general/button_layout", "enum",
     [("O|HMC", "Right: minimize, maximize, close"), ("CMH|O", "Left (macOS style)"), ("O|C", "Close only")]),
    ("Windows", "Compositor (shadows, transparency)", None, "xfconf", "xfwm4", "/general/use_compositing", "bool", None),
    ("Workspaces", "Number of workspaces", None, "xfconf", "xfwm4", "/general/workspace_count", "enum", [(n, str(n)) for n in range(1, 9)]),
    ("Files", "Thunar: show hidden files", None, "xfconf", "thunar", "/last-show-hidden", "bool", None),
]


class Tweak:
    def __init__(self, spec):
        (self.section, self.title, self.desc, self.backend, self.schema, self.key, self.kind, self.options) = spec
        self._settings = None

    # ------------------------------------------------------------ backends
    def available(self):
        if self.backend == "gsettings":
            if Gio is None:
                return False
            src = Gio.SettingsSchemaSource.get_default()
            schema = src.lookup(self.schema, True) if src else None
            return bool(schema) and schema.has_key(self.key)
        if self.backend == "xfconf":
            return shutil.which("xfconf-query") is not None
        return False

    def settings(self):
        if self._settings is None:
            self._settings = Gio.Settings.new(self.schema)
        return self._settings

    def get(self):
        if self.backend == "gsettings":
            v = self.settings().get_value(self.key)
            return v.unpack()
        code, text = run(["xfconf-query", "-c", self.schema, "-p", self.key], timeout=5)
        text = text.strip()
        if self.kind == "bool":
            return text == "true"
        if self.kind == "enum" and self.options and isinstance(self.options[0][0], int):
            return int(text) if re.match(r"^-?\d+$", text) else None
        return text

    def set(self, value):
        if self.backend == "gsettings":
            s = self.settings()
            cur = s.get_value(self.key)
            vtype = cur.get_type_string()
            if vtype == "b":
                s.set_boolean(self.key, bool(value))
            elif vtype == "i":
                s.set_int(self.key, int(value))
            elif vtype == "u":
                s.set_uint(self.key, int(value))
            elif vtype == "d":
                s.set_double(self.key, float(value))
            elif vtype == "s":
                s.set_string(self.key, str(value))
            else:
                s.set_value(self.key, GLib.Variant(vtype, value))
            Gio.Settings.sync()
            return True
        typ = "bool" if self.kind == "bool" else ("int" if isinstance(value, int) else "string")
        val = ("true" if value else "false") if self.kind == "bool" else str(value)
        code, _t = run(["xfconf-query", "-c", self.schema, "-p", self.key, "--create", "-t", typ, "-s", val], timeout=5)
        return code == 0

    def choices(self):
        if self.kind == "choice":
            names = theme_choices(self.options)
            return [(n, n) for n in names]
        return list(self.options or [])


def for_desktop(names):
    """Tweaks for the running desktop (names = lowercase XDG_CURRENT_DESKTOP parts)."""
    specs = []
    if any(n in names for n in ("x-cinnamon", "cinnamon")):
        specs = CINNAMON
    elif "mate" in names:
        specs = MATE
    elif "xfce" in names:
        specs = XFCE
    else:
        specs = GNOME   # GNOME, Budgie, Unity, Pantheon and anything using org.gnome schemas
    tweaks = [Tweak(s) for s in specs]
    return [t for t in tweaks if t.available()]


# ------------------------------------------------------------- startup apps
AUTOSTART_SYSTEM = "/etc/xdg/autostart"


def autostart_user_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "autostart")


def parse_desktop_file(path):
    data, section = {}, None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("["):
                    section = line.strip("[]")
                    continue
                if section == "Desktop Entry" and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    data.setdefault(k.strip(), v.strip())
    except OSError:
        pass
    return data


def autostart_entries(desktop_names):
    """Merged list of autostart entries; user files override system ones by name."""
    entries = {}
    for directory, origin in ((AUTOSTART_SYSTEM, "system"), (autostart_user_dir(), "user")):
        for path in sorted(glob.glob(os.path.join(directory, "*.desktop"))):
            fname = os.path.basename(path)
            d = parse_desktop_file(path)
            prev = entries.get(fname)
            enabled = d.get("Hidden", "false").lower() != "true" and d.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
            only = [x.lower() for x in d.get("OnlyShowIn", "").split(";") if x]
            nots = [x.lower() for x in d.get("NotShowIn", "").split(";") if x]
            relevant = (not only or any(n in only for n in desktop_names)) and not any(n in nots for n in desktop_names)
            entries[fname] = {
                "file": fname, "path": path, "origin": origin if not prev else "override",
                "system_path": prev["system_path"] if prev else (path if origin == "system" else None),
                "name": d.get("Name", (prev or {}).get("name", fname[:-8])), "comment": d.get("Comment", (prev or {}).get("comment", "")),
                "exec": d.get("Exec", (prev or {}).get("exec", "")), "icon": d.get("Icon", (prev or {}).get("icon", "")),
                "enabled": enabled, "relevant": relevant, "no_display": d.get("NoDisplay", "false").lower() == "true",
            }
    return sorted(entries.values(), key=lambda e: e["name"].lower())


def set_autostart(entry, enabled):
    user_dir = autostart_user_dir()
    os.makedirs(user_dir, exist_ok=True)
    target = os.path.join(user_dir, entry["file"])
    if entry["system_path"] and enabled and os.path.exists(target):
        # an override that only disabled a system entry can simply be removed
        d = parse_desktop_file(target)
        if d.get("Hidden", "").lower() == "true" or d.get("X-GNOME-Autostart-enabled", "").lower() == "false":
            os.remove(target)
            if os.path.exists(entry["system_path"]):
                return True
    src = target if os.path.exists(target) else entry["system_path"] or entry["path"]
    try:
        with open(src, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = ["[Desktop Entry]", "Type=Application", f"Name={entry['name']}", f"Exec={entry['exec']}"]
    lines = [l for l in lines if not l.startswith(("Hidden=", "X-GNOME-Autostart-enabled="))]
    try:
        idx = lines.index("[Desktop Entry]") + 1
    except ValueError:
        lines.insert(0, "[Desktop Entry]")
        idx = 1
    lines.insert(idx, f"Hidden={'false' if enabled else 'true'}")
    lines.insert(idx + 1, f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return True


def add_autostart(name, command, delay=0):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "custom"
    path = os.path.join(autostart_user_dir(), f"debos-{slug}.desktop")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", f"Exec={command}", "Hidden=false",
             "X-GNOME-Autostart-enabled=true", "Comment=Added with Debos - Toolbox"]
    if delay:
        lines.append(f"X-GNOME-Autostart-Delay={int(delay)}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# ------------------------------------------------------------- default apps
ROLES = [
    ("browser", "Web browser", "web-browser-symbolic", ["x-scheme-handler/http", "x-scheme-handler/https", "text/html"]),
    ("mail", "Email", "mail-unread-symbolic", ["x-scheme-handler/mailto"]),
    ("files", "File manager", "folder-symbolic", ["inode/directory"]),
    ("text", "Text editor", "text-editor-symbolic", ["text/plain"]),
    ("image", "Image viewer", "camera-photo-symbolic", ["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "image/tiff"]),
    ("video", "Video player", "media-playback-start-symbolic", ["video/mp4", "video/x-matroska", "video/webm", "video/x-msvideo", "video/quicktime"]),
    ("music", "Music player", "audio-speakers-symbolic", ["audio/mpeg", "audio/flac", "audio/ogg", "audio/x-wav", "audio/mp4"]),
    ("pdf", "PDF viewer", "x-office-document-symbolic", ["application/pdf"]),
    ("archive", "Archive manager", "package-x-generic-symbolic", ["application/zip", "application/x-7z-compressed", "application/x-tar",
                                                                    "application/gzip", "application/x-xz-compressed-tar"]),
]


# ------------------------------------------------------- templates & scripts
TEMPLATES = [
    ("Text document.txt", "Text document", ""),
    ("Markdown document.md", "Markdown", "# Title\n\n"),
    ("Shell script.sh", "Shell script", "#!/bin/bash\nset -euo pipefail\n\n"),
    ("Python script.py", "Python script", "#!/usr/bin/env python3\n\n\ndef main():\n    pass\n\n\nif __name__ == \"__main__\":\n    main()\n"),
    ("Web page.html", "HTML page", "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n  <title>Untitled</title>\n</head>\n<body>\n\n</body>\n</html>\n"),
    ("Spreadsheet.csv", "CSV table", "Column A,Column B\n"),
    ("Desktop launcher.desktop", "App launcher", "[Desktop Entry]\nType=Application\nName=My App\nExec=\nIcon=application-x-executable\nTerminal=false\n"),
]

SCRIPTS = [
    ("Open terminal here", "Open a terminal in the selected folder.",
     '#!/bin/bash\ndir="${1:-$PWD}"\n[ -d "$dir" ] || dir="$(dirname "$dir")"\ncd "$dir" && exec x-terminal-emulator\n'),
    ("Copy full path", "Copy the path of the selected files to the clipboard.",
     '#!/bin/bash\npaths=""\nfor f in "$@"; do paths+="$(readlink -f "$f")"$\'\\n\'; done\nprintf "%s" "${paths%$\'\\n\'}" | '
     '(wl-copy 2>/dev/null || xclip -selection clipboard 2>/dev/null || xsel -b 2>/dev/null)\n'),
    ("SHA-256 checksum", "Show SHA-256 checksums of the selected files.",
     '#!/bin/bash\nout=$(sha256sum -- "$@" 2>&1)\n(zenity --info --title=SHA-256 --text="$out" 2>/dev/null || notify-send "SHA-256" "$out")\n'),
    ("Make executable", "Allow the selected files to run as programs.", '#!/bin/bash\nchmod +x -- "$@"\n'),
    ("Compress to ZIP", "Create a .zip archive of the selection.",
     '#!/bin/bash\nname="$(basename "$1").zip"\n[ $# -gt 1 ] && name="archive-$(date +%Y%m%d-%H%M%S).zip"\nzip -r -- "$name" "$@"\n'),
    ("Convert images to PNG", "Convert selected images with ImageMagick.",
     '#!/bin/bash\nfor f in "$@"; do convert -- "$f" "${f%.*}.png"; done\n'),
]


def templates_dir():
    code, text = run(["xdg-user-dir", "TEMPLATES"], timeout=5)
    path = text.strip()
    home = os.path.expanduser("~")
    if not path or os.path.realpath(path) == os.path.realpath(home):
        path = os.path.join(home, "Templates")
    return path


def script_dirs():
    home = os.path.expanduser("~")
    dirs = []
    if shutil.which("nautilus"):
        dirs.append(("Files (Nautilus)", os.path.join(home, ".local/share/nautilus/scripts")))
    if shutil.which("nemo"):
        dirs.append(("Nemo", os.path.join(home, ".local/share/nemo/scripts")))
    if shutil.which("caja"):
        dirs.append(("Caja", os.path.join(home, ".config/caja/scripts")))
    return dirs
