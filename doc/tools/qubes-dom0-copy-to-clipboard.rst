============================
qubes-dom0-copy-to-clipboard
============================

NAME
====
qubes-dom0-copy-to-clipboard - copy text from dom0 to the Qubes global clipboard

SYNOPSIS
========
| qubes-dom0-copy-to-clipboard [options] [FILE]

DESCRIPTION
===========
qubes-dom0-copy-to-clipboard puts the contents of FILE, or of standard input when FILE is omitted or is a single hyphen ('-'), into the Qubes global clipboard, as if it had been copied from dom0 with the clipboard widget.
The text can then be pasted in any qube with the secure paste shortcut (Ctrl+Shift+V by default).
Unlike the widget it needs no graphical session, so it can be used from a terminal or a script, for example to hand a long log file to a qube for a bug report.

The Qubes clipboard protocol only carries UTF-8 text, so binary data and text in other encodings are rejected; use qvm-copy for those.
Input larger than the clipboard buffer (256000 bytes) is rejected as well, unless --truncate is given.

OPTIONS
=======
--truncate
    Cut input larger than the clipboard buffer to the largest prefix that still ends on a character boundary, instead of failing.

--quiet, -q
    Do not print informational messages.

--help, -h
    Show a help message and exit.

EXIT STATUS
===========
0
    The text was copied.

1
    The input could not be read, was empty, or the clipboard files could not be written.

2
    Invalid arguments, or the input is not UTF-8 text.

3
    The input is larger than the clipboard buffer and --truncate was not given.

AUTHORS
=======
| Akshat Lakhera <akshatlnct2024 at gmail dot com>
