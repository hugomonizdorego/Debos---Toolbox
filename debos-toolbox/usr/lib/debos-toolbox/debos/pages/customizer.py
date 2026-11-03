import glob
import os
import re

from gi.repository import Gtk

from .. import widgets as W
from ..core import system
from ..core.tasks import Task
from ..core.util import read_file, shq
from .base import Page
from .desktoptweaks import pick_file

PLYMOUTH_SCRIPT = r'''wallpaper_image = Image("background.png");
screen_width = Window.GetWidth();
screen_height = Window.GetHeight();
wallpaper_sprite = Sprite(wallpaper_image.Scale(screen_width, screen_height));
wallpaper_sprite.SetZ(-100);
message_sprite = Sprite();
message_sprite.SetPosition(screen_width * 0.1, screen_height * 0.85, 10000);
fun password_callback(prompt, bullets) {
    text = prompt + "  ";
    for (i = 0; i < bullets; i++) text = text + "*";
    message_sprite.SetImage(Image.Text(text, 1, 1, 1));
}
Plymouth.SetDisplayPasswordFunction(password_callback);
fun question_callback(prompt, entry) {
    message_sprite.SetImage(Image.Text(prompt + "  " + entry, 1, 1, 1));
}
Plymouth.SetDisplayQuestionFunction(question_callback);
fun normal_callback() {
    message_sprite.SetImage(Image.Text("", 1, 1, 1));
}
Plymouth.SetDisplayNormalFunction(normal_callback);
fun message_callback(text) {
    message_sprite.SetImage(Image.Text(text, 1, 1, 1));
}
Plymouth.SetMessageFunction(message_callback);
'''

COLORS = ["black", "blue", "green", "cyan", "red", "magenta", "brown", "light-gray", "dark-gray", "light-blue", "light-green",
          "light-cyan", "light-red", "light-magenta", "yellow", "white"]


def read_grub():
    vals = {}
    for line in read_file("/etc/default/grub").splitlines():
        m = re.match(r"^\s*(GRUB_[A-Z_]+)=(.*)$", line)
        if m:
            vals[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return vals


def set_key(key, value):
    return (f"if grep -qE '^#?{key}=' /etc/default/grub; then sed -i -E 's|^#?{key}=.*|{key}={value}|' /etc/default/grub; "
            f"else echo '{key}={value}' >> /etc/default/grub; fi")


class Customizer(Page):
    ID = "customizer"
    TITLE = "Customizer"
    SUBTITLE = "GRUB, boot splash and login screen"
    ICON = "preferences-desktop-wallpaper-symbolic"
    KEYWORDS = "grub boot menu timeout plymouth splash login screen gdm lightdm sddm autologin background"

    def build(self):
        g = read_grub()
        grub = self.card("GRUB boot menu", "Values are read from /etc/default/grub; a backup is made before every change.")
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(14)
        self.g_timeout = Gtk.SpinButton.new_with_range(0, 60, 1)
        self.g_timeout.set_value(int(g.get("GRUB_TIMEOUT", "5")) if g.get("GRUB_TIMEOUT", "5").isdigit() else 5)
        combos = [f"{a}/{b}" for a in COLORS for b in ("black", "blue", "dark-gray", "light-gray")]
        self.g_normal = W.dropdown([(c, c) for c in combos], g.get("GRUB_COLOR_NORMAL", "light-gray/black"))
        self.g_high = W.dropdown([(c, c) for c in combos], g.get("GRUB_COLOR_HIGHLIGHT", "black/light-gray"))
        self.g_bg = Gtk.Entry()
        self.g_bg.set_text(g.get("GRUB_BACKGROUND", ""))
        self.g_bg.set_hexpand(True)
        self.g_cmdline = Gtk.Entry()
        self.g_cmdline.set_text(g.get("GRUB_CMDLINE_LINUX_DEFAULT", "quiet"))
        for i, (label, widget) in enumerate((("Timeout (seconds)", self.g_timeout), ("Normal colour", self.g_normal),
                                             ("Highlight colour", self.g_high), ("Background image", self.g_bg),
                                             ("Kernel parameters", self.g_cmdline))):
            grid.attach(W.label(label, "row-title"), 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)
        grid.attach(W.button("Browse…", on_click=lambda: pick_file(self.win, "GRUB background", lambda p: p and self.g_bg.set_text(p),
                                                                    os.path.join(self.win.ctx.home, "Pictures"))), 2, 3, 1, 1)
        grub.add(grid)
        self.g_hidden = W.switch_row("Hide the menu", "Hold Shift (BIOS) or press Esc (UEFI) during boot to show it.", g.get("GRUB_TIMEOUT_STYLE") == "hidden")
        self.g_osprober = W.switch_row("Detect other operating systems (os-prober)", "Lists Windows and other Linux systems in the menu.",
                                       g.get("GRUB_DISABLE_OS_PROBER", "true") == "false")
        self.g_saved = W.switch_row("Remember the last choice", None, g.get("GRUB_DEFAULT") == "saved", last=True)
        for w in (self.g_hidden, self.g_osprober, self.g_saved):
            grub.add(w)
        row = W.hbox(8)
        row.append(W.button("Apply GRUB settings", kind="primary", on_click=self.apply_grub))
        row.append(W.button("Restore backup", on_click=lambda: self.win.run(Task("Restore GRUB settings", [("Restoring", [
            "[ -f /etc/default/grub.debos.bak ] || fail 'No backup found.'", "cp /etc/default/grub.debos.bak /etc/default/grub", "update-grub"])]))))
        grub.add(row)

        ply = self.card("Boot splash (Plymouth)", "Use your own picture as the boot screen, or pick an installed theme. "
                                                  "The custom theme also shows the disk-encryption password prompt.")
        pgrid = Gtk.Grid()
        pgrid.set_row_spacing(10)
        pgrid.set_column_spacing(14)
        self.p_name = Gtk.Entry()
        self.p_name.set_text("debos-custom")
        self.p_img = Gtk.Entry()
        self.p_img.set_hexpand(True)
        themes = sorted(os.path.basename(d) for d in glob.glob("/usr/share/plymouth/themes/*") if os.path.isdir(d))
        self.p_theme = W.dropdown([(t, t) for t in themes] or [("", "(install plymouth-themes first)")], themes[0] if themes else "")
        for i, (label, widget) in enumerate((("Theme name", self.p_name), ("Picture (PNG)", self.p_img), ("Installed theme", self.p_theme))):
            pgrid.attach(W.label(label, "row-title"), 0, i, 1, 1)
            pgrid.attach(widget, 1, i, 1, 1)
        pgrid.attach(W.button("Browse…", on_click=lambda: pick_file(self.win, "Splash picture", lambda p: p and self.p_img.set_text(p),
                                                                     os.path.join(self.win.ctx.home, "Pictures"))), 2, 1, 1, 1)
        ply.add(pgrid)
        prow = W.hbox(8)
        prow.append(W.button("Create from picture", kind="primary", on_click=self.apply_plymouth))
        prow.append(W.button("Use installed theme", on_click=self.apply_existing))
        prow.append(W.button("Install more themes", on_click=lambda: self.win.run(Task("Plymouth themes", [
            ("Installing", "apt_install plymouth plymouth-themes"), ("Themes", "plymouth-set-default-theme -l")]))))
        ply.add(prow)

        login = self.card("Login screen", "Appearance and automatic login for the active login manager. "
                                          "Switch the login manager itself on Desktops & WMs > Login managers.")
        dm = system.display_manager() or ""
        lg = Gtk.Grid()
        lg.set_row_spacing(10)
        lg.set_column_spacing(14)
        self.l_dm = W.dropdown([("gdm3", "GDM"), ("lightdm", "LightDM GTK greeter"), ("slick", "LightDM Slick greeter"), ("sddm", "SDDM")],
                               {"gdm3": "gdm3", "gdm": "gdm3", "sddm": "sddm"}.get(dm, "lightdm"))
        self.l_bg = Gtk.Entry()
        self.l_bg.set_hexpand(True)
        self.l_gtk = Gtk.Entry()
        self.l_gtk.set_text("Adwaita")
        self.l_icons = Gtk.Entry()
        self.l_icons.set_text("Adwaita")
        self.l_font = Gtk.Entry()
        self.l_font.set_text("Noto Sans 11")
        users = system.users()
        self.l_user = W.dropdown([(u, u) for u in users] or [("", "no users")], self.win.ctx.user if self.win.ctx.user in users else (users[0] if users else ""))
        for i, (label, widget) in enumerate((("Login manager", self.l_dm), ("Background", self.l_bg), ("GTK theme", self.l_gtk),
                                             ("Icon theme", self.l_icons), ("Font", self.l_font), ("Automatic login user", self.l_user))):
            lg.attach(W.label(label, "row-title"), 0, i, 1, 1)
            lg.attach(widget, 1, i, 1, 1)
        lg.attach(W.button("Browse…", on_click=lambda: pick_file(self.win, "Login background", lambda p: p and self.l_bg.set_text(p),
                                                                  os.path.join(self.win.ctx.home, "Pictures"))), 2, 1, 1, 1)
        login.add(lg)
        self.l_list = W.switch_row("Show the user list", None, True)
        self.l_auto = W.switch_row("Automatic login", "Starts the desktop without asking for a password.", False, last=True)
        login.add(self.l_list)
        login.add(self.l_auto)
        login.add(W.button("Apply login settings", kind="primary", on_click=self.apply_login))

    # ---------------------------------------------------------------- GRUB
    def apply_grub(self):
        cmdline = self.g_cmdline.get_text().strip()
        if not re.match(r'^[A-Za-z0-9 ._=,:/+-]*$', cmdline):
            self.win.toast("Kernel parameters contain unsupported characters.", "err")
            return
        steps = [("Backing up /etc/default/grub", "cp /etc/default/grub /etc/default/grub.debos.bak"),
                 ("Writing settings", [
                     set_key("GRUB_TIMEOUT", int(self.g_timeout.get_value())),
                     set_key("GRUB_TIMEOUT_STYLE", "hidden" if self.g_hidden.switch.get_active() else "menu"),
                     set_key("GRUB_DISABLE_OS_PROBER", "false" if self.g_osprober.switch.get_active() else "true"),
                     set_key("GRUB_COLOR_NORMAL", f'"{W.dd_value(self.g_normal)}"'),
                     set_key("GRUB_COLOR_HIGHLIGHT", f'"{W.dd_value(self.g_high)}"'),
                     set_key("GRUB_CMDLINE_LINUX_DEFAULT", f'"{cmdline}"'),
                 ] + ([set_key("GRUB_DEFAULT", "saved"), set_key("GRUB_SAVEDEFAULT", "true")] if self.g_saved.switch.get_active()
                      else [set_key("GRUB_DEFAULT", "0"), "sed -i '/^GRUB_SAVEDEFAULT=/d' /etc/default/grub"]))]
        if self.g_osprober.switch.get_active():
            steps.append(("Installing os-prober", "ensure_pkg os-prober"))
        bg = self.g_bg.get_text().strip()
        if bg and not bg.startswith("/boot/grub/"):
            ext = os.path.splitext(bg)[1].lower().lstrip(".").replace("jpeg", "jpg")
            if not os.path.isfile(bg) or ext not in ("png", "jpg", "tga"):
                self.win.toast("GRUB backgrounds must be PNG, JPG or TGA files.", "err")
                return
            steps.append(("Copying background", [f"cp {shq(bg)} /boot/grub/debos-background.{ext}",
                                                 set_key("GRUB_BACKGROUND", f'"/boot/grub/debos-background.{ext}"')]))
        elif not bg:
            steps.append(("Removing background", "sed -i '/^GRUB_BACKGROUND=/d' /etc/default/grub"))
        steps.append(("Regenerating the boot menu", "update-grub"))
        self.win.run(Task("GRUB settings", steps))

    # ------------------------------------------------------------ Plymouth
    def _finish_plymouth(self, theme):
        return [("Activating the theme", f"plymouth-set-default-theme {shq(theme)}"),
                ("Enabling the splash", [
                    "if [ -f /etc/default/grub ] && ! grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=.*splash' /etc/default/grub; then",
                    "  cp /etc/default/grub /etc/default/grub.debos.bak",
                    "  sed -i -E 's/^(GRUB_CMDLINE_LINUX_DEFAULT=\")/\\1splash /' /etc/default/grub && update-grub",
                    "fi"]),
                ("Rebuilding the initramfs", "update-initramfs -u")]

    def apply_plymouth(self):
        img = self.p_img.get_text().strip()
        if not img.lower().endswith(".png") or not os.path.isfile(img):
            self.win.toast("Choose a PNG picture.", "err")
            return
        theme = re.sub(r"[^a-z0-9-]", "", self.p_name.get_text().strip().lower().replace(" ", "-")) or "debos-custom"
        d = f"/usr/share/plymouth/themes/{theme}"
        meta = "\n".join(["[Plymouth Theme]", f"Name={theme}", "Description=Custom splash created by Debos - Toolbox", "ModuleName=script",
                          "", "[script]", f"ImageDir={d}", f"ScriptFile={d}/{theme}.script"])
        steps = [("Installing Plymouth", "apt_install plymouth plymouth-themes"),
                 ("Creating the theme", [f"rm -rf {d}", f"mkdir -p {d}", f"install -m 0644 {shq(img)} {d}/background.png",
                                         f"cat > {d}/{theme}.plymouth <<'DEBOS_EOF'", meta, "DEBOS_EOF",
                                         f"cat > {d}/{theme}.script <<'DEBOS_EOF'", PLYMOUTH_SCRIPT.rstrip("\n"), "DEBOS_EOF"])]
        self.win.run(Task("Boot splash", steps + self._finish_plymouth(theme)))

    def apply_existing(self):
        theme = W.dd_value(self.p_theme)
        if not theme:
            return
        self.win.run(Task("Boot splash", [("Installing Plymouth", "ensure_pkg plymouth")] + self._finish_plymouth(theme)))

    # --------------------------------------------------------------- login
    def apply_login(self):
        dm = W.dd_value(self.l_dm)
        user = W.dd_value(self.l_user) or ""
        auto = self.l_auto.switch.get_active() and bool(user)
        show = self.l_list.switch.get_active()
        gtk_theme, icons, font = self.l_gtk.get_text().strip(), self.l_icons.get_text().strip(), self.l_font.get_text().strip()
        for v in (gtk_theme, icons, font, user):
            if not re.match(r"^[A-Za-z0-9 _.+-]*$", v):
                self.win.toast(f"Invalid value: {v}", "err")
                return
        steps, bg_target = [], ""
        bg = self.l_bg.get_text().strip()
        if bg:
            if not os.path.isfile(bg):
                self.win.toast("Background image not found.", "err")
                return
            ext = os.path.splitext(bg)[1].lower() or ".png"
            bg_target = f"/usr/share/backgrounds/debos/login{ext}"
            steps.append(("Copying the background (the login screen cannot read your home folder)",
                          ["mkdir -p /usr/share/backgrounds/debos", f"install -m 0644 {shq(bg)} {bg_target}"]))
        hide = "false" if show else "true"
        if dm == "gdm3":
            conf = ["[org/gnome/login-screen]", f"disable-user-list={hide}", "", "[org/gnome/desktop/interface]",
                    f"gtk-theme='{gtk_theme}'", f"icon-theme='{icons}'", f"font-name='{font}'"]
            if bg_target:
                conf += ["", "[org/gnome/desktop/background]", f"picture-uri='file://{bg_target}'", f"picture-uri-dark='file://{bg_target}'"]
            code = ["mkdir -p /etc/dconf/db/gdm.d /etc/dconf/profile",
                    "[ -f /etc/dconf/profile/gdm ] || printf 'user-db:user\\nsystem-db:gdm\\nfile-db:/usr/share/gdm/greeter-dconf-defaults\\n' > /etc/dconf/profile/gdm",
                    "cat > /etc/dconf/db/gdm.d/90-debos <<'DEBOS_EOF'"] + conf + ["DEBOS_EOF", "dconf update",
                    "CONF=/etc/gdm3/daemon.conf; [ -f \"$CONF\" ] || CONF=/etc/gdm3/custom.conf",
                    "grep -q '^\\[daemon\\]' \"$CONF\" || echo '[daemon]' >> \"$CONF\"",
                    "sed -i -E '/^#?\\s*AutomaticLogin(Enable)?\\s*=/d' \"$CONF\""]
            if auto:
                code.append(f"sed -i '/^\\[daemon\\]/a AutomaticLoginEnable=true\\nAutomaticLogin={user}' \"$CONF\"")
            steps.append(("Configuring GDM", code))
        elif dm in ("lightdm", "slick"):
            seat = ["[Seat:*]", f"greeter-hide-users={hide}"] + ([f"autologin-user={user}", "autologin-user-timeout=0"] if auto else [])
            code = ["mkdir -p /etc/lightdm/lightdm.conf.d", "cat > /etc/lightdm/lightdm.conf.d/50-debos.conf <<'DEBOS_EOF'"] + seat + ["DEBOS_EOF"]
            if auto:
                code += ["getent group autologin >/dev/null || groupadd -r autologin", f"gpasswd -a {user} autologin"]
            if dm == "lightdm":
                greeter = ["[greeter]", f"theme-name={gtk_theme}", f"icon-theme-name={icons}", f"font-name={font}"] + \
                          ([f"background={bg_target}"] if bg_target else [])
                code += ["mkdir -p /etc/lightdm/lightdm-gtk-greeter.conf.d",
                         "cat > /etc/lightdm/lightdm-gtk-greeter.conf.d/50-debos.conf <<'DEBOS_EOF'"] + greeter + ["DEBOS_EOF"]
            else:
                keys = {"theme-name": gtk_theme, "icon-theme-name": icons, "font-name": font}
                if bg_target:
                    keys["background"] = bg_target
                code += ["CONF=/etc/lightdm/slick-greeter.conf", "touch \"$CONF\"", "cp -n \"$CONF\" \"$CONF.debos.bak\" || true",
                         "grep -q '^\\[Greeter\\]' \"$CONF\" || echo '[Greeter]' >> \"$CONF\""]
                for k, v in keys.items():
                    if v:
                        code += [f"sed -i '/^{k}=/d' \"$CONF\"", f"sed -i '/^\\[Greeter\\]/a {k}={v}' \"$CONF\""]
            steps.append(("Configuring LightDM", code))
        else:
            conf = ["[Theme]", "Current=breeze"] + (["", "[Autologin]", f"User={user}", "Session=$SESSION"] if auto else [])
            code = ["SESSION=''",
                    "for s in plasma plasmawayland plasmax11; do if [ -f /usr/share/wayland-sessions/$s.desktop ] || [ -f /usr/share/xsessions/$s.desktop ]; then SESSION=$s; break; fi; done",
                    "[ -n \"$SESSION\" ] || SESSION=$(basename \"$(ls /usr/share/wayland-sessions/*.desktop /usr/share/xsessions/*.desktop 2>/dev/null | head -n1)\" .desktop)",
                    "mkdir -p /etc/sddm.conf.d", "cat > /etc/sddm.conf.d/50-debos.conf <<DEBOS_EOF"] + conf + ["DEBOS_EOF"]
            if bg_target:
                code.append(f"if [ -d /usr/share/sddm/themes/breeze ]; then printf '[General]\\nbackground=%s\\n' {bg_target} > /usr/share/sddm/themes/breeze/theme.conf.user; fi")
            steps.append(("Configuring SDDM", code))
        steps.append(("Done", "ok 'Restart the login manager or reboot to see the changes.'"))
        self.win.run(Task("Login screen settings", steps))
