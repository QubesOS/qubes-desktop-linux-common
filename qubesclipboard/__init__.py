#!/usr/bin/python3
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

"""Copy text from dom0 to the Qubes global clipboard.

The global clipboard is a set of files under /var/run/qubes written by
qubes-guid and by the clipboard widget. This module writes them the same
way the widget does for its "Copy dom0 clipboard" action, but without a
graphical session, and provides the qubes-dom0-copy-to-clipboard tool.
"""

import argparse
import contextlib
import fcntl
import json
import os
import sys

DATA = '/var/run/qubes/qubes-clipboard.bin'
METADATA = DATA + '.metadata'
SOURCE = DATA + '.source'
XEVENT = DATA + '.xevent'
APPVIEWER_LOCK = '/var/run/qubes/appviewer.lock'

# GUI protocol 1.8, the first one with the .metadata file
PROTOCOL_VERSION = 0x00010008
# MAX_CLIPBOARD_BUFFER_SIZE from qubes-gui-protocol.h
MAX_CLIPBOARD_SIZE = 256000


@contextlib.contextmanager
def appviewer_lock():
    """Hold the lock qubes-guid and the clipboard widget take around any
    access to the clipboard files."""
    fd = os.open(APPVIEWER_LOCK, os.O_RDWR | os.O_CREAT, 0o0666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def copy_to_global_clipboard(data):
    """Put UTF-8 encoded *data* into the global clipboard as copied from dom0.

    The X event timestamp is 0, since there is no key press behind this
    copy. qubes-guid discards a secure paste older than that timestamp, so
    0 never blocks a paste.
    """
    metadata = {
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
        'buffer_size': MAX_CLIPBOARD_SIZE,
        'protocol_version_xside': PROTOCOL_VERSION,
        'protocol_version_vmside': PROTOCOL_VERSION,
    }

    with appviewer_lock():
        with open(DATA, 'wb') as data_file:
            data_file.write(data)
        with open(XEVENT, 'w', encoding='ascii') as xevent_file:
            xevent_file.write('0')
        # the widget trusts .metadata only if it is newer than the data
        # file, and qubes-guid parses it line by line, one "key":value
        # pair per line without whitespace
        with open(METADATA, 'w', encoding='ascii') as metadata_file:
            metadata_file.write(
                json.dumps(metadata, indent=0, separators=(',', ':')) + '\n')
        # the widget watches the .source file, so write it last
        with open(SOURCE, 'w', encoding='ascii') as source_file:
            source_file.write('dom0')


def is_text(data):
    """Whether *data* is UTF-8 text without null bytes, the only content
    the Qubes clipboard protocol carries."""
    if b'\0' in data:
        return False
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


def truncate_utf8(data, size):
    """Cut valid UTF-8 *data* to at most *size* bytes without splitting a
    character."""
    # step back over continuation bytes (0b10xxxxxx) of a split character
    while size > 0 and data[size] & 0xC0 == 0x80:
        size -= 1
    return data[:size]


def read_input(path):
    """Read the whole of *path*, or of standard input for '-', as bytes."""
    if path == '-':
        return sys.stdin.buffer.read()
    with open(path, 'rb') as input_file:
        return input_file.read()


parser = argparse.ArgumentParser(
    description='Copy text from dom0 to the Qubes global clipboard, then '
                'paste it in a qube with the secure paste shortcut '
                '(Ctrl+Shift+V by default).')
parser.add_argument(
    'file', metavar='FILE', nargs='?', default='-',
    help='file to copy; standard input when omitted or \'-\'')
parser.add_argument(
    '--truncate', action='store_true',
    help='cut input larger than the clipboard buffer ({} bytes) instead of '
         'failing'.format(MAX_CLIPBOARD_SIZE))
parser.add_argument(
    '--quiet', '-q', action='store_true',
    help='do not print informational messages')


def main(args=None):
    """main function for qubes-dom0-copy-to-clipboard tool"""
    args = parser.parse_args(args)

    if args.file == '-' and sys.stdin.isatty() and not args.quiet:
        print('Reading from standard input, press Ctrl+D to finish...',
              file=sys.stderr)
    try:
        data = read_input(args.file)
    except OSError as e:
        print('Cannot read {}: {}'.format(args.file, e), file=sys.stderr)
        return 1

    if not data:
        print('Input is empty, nothing to copy.', file=sys.stderr)
        return 1

    if not is_text(data):
        print('Error: Binary data or invalid UTF-8 detected. The Qubes '
              'clipboard only supports UTF-8 text; use qvm-copy to '
              'transfer files.', file=sys.stderr)
        return 2

    if len(data) > MAX_CLIPBOARD_SIZE:
        if not args.truncate:
            print('Input size ({} bytes) exceeds the clipboard buffer size '
                  '({} bytes). Use qvm-copy to transfer large amounts of '
                  'data, or pass --truncate.'.format(
                      len(data), MAX_CLIPBOARD_SIZE), file=sys.stderr)
            return 3
        data = truncate_utf8(data, MAX_CLIPBOARD_SIZE)
        if not args.quiet:
            print('Input truncated to {} bytes.'.format(len(data)),
                  file=sys.stderr)

    try:
        copy_to_global_clipboard(data)
    except OSError as e:
        print('Cannot write to the global clipboard: {}'.format(e),
              file=sys.stderr)
        return 1

    if not args.quiet:
        print('Copied {} bytes to the global clipboard.'.format(len(data)),
              file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
