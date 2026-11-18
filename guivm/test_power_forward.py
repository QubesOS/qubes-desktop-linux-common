#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2026  Frederic Pierret  <frederic@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#

"""
Tests of qubes-guivm-power-forward without D-Bus or QubesDB
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))


class QubesDBError(Exception):
    pass


def load():
    gi = types.ModuleType("gi")
    gi.require_version = lambda *args: None
    repository = types.ModuleType("gi.repository")
    repository.Gio = mock.Mock()
    repository.GLib = mock.Mock()
    gi.repository = repository
    qubesdb = types.ModuleType("qubesdb")
    qubesdb.Error = QubesDBError
    qubesdb.QubesDB = mock.Mock()
    modules = {"gi": gi, "gi.repository": repository, "qubesdb": qubesdb}
    path = os.path.join(HERE, "qubes-guivm-power-forward")
    loader = importlib.machinery.SourceFileLoader("power_forward", path)
    spec = importlib.util.spec_from_loader("power_forward", loader)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, modules):
        loader.exec_module(module)
    return module


power = load()


class TC_00_Forward(unittest.TestCase):
    def setUp(self):
        self.qdb = mock.Mock()
        self.qdb.read.return_value = None
        patch = mock.patch.object(
            power.qubesdb, "QubesDB", return_value=self.qdb
        )
        patch.start()
        self.addCleanup(patch.stop)

    def test_000_services(self):
        self.assertEqual(
            power.SERVICES,
            {
                "poweroff": "qubes.PowerShutdown",
                "halt": "qubes.PowerShutdown",
                "reboot": "qubes.PowerReboot",
            },
        )
        self.assertLess(power.TIMEOUT, 5)

    def test_001_forward(self):
        with mock.patch.object(power.subprocess, "run") as run:
            run.return_value.returncode = 0
            power.forward("reboot")
        self.qdb.read.assert_called_once_with("/qubes-shutdown-requested")
        self.qdb.close.assert_called_once_with()
        self.assertEqual(
            run.call_args.args[0],
            ["qrexec-client-vm", "dom0", "qubes.PowerReboot"],
        )
        self.assertEqual(run.call_args.kwargs["timeout"], power.TIMEOUT)

    def test_002_dom0_requested(self):
        self.qdb.read.return_value = b"1"
        with mock.patch.object(power.subprocess, "run") as run:
            power.forward("poweroff")
        run.assert_not_called()

    def test_003_no_qubesdb(self):
        power.qubesdb.QubesDB.side_effect = QubesDBError()
        with mock.patch.object(power.subprocess, "run") as run:
            run.return_value.returncode = 0
            power.forward("halt")
        self.assertEqual(
            run.call_args.args[0],
            ["qrexec-client-vm", "dom0", "qubes.PowerShutdown"],
        )

    def test_004_other_kind(self):
        with mock.patch.object(power.subprocess, "run") as run:
            power.forward("kexec")
            power.forward("")
        run.assert_not_called()
        power.qubesdb.QubesDB.assert_not_called()

    def test_005_timeout(self):
        with mock.patch.object(
            power.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("qrexec-client-vm", 3),
        ):
            power.forward("reboot")


class TC_01_Prepare(unittest.TestCase):
    def setUp(self):
        self.forwarder = power.Forwarder(mock.Mock())
        self.forwarder.inhibit = mock.Mock()
        self.forwarder.release = mock.Mock()

    def prepare(self, start, metadata):
        params = mock.Mock()
        params.unpack.return_value = (start, metadata)
        self.forwarder.on_prepare(None, None, None, None, None, params)

    def test_000_shutdown(self):
        with mock.patch.object(power, "forward") as forward:
            self.prepare(True, {"type": "poweroff"})
        forward.assert_called_once_with("poweroff")
        self.forwarder.release.assert_called_once_with()
        self.forwarder.inhibit.assert_not_called()

    def test_001_release_on_error(self):
        with mock.patch.object(power, "forward", side_effect=OSError()):
            with self.assertRaises(OSError):
                self.prepare(True, {"type": "reboot"})
        self.forwarder.release.assert_called_once_with()

    def test_002_cancelled(self):
        with mock.patch.object(power, "forward") as forward:
            self.prepare(False, {})
        forward.assert_not_called()
        self.forwarder.inhibit.assert_called_once_with()
        self.forwarder.release.assert_not_called()


if __name__ == "__main__":
    unittest.main()
