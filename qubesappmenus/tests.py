#!/usr/bin/python3
# coding=utf-8
# pylint: skip-file
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016  Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.

import io
import os
import tempfile

import unittest
import unittest.mock

import logging
import pkg_resources
import qubesappmenus
import qubesappmenus.receive

class Label(object):
    def __init__(self, index, color, name):
        self.index = index
        self.color = color
        self.name = name
        self.icon = name + '.png'

class TestApp(object):
    labels = {1: Label(1, '0xcc0000', 'red')}

    def __init__(self):
        self.domains = {}

class TestFeatures(dict):

    def __init__(self, vm, **kwargs) -> None:
        self.vm = vm
        super().__init__(**kwargs)

    def check_with_template(self, feature, default=None):
        if feature in self:
            return self[feature]
        if hasattr(self.vm, 'template'):
            return self.vm.template.features.check_with_template(feature,
                default)
        else:
            return default

class TestVM(object):
    # pylint: disable=too-few-public-methods
    app = TestApp()

    def __init__(self, name, klass, **kwargs):
        self.running = False
        self.is_template = False
        self.name = name
        self.klass = klass
        self.log = logging.getLogger('qubesappmenus.tests')
        self.features = TestFeatures(self)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def is_running(self):
        return self.running

    def __str__(self):
        return self.name

VMPREFIX = 'test-'

class TC_00_Appmenus(unittest.TestCase):
    """Unittests for appmenus, theoretically runnable from git checkout"""
    def setUp(self):
        super(TC_00_Appmenus, self).setUp()
        vmname = VMPREFIX + 'standalone'
        self.standalone = TestVM(
            name=vmname,
            klass='StandaloneVM',
            updateable=True,
        )
        vmname = VMPREFIX + 'template'
        self.template = TestVM(
            name=vmname,
            klass='TemplateVM',
            updateable=True,
        )
        vmname = VMPREFIX + 'vm'
        self.appvm = TestVM(
            name=vmname,
            klass='AppVM',
            template=self.template,
            updateable=False,
        )
        self.app = TestApp()
        self.ext = qubesappmenus.Appmenus()
        self.basedir_obj = tempfile.TemporaryDirectory()
        self.basedir = self.basedir_obj.name
        self.basedir_patch = unittest.mock.patch('qubesappmenus.basedir',
            self.basedir)
        self.basedir_patch.start()

    def tearDown(self):
        self.basedir_patch.stop()
        self.basedir_obj.cleanup()
        super(TC_00_Appmenus, self).tearDown()

    def assertPathExists(self, path):
        if not os.path.exists(path):
            self.fail("Path {} does not exist".format(path))

    def assertPathNotExists(self, path):
        if os.path.exists(path):
            self.fail("Path {} exists while it should not".format(path))


    def test_000_templates_dirs(self):
        self.assertEqual(
            self.ext.templates_dirs(self.standalone),
            [os.path.join(self.basedir,
                self.standalone.name, 'apps.templates')]
        )
        self.assertEqual(
            self.ext.templates_dirs(self.template),
            [os.path.join(self.basedir,
                self.template.name, 'apps.templates')]
        )
        self.assertEqual(
            self.ext.templates_dirs(self.appvm),
            [os.path.join(self.basedir,
                self.appvm.name, 'apps.templates'),
             os.path.join(self.basedir,
                self.template.name, 'apps.templates')]
        )

    def test_001_template_icons_dir(self):
        self.assertEqual(
            self.ext.template_icons_dirs(self.standalone),
            [os.path.join(self.basedir,
                self.standalone.name, 'apps.tempicons')]
        )
        self.assertEqual(
            self.ext.template_icons_dirs(self.template),
            [os.path.join(self.basedir,
                self.template.name, 'apps.tempicons')]
        )
        self.assertEqual(
            self.ext.template_icons_dirs(self.appvm),
            [os.path.join(self.basedir,
                self.appvm.name, 'apps.tempicons'),
             os.path.join(self.basedir,
                self.template.name, 'apps.tempicons')]
        )

    def test_002_appmenus_dir(self):
        self.assertEqual(
            self.ext.appmenus_dir(self.standalone),
            os.path.join(self.basedir,
                self.standalone.name, 'apps')
        )
        self.assertEqual(
            self.ext.appmenus_dir(self.template),
            os.path.join(self.basedir,
                self.template.name, 'apps')
        )
        self.assertEqual(
            self.ext.appmenus_dir(self.appvm),
            os.path.join(self.basedir,
                self.appvm.name, 'apps')
        )

    def test_003_icons_dir(self):
        self.assertEqual(
            self.ext.icons_dir(self.standalone),
            os.path.join(self.basedir,
                self.standalone.name, 'apps.icons')
        )
        self.assertEqual(
            self.ext.icons_dir(self.template),
            os.path.join(self.basedir,
                self.template.name, 'apps.icons')
        )
        self.assertEqual(
            self.ext.icons_dir(self.appvm),
            os.path.join(self.basedir,
                self.appvm.name, 'apps.icons')
        )

    def test_005_created_appvm(self):
        tpl = TestVM('test-inst-tpl',
            klass='TemplateVM',
            virt_mode='pvh',
            updateable=True,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(tpl)
        appvm = TestVM('test-inst-app',
            klass='AppVM',
            template=tpl,
            virt_mode='pvh',
            updateable=False,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(appvm)
        with open(os.path.join(self.ext.templates_dirs(tpl)[0],
                'evince.desktop'), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__,
                'test-data/evince.desktop.template'))
        self.ext.appmenus_create(appvm, refresh_cache=False)
        self.ext.appicons_create(appvm)
        evince_path = os.path.join(
            self.ext.appmenus_dir(appvm), appvm.name + '-evince.desktop')
        self.assertPathExists(evince_path)
        with open(evince_path, 'rb') as f:
            self.assertEqual(
                pkg_resources.resource_string(__name__,
                    'test-data/evince.desktop').replace(b'%BASEDIR%',
                    qubesappmenus.basedir.encode()),
                f.read()
            )

    def test_006_created_appvm_custom(self):
        tpl = TestVM('test-inst-tpl',
            klass='TemplateVM',
            virt_mode='pvh',
            updateable=True,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(tpl)
        appvm = TestVM('test-inst-app',
            klass='AppVM',
            template=tpl,
            virt_mode='pvh',
            updateable=False,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(appvm)
        with open(os.path.join(self.ext.templates_dirs(tpl)[0],
                'evince.desktop'), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__,
                'test-data/evince.desktop.template'))
        self.ext.appmenus_create(appvm, refresh_cache=False)
        self.ext.appicons_create(appvm)

        with open(os.path.join(self.ext.templates_dirs(tpl)[0],
                'xterm.desktop'), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__,
                'test-data/xterm.desktop.template'))
        with open(os.path.join(self.ext.templates_dirs(tpl)[0],
                'evince.desktop'), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__,
                'test-data/evince.desktop.template').
                replace(b'Document Viewer', b'Random Viewer'))
        self.ext.appmenus_update(appvm)
        evince_path = os.path.join(
            self.ext.appmenus_dir(appvm), appvm.name + '-evince.desktop')
        self.assertPathExists(evince_path)
        with open(evince_path, 'rb') as f:
            self.assertEqual(
                pkg_resources.resource_string(__name__,
                    'test-data/evince.desktop')
                    .replace(b'%BASEDIR%', qubesappmenus.basedir.encode())
                    .replace(b'Document Viewer', b'Random Viewer'),
                f.read()
            )

        xterm_path = os.path.join(
            self.ext.appmenus_dir(appvm), appvm.name + '-xterm.desktop')
        self.assertPathExists(xterm_path)
        with open(xterm_path, 'rb') as f:
            self.assertEqual(
                pkg_resources.resource_string(__name__,
                    'test-data/xterm.desktop')
                    .replace(b'%BASEDIR%', qubesappmenus.basedir.encode()),
                f.read()
            )

    def test_100_get_appmenus(self):
        self.maxDiff = None
        def _run(service, **kwargs):
            class PopenMockup(object):
                pass
            self.assertEqual(service, 'qubes.GetAppmenus')
            p = PopenMockup()
            p.stdout = pkg_resources.resource_stream(__name__,
                'test-data/appmenus.input')
            p.wait = lambda: None
            p.returncode = 0
            return p
        vm = TestVM('test-vm', klass='TemplateVM', run_service=_run)
        appmenus = qubesappmenus.receive.get_appmenus(vm)
        expected_appmenus = {
            'org.gnome.Nautilus': {
                'Name': 'Files',
                'Comment': 'Access and organize files',
                'Categories': 'GNOME;GTK;Utility;Core;FileManager;',
                'Exec': 'qubes-desktop-run '
                        '/usr/share/applications/org.gnome.Nautilus.desktop',
                'Icon': 'system-file-manager',
            },
            'org.gnome.Weather.Application': {
                'Name': 'Weather',
                'Comment': 'Show weather conditions and forecast',
                'Categories': 'GNOME;GTK;Utility;Core;',
                'Exec': 'qubes-desktop-run '
                        '/usr/share/applications/org.gnome.Weather.Application.desktop',
                'Icon': 'org.gnome.Weather.Application',
            },
            'org.gnome.Cheese': {
                'Name': 'Cheese',
                'GenericName': 'Webcam Booth',
                'Comment': 'Take photos and videos with your webcam, with fun graphical effects',
                'Categories': 'GNOME;AudioVideo;Video;Recorder;',
                'Exec': 'qubes-desktop-run '
                        '/usr/share/applications/org.gnome.Cheese.desktop',
                'Icon': 'cheese',
            },
            'evince': {
                'Name': 'Document Viewer',
                'Comment': 'View multi-page documents',
                'Categories': 'GNOME;GTK;Office;Viewer;Graphics;2DGraphics;VectorGraphics;',
                'Exec': 'qubes-desktop-run '
                        '/usr/share/applications/evince.desktop',
                'Icon': 'evince',
            },
        }
        self.assertEqual(expected_appmenus, appmenus)

    def test_110_create_template(self):
        values = {
            'Name': 'Document Viewer',
            'Comment': 'View multi-page documents',
            'Categories': 'GNOME;GTK;Office;Viewer;Graphics;2DGraphics;VectorGraphics;',
            'Exec': 'qubes-desktop-run '
                    '/usr/share/applications/evince.desktop',
            'Icon': 'evince',
        }
        expected_template = (
            '[Desktop Entry]\n'
            'Version=1.0\n'
            'Type=Application\n'
            'Terminal=false\n'
            'X-Qubes-VmName=%VMNAME%\n'
            'Icon=%VMDIR%/apps.icons/evince.png\n'
            'Name=%VMNAME%: Document Viewer\n'
            'Comment=View multi-page documents\n'
            'Categories=GNOME;GTK;Office;Viewer;Graphics;2DGraphics'
            ';VectorGraphics;X-Qubes-VM;\n'
            'Exec=qvm-run -q -a --service -- %VMNAME% qubes.StartApp+evince\n'
            'X-Qubes-DispvmExec=qvm-run -q -a --service --dispvm=%VMNAME% -- '
            'qubes.StartApp+evince\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'evince.desktop')
            qubesappmenus.receive.create_template(
                path, 'evince', values, False)
            with open(path) as f:
                actual_template = f.read()
            self.assertEqual(actual_template, expected_template)

    def test_111_create_template_legacy(self):
        values = {
            'Name': 'Document Viewer',
            'Comment': 'View multi-page documents',
            'Categories': 'GNOME;GTK;Office;Viewer;Graphics;2DGraphics;VectorGraphics;',
            'Exec': 'qubes-desktop-run '
                    '/usr/share/applications/evince.desktop',
            'Icon': 'evince',
        }
        expected_template = (
            '[Desktop Entry]\n'
            'Version=1.0\n'
            'Type=Application\n'
            'Terminal=false\n'
            'X-Qubes-VmName=%VMNAME%\n'
            'Icon=%VMDIR%/apps.icons/evince.png\n'
            'Name=%VMNAME%: Document Viewer\n'
            'Comment=View multi-page documents\n'
            'Categories=GNOME;GTK;Office;Viewer;Graphics;2DGraphics'
            ';VectorGraphics;X-Qubes-VM;\n'
            'Exec=qvm-run -q -a %VMNAME% -- \'qubes-desktop-run '
            '/usr/share/applications/evince.desktop\'\n'
            'X-Qubes-DispvmExec=qvm-run -q -a --dispvm=%VMNAME% -- '
            '\'qubes-desktop-run /usr/share/applications/evince.desktop\'\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'evince.desktop')
            qubesappmenus.receive.create_template(
                path, 'evince', values, True)
            with open(path) as f:
                actual_template = f.read()
            self.assertEqual(actual_template, expected_template)

    @unittest.mock.patch('subprocess.check_call')
    def test_120_create_appvm(self, mock_subprocess):
        tpl = TestVM('test-inst-tpl',
            klass='TemplateVM',
            virt_mode='pvh',
            updateable=True,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(tpl)
        with open(os.path.join(self.ext.templates_dirs(tpl)[0],
                'evince.desktop'), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__,
                'test-data/evince.desktop.template'))
        appvm = TestVM('test-inst-app',
            klass='AppVM',
            template=tpl,
            virt_mode='pvh',
            updateable=False,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(appvm)
        self.ext.appmenus_create(appvm, refresh_cache=False)
        evince_path = os.path.join(
            self.ext.appmenus_dir(appvm), 'test-inst-app-evince.desktop')
        self.assertPathExists(evince_path)
        with open(evince_path, 'rb') as f:
            self.assertEqual(
                pkg_resources.resource_string(__name__,
                    'test-data/evince.desktop').replace(b'%BASEDIR%',
                    qubesappmenus.basedir.encode()),
                f.read()
            )

        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        self.assertEqual(
            args[:3],
            ['xdg-desktop-menu', 'install', '--noupdate'])
        prefix = self.basedir + '/test-inst-app/apps/test-inst-app-'
        self.assertEqual(sorted(args[3:]), [
            prefix + 'evince.desktop',
            prefix + 'qubes-start.desktop',
            prefix + 'qubes-vm-settings.desktop',
            prefix + 'vm.directory'
        ])

    @unittest.mock.patch('subprocess.check_call')
    def test_121_create_appvm_with_whitelist(self, mock_subprocess):
        tpl = TestVM('test-inst-tpl',
            klass='TemplateVM',
            virt_mode='pvh',
            updateable=True,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(tpl)
        with open(os.path.join(self.ext.templates_dirs(tpl)[0],
                'evince.desktop'), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__,
                'test-data/evince.desktop.template'))
        with open(os.path.join(self.basedir, tpl.name,
                'vm-whitelisted-appmenus.list'), 'wb') as f:
            f.write(b'evince.desktop\n')
        appvm = TestVM('test-inst-app',
            klass='AppVM',
            template=tpl,
            virt_mode='pvh',
            updateable=False,
            provides_network=False,
            label=self.app.labels[1])
        self.ext.appmenus_init(appvm)
        self.ext.appmenus_create(appvm, refresh_cache=False)
        evince_path = os.path.join(
            self.ext.appmenus_dir(appvm), 'test-inst-app-evince.desktop')
        self.assertPathExists(evince_path)
        with open(evince_path, 'rb') as f:
            self.assertEqual(
                pkg_resources.resource_string(__name__,
                    'test-data/evince.desktop').replace(b'%BASEDIR%',
                    qubesappmenus.basedir.encode()),
                f.read()
            )

        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        self.assertEqual(
            args[:3],
            ['xdg-desktop-menu', 'install', '--noupdate'])
        prefix = self.basedir + '/test-inst-app/apps/test-inst-app-'
        self.assertEqual(sorted(args[3:]), [
            prefix + 'evince.desktop',
            prefix + 'qubes-vm-settings.desktop',
            prefix + 'vm.directory'
        ])

    def test_130_process_appmenus_templates(self):
        def _run(service, **kwargs):
            class PopenMockup(object):
                pass
            self.assertEqual(service, 'qubes.GetImageRGBA')
            p = PopenMockup()
            p.stdin = unittest.mock.Mock()
            p.stdout = io.BytesIO(b'1 1\nxxxx')
            p.wait = lambda: None
            p.returncode = 0
            return p
        self.appvm.virt_mode = 'pvh'
        self.appvm.run_service = _run
        self.appvm.log = unittest.mock.Mock()
        appmenus = {
            'org.gnome.Cheese': {
                'Name': 'Cheese',
                'GenericName': 'Webcam Booth',
                'Comment': 'Take photos and videos with your webcam, with fun graphical effects',
                'Categories': 'GNOME;AudioVideo;Video;Recorder;',
                'Exec': 'qubes-desktop-run '
                        '/usr/share/applications/org.gnome.Cheese.desktop',
                'Icon': 'cheese',
            },
            'evince': {
                'Name': 'Document Viewer',
                'Comment': 'View multi-page documents',
                'Categories': 'GNOME;GTK;Office;Viewer;Graphics;2DGraphics;VectorGraphics;',
                'Exec': 'qubes-desktop-run '
                        '/usr/share/applications/evince.desktop',
                'Icon': 'evince',
            },
        }

        # function under test
        qubesappmenus.receive.process_appmenus_templates(self.ext,
            self.appvm, appmenus)

        evince_path = os.path.join(
            self.ext.templates_dirs(self.appvm)[0],
            'evince.desktop')
        self.assertPathExists(evince_path)
        with open(evince_path, 'rb') as f:
            self.assertEqual(
                pkg_resources.resource_string(__name__,
                    'test-data/evince.desktop.template'),
                f.read()
            )
        self.assertCountEqual(self.appvm.log.mock_calls, [
            ('info', ('Creating org.gnome.Cheese',), {}),
            ('info', ('Creating evince',), {}),
        ])



def list_tests():
    return (TC_00_Appmenus,)
