import os
import re
import tempfile

from gi.repository import Gtk

from .. import APP_NAME, VERSION, widgets as W
from ..core import catalog, sources
from ..core.tasks import Task
from ..core.util import run, shq
from ..i18n import _
from .base import Page
from .updates import MIRRORS, official_style

FASTTRACK_URI = "https://fasttrack.debian.net/debian-fasttrack/"


def gpg_keys(path):
    with tempfile.TemporaryDirectory() as home:
        code, text = run(["gpg", "--homedir", home, "--batch", "--show-keys", "--with-colons", path], timeout=15)
    return sources.parse_gpg_colons(text)


def key_state(key):
    import time
    exp = key.get("expires")
    if key.get("validity") == "r":
        return "revoked", "err"
    if exp and exp.isdigit() and int(exp) < time.time():
        return "expired", "err"
    if exp and exp.isdigit():
        days = (int(exp) - time.time()) / 86400
        if days < 60:
            return f"expires in {int(days)} days", "warn"
        return "valid until " + time.strftime("%Y-%m-%d", time.localtime(int(exp))), "ok"
    return "valid, no expiry", "ok"


class Repositories(Page):
    ID = "repositories"
    TITLE = "Repositories"
    SUBTITLE = "Official, backports, extrepo and third-party repositories"
    ICON = "network-server-symbolic"
    KEYWORDS = "repository repo extrepo backports fasttrack gpg key apt sources doctor non-free contrib mirror third-party ppa"

    def build(self):
        self.add_action(W.button("Repository Doctor", "emblem-system-symbolic", "primary", self.doctor))
        self.seg = W.Segmented([("official", "Official Debian"), ("extrepo", "Third-party (extrepo)"), ("other", "Other sources"),
                                ("keys", "GPG keys"), ("doctor", "Problems")], self._tab)
        self.seg.set_halign(Gtk.Align.START)
        self.content.append(self.seg)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content.append(self.stack)
        self.tabs = {}
        for key in ("official", "extrepo", "other", "keys", "doctor"):
            box = W.vbox(16)
            self.stack.add_named(box, key)
            self.tabs[key] = box
        self.current_tab = "official"

    def _tab(self, key):
        self.current_tab = key
        self.stack.set_visible_child_name(key)
        if self.loaded:
            self.refresh_tab(key)

    def refresh(self):
        self.refresh_tab(self.current_tab)

    def refresh_tab(self, key):
        getattr(self, "_fill_" + key)(self.tabs[key])

    # -------------------------------------------------------------- official
    def _fill_official(self, box):
        W.clear(box)
        r = self.win.release
        style = official_style()
        ents = sources.parse_all()
        card = W.Card("Debian archive components",
                      "main is always enabled. contrib and non-free contain software with non-free dependencies or licenses; "
                      "non-free-firmware contains firmware for Wi-Fi, GPUs and CPU microcode.")
        box.append(card)
        for comp, desc in (("contrib", "Free software that depends on non-free parts (e.g. Steam installer, MS fonts installer)."),
                           ("non-free", "Software with non-free licenses (e.g. NVIDIA driver, unrar)."),
                           ("non-free-firmware", "Firmware blobs (Wi-Fi, GPU, CPU microcode) - recommended.")):
            card.add(W.switch_row(comp, desc, comp in style["components"],
                                  lambda on, c=comp: self._component(c, on), last=comp == "non-free-firmware"))
        extra = W.Card("Extra Debian repositories")
        box.append(extra)
        has = lambda pred: any(e.enabled and pred(e) for e in ents)
        if r["branch"] in ("stable", "oldstable"):
            extra.add(W.switch_row("Backports", f"Newer software rebuilt for Debian {r['debian_codename']} ({r['debian_codename']}-backports). "
                                                "Only installed when you ask for it.",
                                   has(lambda e: any(s.endswith("-backports") for s in e.suites)), self._backports))
            extra.add(W.switch_row("Fasttrack", "Debian Fasttrack: VirtualBox, GitLab and other fast-moving software for Stable.",
                                   has(lambda e: "fasttrack.debian.net" in e.uri), self._fasttrack))
        if r["branch"] == "sid":
            extra.add(W.switch_row("Experimental", "Pre-release packages. Never installed unless you request them with -t experimental.",
                                   has(lambda e: "experimental" in e.suites), self._experimental))
        extra.add(W.switch_row("Source packages (deb-src)", "Needed for apt source and building packages.", style["deb_src"],
                               self._debsrc, last=True))
        mcard = W.Card("Mirror", "deb.debian.org automatically picks a fast server near you.")
        box.append(mcard)
        row = W.hbox(10)
        known = [m for m, _l in MIRRORS]
        opts = MIRRORS if style["mirror"] in known else [(style["mirror"], style["mirror"] + " (current)")] + MIRRORS
        self.mirror_dd = W.dropdown(opts, style["mirror"])
        self.mirror_dd.set_hexpand(True)
        row.append(self.mirror_dd)
        row.append(W.button(_("Apply"), kind="primary", on_click=self._apply_mirror))
        mcard.add(row)
        mcard.add(W.label("The current entries are rewritten as a single deb822 file (debian.sources) - see Updates & Release.", "dim", wrap=True))

    def _component(self, comp, on):
        self.win.run(Task(f"{'Enable' if on else 'Disable'} {comp}", [
            ("Backing up APT configuration", "backup_apt_sources"),
            (f"{'Enabling' if on else 'Disabling'} {comp}", f"debos_helper set-component {shq(comp)} {'on' if on else 'off'}"),
            ("Refreshing package lists", "apt_update")], refresh={"sources", "packages"}))

    def _extra_repo(self, name, on, text, title):
        steps = [("Backing up APT configuration", "backup_apt_sources")]
        if on:
            steps.append((f"Enabling {title}", [f"debos_helper set-extra {name} on <<'DEBOS_EOF'", text.rstrip("\n"), "DEBOS_EOF"]))
        else:
            steps.append((f"Disabling {title}", f"debos_helper set-extra {name} off"))
        steps.append(("Refreshing package lists", "apt_update"))
        return steps

    def _backports(self, on):
        c = self.win.release["debian_codename"]
        if not on:
            # remove our file and disable backports entries written elsewhere
            steps = self._extra_repo("debos-backports", False, None, "backports")
            for e in sources.parse_all():
                if e.enabled and any(s.endswith("-backports") for s in e.suites) and e.is_official_debian() and \
                        not e.file.endswith("debos-backports.sources"):
                    steps.insert(-1, (f"Disabling {os.path.basename(e.file)}", f"debos_helper set-entry {shq(e.file)} {e.index} disable"))
            self.win.run(Task("Disable backports", steps, refresh={"sources", "packages"}))
            return
        text = sources.render_deb822(["deb"], [sources.DEBIAN_MIRROR], [f"{c}-backports"],
                                     ["main", "contrib", "non-free", "non-free-firmware"], sources.DEBIAN_KEYRING,
                                     comment=f"Debian {c}-backports - added by {APP_NAME}")
        self.win.run(Task("Enable backports", self._extra_repo("debos-backports", True, text, "backports"), refresh={"sources", "packages"}))

    def _fasttrack(self, on):
        c = self.win.release["debian_codename"]
        if not on:
            self.win.run(Task("Disable Fasttrack", self._extra_repo("debos-fasttrack", False, None, "Fasttrack"), refresh={"sources"}))
            return
        text = (f"# Debian Fasttrack - added by {APP_NAME}\nTypes: deb\nURIs: {FASTTRACK_URI}\n"
                f"Suites: {c}-fasttrack {c}-backports-staging\nComponents: main contrib\n")
        steps = [("Installing the Fasttrack keyring", "apt_install fasttrack-archive-keyring")] + \
            self._extra_repo("debos-fasttrack", True, text, "Fasttrack")
        self.win.run(Task("Enable Fasttrack", steps, refresh={"sources", "packages"}))

    def _experimental(self, on):
        text = sources.render_deb822(["deb"], [sources.DEBIAN_MIRROR], ["experimental"], ["main", "contrib", "non-free", "non-free-firmware"],
                                     sources.DEBIAN_KEYRING, comment="Debian experimental (never installed automatically)")
        self.win.run(Task(("Enable" if on else "Disable") + " experimental", self._extra_repo("debos-experimental", on, text, "experimental"),
                          refresh={"sources"}))

    def _debsrc(self, on):
        page = self.win.pages["updates"]
        page.ensure_built()
        page.opt_src.switch.set_active(on)
        self._write_official(page)

    def _apply_mirror(self):
        if not hasattr(self, "mirror_dd"):
            return
        page = self.win.pages["updates"]
        page.ensure_built()
        mirror = W.dd_value(self.mirror_dd)
        keys = page.mirror.keys
        if mirror not in keys:
            return
        page.mirror.set_selected(keys.index(mirror))
        self._write_official(page)

    def _write_official(self, page):
        text = page.generated()
        self.win.run(Task("Rewrite official Debian sources", [
            ("Backing up APT configuration", "backup_apt_sources"),
            ("Writing debian.sources", ["debos_helper write-official <<'DEBOS_EOF'", text.rstrip("\n"), "DEBOS_EOF"]),
            ("Refreshing package lists", "apt_update")], refresh={"sources", "packages"}), confirm="The official entries will be rewritten as:\n\n" + text)

    # -------------------------------------------------------------- extrepo
    def _fill_extrepo(self, box):
        W.clear(box)
        if not os.path.exists("/usr/bin/extrepo"):
            card = W.Card("extrepo is not installed",
                          "extrepo is Debian's own tool for adding third-party repositories (Brave, Chrome, VS Code, Docker, Spotify, "
                          "Signal, Steam, Liquorix, TeamViewer, Syncthing and more) with verified keys and the right suites for your release.")
            card.add(W.button("Install extrepo", "system-software-install-symbolic", "primary",
                              lambda: self.win.run(Task("Install extrepo", [("Installing", "apt_install extrepo")], refresh={"extrepo", "packages"}))))
            box.append(card)
            return
        top = W.hbox(10)
        self.ex_search = W.search_entry("Filter repositories")
        self.ex_search.set_hexpand(True)
        top.append(self.ex_search)
        top.append(W.label("Non-free repositories need the matching extrepo policy; Debos enables it automatically.", "dim", wrap=True))
        box.append(top)
        self.ex_list = W.Card()
        box.append(self.ex_list)
        self.loading(self.ex_list.body, "Downloading the extrepo index…")
        self.ex_search.connect("search-changed", lambda *_a: self._render_extrepo())
        self.win.data.get("extrepo", catalog.extrepo_list, self._got_extrepo)

    def _got_extrepo(self, repos):
        self.ex_repos = repos if isinstance(repos, dict) else {}
        self._render_extrepo()

    def _render_extrepo(self):
        body = self.ex_list.body
        W.clear(body)
        repos = getattr(self, "ex_repos", {})
        if not repos:
            body.append(W.empty_state("network-offline-symbolic", "No repositories found",
                                      "extrepo could not download its index. Check your internet connection."))
            return
        q = self.ex_search.get_text().strip().lower() if hasattr(self, "ex_search") else ""
        state = {}
        for e in sources.parse_all():
            m = re.match(r".*/extrepo_(.+)\.sources$", e.file)
            if m:
                state[m.group(1)] = e.enabled
        shown = [r for r in sorted(repos.values(), key=lambda r: (r["name"] not in state, r["name"]))
                 if not q or q in r["name"].lower() or q in r["description"].lower()]
        for i, r in enumerate(shown[:300]):
            badges = [(r["policy"], "warn" if r["policy"] != "main" else "muted")]
            if r["name"] in state:
                badges.append(("enabled" if state[r["name"]] else "disabled", "ok" if state[r["name"]] else "muted"))
            row = W.switch_row(r["name"], r["description"] or " ", state.get(r["name"], False),
                               lambda on, rr=r: self._extrepo_toggle(rr, on), last=i == len(shown) - 1)
            for text, kind in badges:
                b = W.badge(text, kind)
                b.set_valign(Gtk.Align.CENTER)
                row.insert_child_after(b, row.get_first_child())
            body.append(row)

    def _extrepo_toggle(self, repo, on):
        name = shq(repo["name"])
        if on:
            steps = [("Enabling " + repo["name"], f"extrepo_enable {name} {shq(repo['policy'])}"), ("Refreshing package lists", "apt_update")]
        else:
            steps = [("Disabling " + repo["name"], f"extrepo disable {name}"), ("Refreshing package lists", "apt_update")]
        self.win.run(Task(("Enable " if on else "Disable ") + repo["name"], steps, refresh={"sources", "packages"}))

    # -------------------------------------------------------------- other
    def _fill_other(self, box):
        W.clear(box)
        ents = [e for e in sources.parse_all() if not e.is_official_debian() and not e.is_cdrom()]
        head = W.hbox(10)
        head.append(W.label("Repositories that are not part of Debian. Disabled entries stay in the file and can be re-enabled.", "dim", wrap=True))
        head.append(W.spacer())
        head.append(W.button("Add repository", "list-add-symbolic", "primary", self._add_dialog))
        box.append(head)
        card = W.Card()
        box.append(card)
        if not ents:
            card.add(W.empty_state("network-server-symbolic", "No third-party repositories", "Only official Debian sources are configured."))
            return
        for i, e in enumerate(ents):
            sb = e.signed_by
            key_ok = not sb or not sb.startswith("/") or os.path.exists(sb)
            badges = [(e.fmt, "muted"), ("key ok" if sb and key_ok else ("key missing" if sb else "global key"),
                                         "ok" if sb and key_ok else ("err" if sb else "warn"))]
            sub = f"{e.uri}  ·  {' '.join(e.suites)} {' '.join(e.components)}\n{e.file}"
            row = W.switch_row(e.host or e.uri, sub, e.enabled, lambda on, en=e: self._entry(en, "enable" if on else "disable"),
                               last=i == len(ents) - 1)
            rm = W.icon_button("user-trash-symbolic", "Remove this entry", lambda en=e: self._remove(en))
            rm.set_valign(Gtk.Align.CENTER)
            row.append(rm)
            for text, kind in badges:
                b = W.badge(text, kind)
                b.set_valign(Gtk.Align.CENTER)
                row.insert_child_after(b, row.get_first_child())
            card.add(row)

    def _entry(self, e, action):
        self.win.run(Task(f"{action.capitalize()} {e.host or e.uri}", [
            ("Backing up APT configuration", "backup_apt_sources"),
            (f"{action.capitalize()} entry", f"debos_helper set-entry {shq(e.file)} {e.index} {action}"),
            ("Refreshing package lists", "apt_update")], refresh={"sources", "packages"}))

    def _remove(self, e):
        self.win.confirm("Remove repository?", f"{e.label()}\n\nA backup is kept in /var/backups/debos-toolbox.",
                         lambda: self._entry(e, "remove"), "Remove", danger=True)

    def _add_dialog(self):
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(10)
        fields = {}
        for i, (key, label, ph) in enumerate((("name", "Name", "my-repo"), ("uri", "URI", "https://example.com/debian"),
                                              ("suites", "Suites", "stable  (or $VENDOR_CODENAME)"), ("components", "Components", "main"),
                                              ("key", "Key URL", "https://example.com/key.gpg"))):
            grid.attach(W.label(label, "row-title"), 0, i, 1, 1)
            ent = Gtk.Entry()
            ent.set_placeholder_text(ph)
            ent.set_hexpand(True)
            grid.attach(ent, 1, i, 1, 1)
            fields[key] = ent
        fields["components"].set_text("main")

        def ok():
            v = {k: e.get_text().strip() for k, e in fields.items()}
            name = re.sub(r"[^a-z0-9-]", "-", v["name"].lower()).strip("-")
            if not name or not re.match(r"^https?://\S+$", v["uri"]) or not v["suites"] or not v["key"].startswith("https://"):
                self.win.toast("Name, http(s) URI, suites and an https key URL are required.", "err")
                return
            keyfile = f"/etc/apt/keyrings/{name}.gpg"
            text = sources.render_deb822(["deb"], [v["uri"]], v["suites"].split(), (v["components"] or "main").split(), keyfile,
                                         comment=f"Added with {APP_NAME} {VERSION}")
            self.win.run(Task(f"Add repository {name}", [
                ("Importing the signing key", f"debos_helper key-import {shq(name)} {shq(v['key'])}"),
                ("Writing the repository", [f"write_source {shq(name)} <<'DEBOS_EOF'", text.rstrip("\n"), "DEBOS_EOF"]),
                ("Refreshing package lists", "apt_update")], refresh={"sources", "packages"}))
        W.Dialog(self.win, "Add a repository", "The key is stored in /etc/apt/keyrings and referenced with Signed-By, "
                 "so it only applies to this repository.", extra=grid, buttons=(("Cancel", "", None), ("Add", "primary", ok))).present()

    # ---------------------------------------------------------------- keys
    def _fill_keys(self, box):
        W.clear(box)
        card = W.Card("Repository signing keys", "Keys found in /etc/apt/keyrings, trusted.gpg.d, /usr/share/keyrings and extrepo.")
        box.append(card)
        self.loading(card.body, "Reading keys…")
        self.win.async_call(self._load_keys, lambda res: self._show_keys(card, res))

    def _load_keys(self):
        ents = [e for e in sources.parse_all() if e.enabled]
        used = {}
        for e in ents:
            if e.signed_by.startswith("/"):
                used.setdefault(os.path.realpath(e.signed_by), []).append(e)
        res = []
        for path in sources.keyring_files():
            if path.startswith("/usr/share/keyrings/") and os.path.realpath(path) not in used:
                continue  # package-owned keyrings that nothing references are not interesting
            res.append((path, gpg_keys(path), used.get(os.path.realpath(path), [])))
        return res

    def _show_keys(self, card, res):
        W.clear(card.body)
        if isinstance(res, Exception):
            card.add(W.label(str(res), "err-text"))
            return
        legacy = [r for r in res if r[0] == sources.LEGACY_KEYRING]
        if legacy:
            card.add(W.action_row("Legacy keyring /etc/apt/trusted.gpg", "Deprecated since Debian 11: apt prints warnings for every repository using it.",
                                  [W.button("Migrate", kind="primary", small=True, on_click=lambda: self.win.run(Task(
                                      "Migrate repository keys", [("Migrating", "debos_helper migrate-keys"), ("Refresh", "apt_update")],
                                      refresh={"sources"})))], "dialog-warning-symbolic", "warning"))
        for i, (path, keys, users) in enumerate(res):
            states = [key_state(k) for k in keys] or [("unreadable", "err")]
            worst = next((s for s in states if s[1] == "err"), states[0])
            uid = ", ".join(k["uid"] for k in keys if k["uid"])[:110] or "(no user id)"
            used_by = ", ".join(sorted({u.host or os.path.basename(u.file) for u in users})) or "not referenced (global trust)" \
                if not path.startswith(("/etc/apt/keyrings/", "/var/lib/extrepo/")) else \
                (", ".join(sorted({u.host or os.path.basename(u.file) for u in users})) or "unused")
            buttons = []
            if users and worst[1] == "err":
                u = users[0]
                buttons.append(W.button("Refresh key", kind="primary", small=True, on_click=lambda e=u: self.win.run(Task(
                    "Refresh repository key", [("Refreshing", f"debos_helper repair-key {shq(e.file)} {e.index}"), ("Refresh", "apt_update")],
                    refresh={"sources"}))))
            if not users and path.startswith(("/etc/apt/keyrings/",)):
                buttons.append(W.button(_("Remove"), kind="danger", small=True, on_click=lambda p=path: self.win.run(Task(
                    "Remove unused key", [("Removing", f"debos_helper key-remove {shq(p)}")], refresh={"sources"}))))
            card.add(W.action_row(os.path.basename(path), f"{uid}\n{path} · used by: {used_by}", buttons,
                                  "dialog-password-symbolic", "info" if worst[1] == "ok" else ("warning" if worst[1] == "warn" else "critical"),
                                  last=i == len(res) - 1, title_badges=[(worst[0], worst[1])]))

    # --------------------------------------------------------------- doctor
    def _fill_doctor(self, box):
        W.clear(box)
        r = self.win.release
        issues = sources.entry_issues(sources.parse_all(), r.get("debian_codename"), r.get("branch"))
        if os.path.isfile(sources.LEGACY_KEYRING) and os.path.getsize(sources.LEGACY_KEYRING) > 0:
            issues.append({"id": "legacy", "severity": "warning", "title": "Keys in the deprecated /etc/apt/trusted.gpg",
                           "detail": "Migrating them removes the 'legacy trusted.gpg keyring' warnings.", "entries": []})
        card = W.Card("Repository Doctor",
                      "Static checks run instantly. 'Run Repository Doctor' also runs apt-get update and repairs what it reports: "
                      "missing or expired keys (NO_PUBKEY / EXPKEYSIG), duplicate and conflicting entries, CD/DVD entries, dead "
                      "repositories, wrong architectures, release-info changes after a Debian release and the legacy keyring.",
                      W.button("Run Repository Doctor", "emblem-system-symbolic", "primary", self.doctor))
        box.append(card)
        if not issues:
            card.add(W.empty_state("object-select-symbolic", "No problems found in the APT configuration"))
            return
        icon = {"error": ("dialog-error-symbolic", "critical"), "warning": ("dialog-warning-symbolic", "warning"),
                "info": ("dialog-information-symbolic", "info")}
        for i, issue in enumerate(issues):
            ic, css = icon.get(issue["severity"], icon["info"])
            where = "\n".join(e.label() for e in issue["entries"][:4])
            card.add(W.action_row(issue["title"], issue["detail"] + (f"\n{where}" if where else ""), [], ic, css,
                                  last=i == len(issues) - 1))

    def doctor(self):
        self.win.run(Task("Repository Doctor", [("Backing up APT configuration", "backup_apt_sources"),
                                                ("Repository Doctor", "debos_helper doctor")], refresh={"sources", "packages"}))
