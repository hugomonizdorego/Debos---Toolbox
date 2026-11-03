from .. import widgets as W
from ..core import catalog
from ..core.tasks import Task
from ..i18n import _
from .base import Page


def commands(win):
    dash = lambda: win.pages["dashboard"]
    return [
        ("update upgrade system", "Update the system", "software-update-available-symbolic", lambda: (dash().ensure_built(), dash().update_system())),
        ("fix repair broken dpkg packages", "Repair broken packages", "emblem-system-symbolic", lambda: (dash().ensure_built(), dash().fix_packages())),
        ("repository doctor gpg key no_pubkey fix repo", "Run the Repository Doctor", "network-server-symbolic",
         lambda: win.run(Task("Repository Doctor", [("Repository Doctor", "debos_helper doctor")], refresh={"sources", "packages"}))),
        ("clean junk cache space", "Scan for junk files", "user-trash-symbolic", lambda: win.navigate("cleaner")),
        ("apt update refresh lists", "Refresh package lists (apt update)", "view-refresh-symbolic",
         lambda: win.run(Task("Refresh package lists", [("apt-get update", "apt_update")], refresh={"packages", "sources"}))),
        ("dark light theme mode", "Toggle dark mode", "weather-clear-night-symbolic", win.toggle_theme),
        ("console terminal log", "Show the console", "utilities-terminal-symbolic", lambda: win.show_console(True)),
        ("reboot restart", "Restart the computer", "system-reboot-symbolic", lambda: (dash().ensure_built(), dash().reboot())),
    ]


class Search(Page):
    ID = "search"
    TITLE = "Search"
    SUBTITLE = "Pages, apps, settings and commands"
    ICON = "system-search-symbolic"

    def build(self):
        self.results = W.vbox(16)
        self.content.append(self.results)
        self.first = None

    def search(self, text):
        self.ensure_built()
        q = text.lower().strip()
        W.clear(self.results)
        self.first = None
        from .registry import PAGES
        pages = [(pid, cls) for pid, cls in PAGES.items() if pid != "search" and
                 (q in _(cls.TITLE).lower() or q in cls.TITLE.lower() or q in cls.KEYWORDS or q in _(cls.SUBTITLE).lower())]
        cmds = [c for c in commands(self.win) if q in c[0] or q in c[1].lower()]
        apps = [a for a in catalog.APPS if q in (a["name"] + " " + a["summary"] + " " + a["id"]).lower()]
        if cmds:
            card = W.Card("Commands")
            for i, (_k, title, icon, cb) in enumerate(cmds):
                card.add(W.action_row(title, None, [W.button(_("Run"), kind="primary", small=True, on_click=cb)], icon, "tip", last=i == len(cmds) - 1))
                self.first = self.first or cb
            self.results.append(card)
        if pages:
            card = W.Card("Pages")
            for i, (pid, cls) in enumerate(pages):
                cb = (lambda p=pid: self.win.navigate(p))
                card.add(W.action_row(_(cls.TITLE), _(cls.SUBTITLE), [W.button(_("Open"), small=True, on_click=cb)], cls.ICON, "info",
                                      last=i == len(pages) - 1))
                self.first = self.first or cb
            self.results.append(card)
        if apps:
            card = W.Card("Apps")
            for i, a in enumerate(apps[:20]):
                cb = (lambda app=a: self._open_app(app))
                card.add(W.action_row(a["name"], a["summary"], [W.button(_("Details"), small=True, on_click=cb)], a["glyph"], "info",
                                      last=i == min(19, len(apps) - 1)))
                self.first = self.first or cb
            self.results.append(card)
        more = W.Card(f"Search all Debian packages for '{text}'", "Press Enter in the Software Center filter, or click here.",
                      W.button(_("Search"), kind="primary", on_click=lambda: self._search_debian(text)))
        self.results.append(more)
        if not (cmds or pages or apps):
            self.results.prepend(W.empty_state("system-search-symbolic", f"Nothing found for '{text}'"))
            self.first = lambda: self._search_debian(text)

    def activate_first(self):
        if self.first:
            self.first()

    def _open_app(self, app):
        sw = self.win.pages["software"]
        self.win.search.set_text("")
        self.win.navigate("software")
        if sw.state:
            sw.details(app)
        else:
            self.win.data.get("software", __import__("debos.pages.software", fromlist=["x"]).load_software_state,
                              lambda st: (setattr(sw, "state", st), sw.details(app)))

    def _search_debian(self, text):
        sw = self.win.pages["software"]
        self.win.search.set_text("")
        self.win.navigate("software")
        sw.filter.set_text(text)
        sw.search_everything(text)
