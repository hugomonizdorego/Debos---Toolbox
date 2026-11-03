from gi.repository import Gtk

from .. import theme, widgets as W
from ..core import recommend
from ..core.tasks import Task
from ..i18n import _
from .base import Page

SEV_ICON = {"critical": "dialog-error-symbolic", "warning": "dialog-warning-symbolic", "info": "dialog-information-symbolic",
            "tip": "starred-symbolic"}
SEV_LABEL = {"critical": ("Critical", "err"), "warning": ("Warning", "warn"), "info": ("Info", "info"), "tip": ("Tip", "ok")}


def run_recommendation(win, rec):
    action = rec["action"]
    if action[0] == "page":
        win.navigate(action[1])
        return
    _kind, title, steps, root = action
    win.run(Task(title, steps, root=root, refresh={"packages", "sources", "kernels", "cleaner", "tweaks"}),
            confirm=rec["detail"])


def rec_row(win, rec, last=False, on_ignore=None):
    text, kind = SEV_LABEL.get(rec["severity"], ("Info", "info"))
    buttons = [W.button(_(rec.get("label", "Fix")), kind="primary" if rec["action"][0] == "task" else "", small=True,
                        on_click=lambda r=rec: run_recommendation(win, r))]
    if on_ignore:
        buttons.insert(0, W.button(_("Ignore"), kind="ghost", small=True, on_click=lambda r=rec: on_ignore(r)))
    return W.action_row(rec["title"], rec["detail"], buttons, SEV_ICON.get(rec["severity"]), rec["severity"], last=last,
                        title_badges=[(text, kind)])


class Recommendations(Page):
    ID = "recommendations"
    TITLE = "Recommendations"
    SUBTITLE = "Smart suggestions to keep Debian healthy"
    ICON = "starred-symbolic"
    KEYWORDS = "health suggestions advice fix problems check"

    def build(self):
        self.add_action(W.button(_("Scan"), "view-refresh-symbolic", "", self.rescan))
        self.fix_all_btn = self.add_action(W.button(_("Fix all") + " (safe)", "object-select-symbolic", "primary", self.fix_all))
        top = W.hbox(16)
        self.content.append(top)
        pal = theme.PALETTES[theme.resolve_mode(self.win.settings.get("theme"))]
        score_card = W.Card(css="card neu")
        self.donut = W.Donut(150, "green", 0, None, track=pal["surface3"], text_color=pal["text"])
        self.donut.set_halign(Gtk.Align.CENTER)
        score_card.add(self.donut)
        score_card.add(W.label(_("Health score"), "card-title", xalign=0.5))
        score_card.set_size_request(220, -1)
        top.append(score_card)
        self.summary = W.Card("Summary")
        self.summary.set_hexpand(True)
        top.append(self.summary)
        self.list_box = W.vbox(16)
        self.content.append(self.list_box)
        self.show_ignored = False

    def rescan(self):
        self.win.data.invalidate({"all"})
        self.refresh()

    def refresh(self):
        self.loading(self.list_box, "Checking your system (packages, repositories, kernels, drivers, services)…")
        from .dashboard import load_recommendations
        self.win.data.get("recommendations", lambda: load_recommendations(self.win), self._fill)

    def _fill(self, recs):
        W.clear(self.list_box)
        if isinstance(recs, Exception):
            self.list_box.append(W.empty_state("dialog-error-symbolic", "The scan failed", str(recs)))
            return
        ignored = set(self.win.settings.get("ignored_recommendations") or [])
        active = [r for r in recs if r["id"] not in ignored]
        hidden = [r for r in recs if r["id"] in ignored]
        self.recs = active
        score = recommend.health_score(active)
        self.donut.set_value(score, color="green" if score >= 80 else ("amber" if score >= 55 else "red"))
        self.win.set_nav_count("recommendations", len([r for r in active if r["severity"] in ("critical", "warning")]))
        W.clear(self.summary.body)
        counts = {s: sum(1 for r in active if r["severity"] == s) for s in ("critical", "warning", "info", "tip")}
        row = W.hbox(10)
        for sev, n in counts.items():
            text, kind = SEV_LABEL[sev]
            row.append(W.badge(f"{n} {text}", kind if n else "muted"))
        self.summary.add(row)
        safe = [r for r in active if r.get("safe") and r["action"][0] == "task"]
        self.fix_all_btn.set_sensitive(bool(safe))
        self.summary.add(W.label(
            "Recommendations come from checks of your packages, repositories and keys, kernels, drivers and firmware, "
            "services, disk space and Debian best practices for your branch. 'Fix all' only runs the safe repairs: "
            f"{len(safe)} available.", "dim", wrap=True))
        if not active:
            self.list_box.append(W.empty_state("object-select-symbolic", _("Everything looks good"),
                                               "No problems were found. Check again after installing updates or new software."))
        for sev in ("critical", "warning", "info", "tip"):
            items = [r for r in active if r["severity"] == sev]
            if not items:
                continue
            card = W.Card({"critical": "Needs attention now", "warning": "Recommended", "info": "Good to know",
                           "tip": "Tips"}[sev])
            for i, r in enumerate(items):
                card.add(rec_row(self.win, r, last=i == len(items) - 1, on_ignore=self.ignore))
            self.list_box.append(card)
        if hidden:
            card = W.Card(f"Ignored ({len(hidden)})", "Suggestions you chose to hide.",
                          W.button("Restore all", kind="ghost", on_click=self.restore))
            for i, r in enumerate(hidden):
                card.add(W.action_row(r["title"], r["detail"], [], SEV_ICON.get(r["severity"]), r["severity"], last=i == len(hidden) - 1))
            self.list_box.append(card)

    def ignore(self, rec):
        ignored = list(self.win.settings.get("ignored_recommendations") or [])
        if rec["id"] not in ignored:
            ignored.append(rec["id"])
        self.win.settings.set("ignored_recommendations", ignored)
        self.win.data.get("recommendations", lambda: [], self._fill)

    def restore(self):
        self.win.settings.set("ignored_recommendations", [])
        self.win.data.get("recommendations", lambda: [], self._fill)

    def fix_all(self):
        safe = [r for r in getattr(self, "recs", []) if r.get("safe") and r["action"][0] == "task"]
        if not safe:
            return
        steps = []
        for r in safe:
            steps += r["action"][2]
        self.win.run(Task("Fix recommendations", steps, refresh={"packages", "sources", "kernels", "cleaner"}),
                     confirm="These safe repairs will run:\n• " + "\n• ".join(r["title"] for r in safe))
