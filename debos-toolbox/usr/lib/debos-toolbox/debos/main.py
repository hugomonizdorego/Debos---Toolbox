"""Command-line entry point."""

import os
import shutil
import subprocess
import sys

from . import APP_NAME, BUILD, VERSION

USAGE = f"""{APP_NAME} {VERSION}

Usage: debos-toolbox [OPTION]

  --page NAME   open a page directly (dashboard, recommendations, cleaner, updates, repositories,
                sources, software, uninstall, desktops, kernels, drivers, network, systemtweaks,
                desktoptweaks, startup, defaultapps, templates, customizer, about)
  --startup     run the background health check and exit (used by the login monitor)
  --version     print the version and exit
  --help        show this help
"""


def health_check():
    """Notify about broken packages, pending updates and low disk space (no GTK needed)."""
    from .core import apt
    from .core.util import human_size

    def notify(urgency, msg):
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "-u", urgency, "-i", "debos-toolbox", "-a", APP_NAME, APP_NAME, msg])
        else:
            print(msg)

    if apt.broken():
        notify("critical", "Some packages are not fully installed. Open Debos - Toolbox > Recommendations to repair them.")
    items, _ok = apt.simulate_upgrade(True)
    if items:
        sec = sum(1 for i in items if i["security"])
        notify("normal", f"{len(items)} update(s) available" + (f", {sec} security" if sec else "") + ". Open Debos - Toolbox > Updates.")
    usage = shutil.disk_usage("/")
    if usage.free < 2 * 1024 ** 3:
        notify("critical", f"Low disk space on / ({human_size(usage.free)} free). Open Debos - Toolbox > Cleaner.")
    return 0


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    args = argv[1:]
    if "--help" in args or "-h" in args:
        print(USAGE)
        return 0
    if "--version" in args or "-v" in args:
        print(f"{APP_NAME} {VERSION} (build {BUILD})")
        return 0
    if "--startup" in args:
        return health_check()
    page = "dashboard"
    if "--page" in args:
        i = args.index("--page")
        if i + 1 < len(args):
            page = args[i + 1]
    if os.geteuid() == 0 and not os.environ.get("DEBOS_ALLOW_ROOT"):
        print("Please start Debos - Toolbox as your normal user; it asks for the administrator password when needed.", file=sys.stderr)
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
        Gtk.get_major_version()
    except (ImportError, ValueError) as exc:
        print(f"{APP_NAME} needs GTK 4 for Python: sudo apt install python3-gi gir1.2-gtk-4.0 python3-gi-cairo ({exc})", file=sys.stderr)
        return 1
    from gi.repository import GLib
    GLib.set_prgname("debos-toolbox")
    from .app import DebosApp
    app = DebosApp(page)
    return app.run([argv[0]])
