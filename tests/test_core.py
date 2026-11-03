"""Unit tests for the non-GUI core of Debos - Toolbox.

Run from the repository root:  python3 -m unittest discover -s tests -v
They need no root rights and no network; files are created in temporary directories.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "debos-toolbox", "usr", "lib", "debos-toolbox"))

from debos.core import catalog, doctor, kernels, sources, system, tasks  # noqa: E402


def bash_syntax_ok(text):
    r = subprocess.run(["bash", "-n"], input=text, text=True, capture_output=True)
    return r.returncode == 0, r.stderr


class TempDir(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="debos-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class SourcesTest(TempDir):
    def test_list_parsing_ignores_trailing_comment(self):
        p = self.write("a.list", "deb [arch=amd64 signed-by=/k.gpg] http://deb.debian.org/debian trixie main contrib # note\n"
                                 "# deb-src http://deb.debian.org/debian trixie main\n")
        e = sources.parse_file(p)
        self.assertEqual(len(e), 2)
        self.assertEqual(e[0].components, ["main", "contrib"])
        self.assertEqual(e[0].signed_by, "/k.gpg")
        self.assertTrue(e[0].enabled)
        self.assertFalse(e[1].enabled)

    def test_deb822_parsing_multiline_and_disabled(self):
        p = self.write("d.sources", "Types: deb deb-src\nURIs: http://deb.debian.org/debian\nSuites: trixie trixie-updates\n"
                                    "Components: main\n contrib\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\n"
                                    "# comment\nTypes: deb\nURIs: http://x.org/y\nSuites: s\nComponents: c\nEnabled: no\n")
        e = sources.parse_file(p)
        self.assertEqual(len(e), 2)
        self.assertEqual(e[0].types, ["deb", "deb-src"])
        self.assertEqual(e[0].components, ["main", "contrib"])
        self.assertEqual(len(list(e[0].keys())), 4)
        self.assertTrue(e[0].is_official_debian())
        self.assertFalse(e[1].enabled)

    def test_disable_enable_round_trip(self):
        text = "deb http://deb.debian.org/debian trixie main\n"
        p = self.write("r.list", text)
        e = sources.parse_file(p)[0]
        off = sources.disable_in_text(text, e)
        self.assertTrue(off.startswith(sources.DISABLED_MARK))
        self.assertFalse(sources.parse_file(p, off)[0].enabled)
        on = sources.enable_in_text(off, sources.parse_file(p, off)[0])
        self.assertEqual(on, text)

    def test_signed_by_set_and_remove(self):
        text = "deb [arch=amd64] http://x.org/debian trixie main\n"
        p = self.write("s.list", text)
        t1 = sources.set_signed_by_in_text(text, sources.parse_file(p)[0], "/etc/apt/keyrings/x.gpg")
        self.assertIn("[arch=amd64 signed-by=/etc/apt/keyrings/x.gpg]", t1)
        t2 = sources.set_signed_by_in_text(t1, sources.parse_file(p, t1)[0], "")
        self.assertEqual(t2, text)
        d = "Types: deb\nURIs: http://x.org\nSuites: a\nComponents: b\nSigned-By: /k.gpg\n"
        pd = self.write("s.sources", d)
        t3 = sources.set_signed_by_in_text(d, sources.parse_file(pd)[0], "")
        self.assertNotIn("Signed-By", t3)

    def test_set_components(self):
        text = "deb [signed-by=/k.gpg] http://x.org/debian trixie main # keep\n"
        p = self.write("c.list", text)
        out = sources.set_components_in_text(text, sources.parse_file(p)[0], ["main", "contrib"])
        self.assertEqual(out, "deb [signed-by=/k.gpg] http://x.org/debian trixie main contrib # keep\n")

    def test_vendor_with_debian_layout_is_not_official(self):
        p = self.write("j.sources", "Types: deb\nURIs: https://repo.jellyfin.org/debian\nSuites: trixie\nComponents: main\n"
                                    "Signed-By: /etc/apt/keyrings/jellyfin.gpg\n")
        self.assertFalse(sources.parse_file(p)[0].is_official_debian())

    def test_official_sources_text_is_parseable(self):
        for branch in ("stable", "testing", "sid", "oldstable"):
            text = sources.official_sources_text(branch, system.STABLE, system.TESTING)
            p = self.write(f"{branch}.sources", text)
            entries = sources.parse_file(p)
            self.assertTrue(entries, branch)
            self.assertTrue(all(e.is_official_debian() for e in entries), branch)


class DedupeTest(TempDir):
    def setUp(self):
        super().setUp()
        self.key = self.write("archive.gpg", "not a real key")
        say, doctor.say = doctor.say, lambda *a: None
        self.addCleanup(setattr, doctor, "say", say)

    def test_merges_components_and_disables_duplicate(self):
        a = self.write("sources.list", "deb http://x.org/debian trixie main universe\n")
        b = self.write("dup.list", f"deb [signed-by={self.key}] http://x.org/debian trixie main\n")
        doctor.dedupe(sources.parse_all([a, b]))
        self.assertFalse(sources.parse_file(a)[0].enabled)
        kept = sources.parse_file(b)[0]
        self.assertTrue(kept.enabled)
        self.assertEqual(kept.components, ["main", "universe"])

    def test_keeps_entry_with_unique_suite_and_aligns_signed_by(self):
        a = self.write("dup.list", f"deb [signed-by={self.key}] http://x.org/debian trixie main\n")
        b = self.write("multi.sources", "Types: deb\nURIs: http://x.org/debian\nSuites: trixie trixie-updates\nComponents: contrib\n")
        doctor.dedupe(sources.parse_all([a, b]))
        multi = sources.parse_file(b)[0]
        self.assertTrue(multi.enabled)
        self.assertEqual(multi.signed_by, self.key)
        self.assertTrue(sources.parse_file(a)[0].enabled)

    def test_unrelated_entries_untouched(self):
        a = self.write("a.list", "deb http://x.org/debian trixie main\ndeb http://x.org/debian trixie-updates main\n")
        before = self.read(a)
        doctor.dedupe(sources.parse_all([a]))
        self.assertEqual(self.read(a), before)


class AptOutputTest(unittest.TestCase):
    def test_patterns_for_apt2_apt3_and_sqv(self):
        lines = [
            "W: GPG error: http://deb.debian.org/debian bookworm InRelease: The following signatures couldn't be "
            "verified because the public key is not available: NO_PUBKEY 6ED0E7B82643E131",
            "W: OpenPGP signature verification failed: http://archive.example.org/debian trixie InRelease: The following "
            "signatures couldn't be verified because the public key is not available: NO_PUBKEY 871920D1991BC93C",
            "W: OpenPGP signature verification failed: https://download.docker.com/linux/debian trixie InRelease: "
            "Sub-process /usr/bin/sqv returned an error code (1), error message is: Missing key 7EA0A9C3F273FCD8, which "
            "is needed to verify signature.",
            "W: OpenPGP signature verification failed: https://repository.example.com stable InRelease: Sub-process "
            "/usr/bin/sqv returned an error code (1), error message is: Signing key on 5384CE82BA52C83A is not bound",
            "W: GPG error: https://dl.example.com stable InRelease: The following signatures were invalid: EXPKEYSIG "
            "1234567890ABCDEF Example <a@b>",
            "E: The repository 'http://x.org/debian nonexistent Release' does not have a Release file.",
            "E: The repository 'http://x.org/debian trixie InRelease' is not signed.",
            "E: Conflicting values set for option Signed-By regarding source https://x.org/apt/ stable: /a.gpg != ",
        ]
        found = doctor.analyse_apt_output(lines)
        self.assertEqual([k for _u, _s, k in found["nopubkey"]], ["6ED0E7B82643E131", "871920D1991BC93C", "7EA0A9C3F273FCD8"])
        self.assertEqual([k for _u, _s, k in found["expkeysig"]], ["5384CE82BA52C83A", "1234567890ABCDEF"])
        self.assertEqual(found["no_release"], [("http://x.org/debian", "nonexistent")])
        self.assertEqual(found["not_signed"], [("http://x.org/debian", "trixie")])
        self.assertEqual(found["conflict"], [("https://x.org/apt/", "stable")])


class ReleaseTest(unittest.TestCase):
    def detect(self, osr, dv, suites=frozenset()):
        return system.detect_release(osr, dv, set(suites))

    def test_branches(self):
        stable = f'ID=debian\nVERSION_ID="13"\nVERSION_CODENAME={system.STABLE}\n'
        self.assertEqual(self.detect(stable, "13.1")["branch"], "stable")
        rolling = f"ID=debian\nVERSION_CODENAME={system.TESTING}\n"
        r = self.detect(rolling, f"{system.TESTING}/sid", {system.TESTING})
        self.assertEqual((r["branch"], r["debian_codename"]), ("testing", system.TESTING))
        self.assertEqual(r["vendor_codename"], system.STABLE)
        r = self.detect(rolling, f"{system.TESTING}/sid", {"sid"})
        self.assertEqual((r["branch"], r["debian_codename"]), ("sid", "sid"))

    def test_lmde(self):
        r = self.detect("ID=linuxmint\nVERSION_ID=7\nVERSION_CODENAME=gigi\nDEBIAN_CODENAME=trixie\nID_LIKE=debian\n", "13.0")
        self.assertTrue(r["is_lmde"])
        self.assertEqual(r["debian_codename"], "trixie")


class ScriptTest(unittest.TestCase):
    def ctx(self):
        return tasks.Context(release={"branch": "stable", "debian_codename": system.STABLE,
                                      "vendor_codename": system.STABLE, "is_lmde": False})

    def test_heredoc_steps_are_valid_bash(self):
        step = ("Write a file", ["cat > /dev/null <<EOF", "Types: deb", "EOF", "echo done"])
        ok, err = bash_syntax_ok(tasks.build_script(tasks.Task("t", [step]), self.ctx()))
        self.assertTrue(ok, err)

    def test_arch_is_not_exported(self):
        script = tasks.build_script(tasks.Task("t", [("s", "true")]), self.ctx())
        self.assertIn("unset ARCH CROSS_COMPILE", script)
        for line in script.splitlines():
            if line.startswith("export "):
                self.assertNotIn("ARCH", line.split())

    def run_script(self, task):
        script = tasks.build_script(task, self.ctx())
        r = subprocess.run(["bash"], input=script, text=True, capture_output=True, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def test_failed_step_is_reported_and_others_continue(self):
        rc, out = self.run_script(tasks.Task("t", [("one", "true"), ("two", "false"), ("three", "echo third-ran")]))
        self.assertEqual(rc, 1)
        self.assertIn("third-ran", out)
        self.assertIn("1 of 3 step(s) failed", out)

    def test_stop_on_error_skips_dependent_steps(self):
        rc, out = self.run_script(tasks.Task("t", [("one", "false"), ("two", "echo second-ran")], stop_on_error=True))
        self.assertEqual(rc, 1)
        self.assertNotIn("second-ran", out)
        self.assertIn("Skipping the remaining 1 step(s)", out)

    def test_success(self):
        rc, out = self.run_script(tasks.Task("t", [("one", "true"), ("two", ["x=1", "[ $x -eq 1 ]"])]))
        self.assertEqual(rc, 0, out)
        self.assertIn("All 2 step(s) finished successfully", out)


class KernelTest(unittest.TestCase):
    def test_mainline_recipe_is_valid_bash(self):
        for kw in ({}, {"version": "6.12"}, {"version": "6.6.60", "localmod": True, "config": "defconfig", "jobs": 4}):
            task = tasks.Task("k", kernels.mainline_steps(**kw), stop_on_error=True)
            ok, err = bash_syntax_ok(tasks.build_script(task, ScriptTest.ctx(self)))
            self.assertTrue(ok, f"{kw}: {err}")

    def test_mainline_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            kernels.mainline_steps(version="6.1; rm -rf /")
        with self.assertRaises(ValueError):
            kernels.mainline_steps(suffix="-$(id)")

    def test_mainline_uses_real_kernel_release(self):
        code = "\n".join(s[1] if isinstance(s[1], str) else "\n".join(s[1]) for s in kernels.mainline_steps(version="6.12"))
        self.assertIn("include/config/kernel.release", code)
        self.assertIn("fakeroot", code)
        self.assertNotIn('yes "" |', code)

    def test_kernel_kind(self):
        self.assertEqual(kernels.kernel_kind("6.12.48+deb13-amd64"), "Debian")
        self.assertEqual(kernels.kernel_kind("6.1.0-18-amd64"), "Debian")
        self.assertEqual(kernels.kernel_kind("6.17.2-x64v3-xanmod1"), "XanMod")
        self.assertEqual(kernels.kernel_kind("6.16-3.1-liquorix-amd64"), "Liquorix")
        self.assertEqual(kernels.kernel_kind("6.8.0-debos"), "Built by Debos")

    def test_remove_steps(self):
        k = [{"version": "6.1.0-1-amd64", "managed": True, "running": False, "package": "linux-image-6.1.0-1-amd64",
              "headers": ["linux-headers-6.1.0-1-amd64"], "dbg": None},
             {"version": "6.7.4-debos", "managed": False, "running": False},
             {"version": "6.12.0-1-amd64", "managed": True, "running": True, "package": "linux-image-6.12.0-1-amd64",
              "headers": [], "dbg": None}]
        code = "\n".join(c if isinstance(c, str) else "\n".join(c) for _t, c in kernels.remove_steps(k))
        self.assertIn("linux-image-6.1.0-1-amd64", code)
        self.assertIn("remove-kernel-files 6.7.4-debos", code)
        self.assertNotIn("6.12.0-1-amd64", code)   # never the running kernel


class CatalogTest(unittest.TestCase):
    def test_unique_ids_and_valid_recipes(self):
        ids = [a["id"] for a in catalog.APPS]
        self.assertEqual(len(ids), len(set(ids)))
        ctx = ScriptTest.ctx(self)
        for app in catalog.APPS:
            self.assertTrue(app["methods"], app["id"])
            for m in app["methods"]:
                task = tasks.Task(app["name"], catalog.install_steps(app, m))
                ok, err = bash_syntax_ok(tasks.build_script(task, ctx))
                self.assertTrue(ok, f"{app['id']} / {m['type']}: {err}")


if __name__ == "__main__":
    unittest.main()
