#!/usr/bin/python3
# pylint: skip-file
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2026  Akshat Lakhera <akshatlnct2024@gmail.com>
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

import contextlib
import fcntl
import io
import json
import os
import re
import sys
import tempfile
import unittest
import unittest.mock

import qubesclipboard

MAX_SIZE = qubesclipboard.MAX_CLIPBOARD_SIZE


class FakeStdin(object):
    def __init__(self, data=b'', tty=False):
        self.buffer = io.BytesIO(data)
        self.tty = tty

    def isatty(self):
        return self.tty


class TC_00_Clipboard(unittest.TestCase):
    def setUp(self):
        super().setUp()
        # point all the clipboard files at a temporary directory
        self.tmpdir = tempfile.mkdtemp()
        for name in ('DATA', 'METADATA', 'SOURCE', 'XEVENT', 'APPVIEWER_LOCK'):
            path = os.path.join(self.tmpdir,
                os.path.basename(getattr(qubesclipboard, name)))
            patcher = unittest.mock.patch.object(qubesclipboard, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for name in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, name))
        os.rmdir(self.tmpdir)
        super().tearDown()

    def read_file(self, name):
        with open(os.path.join(self.tmpdir, name), 'rb') as f:
            return f.read()

    def read_metadata(self):
        return self.read_file('qubes-clipboard.bin.metadata').decode('ascii')

    def run_tool(self, *args, stdin=b'', tty=False):
        """Run main() with *args*, return (exit code, stderr output)"""
        stderr = io.StringIO()
        with unittest.mock.patch.object(sys, 'stdin', FakeStdin(stdin, tty)), \
                contextlib.redirect_stderr(stderr):
            retcode = qubesclipboard.main(list(args))
        return retcode, stderr.getvalue()

    def test_000_copy_writes_files(self):
        data = 'zażółć gęślą jaźń\n'.encode('utf-8')
        qubesclipboard.copy_to_global_clipboard(data)

        self.assertEqual(self.read_file('qubes-clipboard.bin'), data)
        self.assertEqual(self.read_file('qubes-clipboard.bin.source'),
            b'dom0')
        self.assertEqual(self.read_file('qubes-clipboard.bin.xevent'), b'0')
        self.assertEqual(json.loads(self.read_metadata()), {
            'vmname': 'dom0',
            'xevent_timestamp': 0,
            'successful': 1,
            'copy_action': 1,
            'paste_action': 0,
            'malformed_request': 0,
            'oversized_request': 0,
            'cleared': 0,
            'qrexec_clipboard': 0,
            'sent_size': len(data),
            'buffer_size': MAX_SIZE,
            'protocol_version_xside': 0x00010008,
            'protocol_version_vmside': 0x00010008,
        })

    def test_001_metadata_format(self):
        """qubes-guid reads .metadata with sscanf, one "key":value per line"""
        qubesclipboard.copy_to_global_clipboard(b'text')

        lines = self.read_metadata().split('\n')
        self.assertEqual(lines[0], '{')
        self.assertEqual(lines[-2:], ['}', ''])
        for line in lines[1:-2]:
            self.assertRegex(line, r'^"[A-Za-z0-9_-]+":["A-Za-z0-9_-]+,?$')
        self.assertIn('"vmname":"dom0",', lines)
        self.assertIn('"sent_size":4,', lines)

    def test_002_files_written_under_lock_source_last(self):
        written = []
        real_open = open

        def tracking_open(path, *args, **kwargs):
            # the lock must be held for every write
            with real_open(qubesclipboard.APPVIEWER_LOCK, 'rb') as lock_file:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            written.append(os.path.basename(path))
            return real_open(path, *args, **kwargs)

        with unittest.mock.patch('builtins.open', tracking_open):
            qubesclipboard.copy_to_global_clipboard(b'text')

        self.assertCountEqual(written, [
            'qubes-clipboard.bin',
            'qubes-clipboard.bin.xevent',
            'qubes-clipboard.bin.metadata',
            'qubes-clipboard.bin.source',
        ])
        # the widget reads .metadata only if it is newer than the data file,
        # and reacts to the .source file
        self.assertLess(written.index('qubes-clipboard.bin'),
            written.index('qubes-clipboard.bin.metadata'))
        self.assertEqual(written[-1], 'qubes-clipboard.bin.source')

    def test_010_copy_stdin(self):
        data = 'żółw\n'.encode('utf-8')
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool(stdin=data)
        self.assertEqual(retcode, 0)
        copy.assert_called_once_with(data)
        self.assertEqual(stderr, 'Copied 8 bytes to the global clipboard.\n')

    def test_011_copy_file(self):
        path = os.path.join(self.tmpdir, 'input.txt')
        with open(path, 'wb') as f:
            f.write(b'from file')
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool('-q', path, stdin=b'not this')
        self.assertEqual(retcode, 0)
        copy.assert_called_once_with(b'from file')
        self.assertEqual(stderr, '')

    def test_012_tty_prompt(self):
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool('-', stdin=b'typed', tty=True)
        self.assertEqual(retcode, 0)
        copy.assert_called_once_with(b'typed')
        self.assertIn('Ctrl+D', stderr)

        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool('-q', stdin=b'typed', tty=True)
        self.assertEqual(retcode, 0)
        self.assertEqual(stderr, '')

    def test_013_missing_file(self):
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool(
                os.path.join(self.tmpdir, 'missing'))
        self.assertEqual(retcode, 1)
        copy.assert_not_called()
        self.assertIn('Cannot read', stderr)

    def test_014_empty_input(self):
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool(stdin=b'')
        self.assertEqual(retcode, 1)
        copy.assert_not_called()
        self.assertIn('empty', stderr)

    def test_015_reject_binary(self):
        for data in (b'text\0with null', b'\xff\xfe not utf-8',
                'żółw'.encode('utf-16')):
            with self.subTest(data=data), \
                    unittest.mock.patch.object(qubesclipboard,
                        'copy_to_global_clipboard') as copy:
                retcode, stderr = self.run_tool(stdin=data)
                self.assertEqual(retcode, 2)
                copy.assert_not_called()
                self.assertIn('invalid UTF-8', stderr)

    def test_016_too_big(self):
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard') as copy:
            retcode, stderr = self.run_tool(stdin=b'x' * (MAX_SIZE + 1))
        self.assertEqual(retcode, 3)
        copy.assert_not_called()
        self.assertIn('--truncate', stderr)

    def test_017_truncate(self):
        cases = [
            # cut exactly at a character boundary
            (b'x' * (MAX_SIZE + 100), b'x' * MAX_SIZE),
            # 3-byte character starting at the last byte would be split
            (b'x' * (MAX_SIZE - 1) + '€uro'.encode('utf-8'),
             b'x' * (MAX_SIZE - 1)),
            # 2-byte character ending exactly at the limit fits
            (b'x' * (MAX_SIZE - 2) + 'ł'.encode('utf-8') + b'x',
             b'x' * (MAX_SIZE - 2) + 'ł'.encode('utf-8')),
        ]
        for data, expected in cases:
            with self.subTest(size=len(data)), \
                    unittest.mock.patch.object(qubesclipboard,
                        'copy_to_global_clipboard') as copy:
                retcode, stderr = self.run_tool('--truncate', stdin=data)
                self.assertEqual(retcode, 0)
                copy.assert_called_once_with(expected)
                self.assertIn(
                    'truncated to {} bytes'.format(len(expected)), stderr)

    def test_018_write_error(self):
        with unittest.mock.patch.object(qubesclipboard,
                'copy_to_global_clipboard',
                side_effect=PermissionError('denied')):
            retcode, stderr = self.run_tool(stdin=b'text')
        self.assertEqual(retcode, 1)
        self.assertIn('Cannot write to the global clipboard: denied', stderr)

    def test_020_end_to_end(self):
        """Run the tool against real files, without mocking the writer"""
        retcode, stderr = self.run_tool('-q', stdin=b'hello')
        self.assertEqual(retcode, 0)
        self.assertEqual(stderr, '')
        self.assertEqual(self.read_file('qubes-clipboard.bin'), b'hello')
        self.assertEqual(self.read_file('qubes-clipboard.bin.source'),
            b'dom0')
        self.assertEqual(json.loads(self.read_metadata())['sent_size'], 5)


def list_tests():
    return (TC_00_Clipboard,)

if __name__ == '__main__':
    unittest.main()
