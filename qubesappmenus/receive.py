#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2011  Marek Marczykowski <marmarek@mimuw.edu.pl>
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
#

'''Retrieve menu entries from a VM and convert to appmenu templates'''

import re
import os
import sys
import pipes
import pkg_resources

import qubesadmin.exc
import qubesadmin.tools
import qubesappmenus

import qubesimgconverter

parser = qubesadmin.tools.QubesArgumentParser(
    vmname_nargs='?',
    description='retrieve appmenus')

parser.add_argument('--force-rpc',
    action='store_true', default=False,
    help="Force to start a new RPC call, even if called from existing one")

parser.add_argument('--regenerate-only',
    action='store_true', default=False,
    help='Only regenerate appmenus entries, do not synchronize with system '
         'in template')

# qubesadmin.tools.QubesArgumentParser already adds it (but with supressed help)
#parser.add_argument(
#    '--force-root', action='store',
#    help='Use to force the tool to be run as root. Not recommended.'
#)

# TODO offline mode

# fields required to be present (and verified) in retrieved desktop file
required_fields_legacy = ["Name", "Exec"]
required_fields = ["Name"]

# limits
appmenus_line_size = 1024
appmenus_line_count = 100000

# regexps for sanitization of retrieved values
std_re = re.compile(r"^[/a-zA-Z0-9.,:&()_ -]*$")
fields_regexp = {
    "Name": std_re,
    "GenericName": std_re,
    "Comment": std_re,
    "Categories": re.compile(r"^[a-zA-Z0-9/.;:'() -]*$"),
    "Exec": re.compile(r"^[a-zA-Z0-9()_&>/{}:.= -]*$"),
    "Icon": re.compile(r"^[a-zA-Z0-9/_.-]*$"),
}

CATEGORIES_WHITELIST = {
    # Main Categories
    # http://standards.freedesktop.org/menu-spec/1.1/apa.html 20140507
    'AudioVideo', 'Audio', 'Video', 'Development', 'Education', 'Game',
    'Graphics', 'Network', 'Office', 'Science', 'Settings', 'System',
    'Utility',

    # Additional Categories
    # http://standards.freedesktop.org/menu-spec/1.1/apas02.html
    'Building', 'Debugger', 'IDE', 'GUIDesigner', 'Profiling',
    'RevisionControl', 'Translation', 'Calendar', 'ContactManagement',
    'Database', 'Dictionary', 'Chart', 'Email', 'Finance', 'FlowChart', 'PDA',
    'ProjectManagement', 'Presentation', 'Spreadsheet', 'WordProcessor',
    '2DGraphics', 'VectorGraphics', 'RasterGraphics', '3DGraphics', 'Scanning',
    'OCR', 'Photography', 'Publishing', 'Viewer', 'TextTools',
    'DesktopSettings', 'HardwareSettings', 'Printing', 'PackageManager',
    'Dialup', 'InstantMessaging', 'Chat', 'IRCClient', 'Feed', 'FileTransfer',
    'HamRadio', 'News', 'P2P', 'RemoteAccess', 'Telephony', 'TelephonyTools',
    'VideoConference', 'WebBrowser', 'WebDevelopment', 'Midi', 'Mixer',
    'Sequencer', 'Tuner', 'TV', 'AudioVideoEditing', 'Player', 'Recorder',
    'DiscBurning', 'ActionGame', 'AdventureGame', 'ArcadeGame', 'BoardGame',
    'BlocksGame', 'CardGame', 'KidsGame', 'LogicGame', 'RolePlaying',
    'Shooter', 'Simulation', 'SportsGame', 'StrategyGame', 'Art',
    'Construction', 'Music', 'Languages', 'ArtificialIntelligence',
    'Astronomy', 'Biology', 'Chemistry', 'ComputerScience',
    'DataVisualization', 'Economy', 'Electricity', 'Geography', 'Geology',
    'Geoscience', 'History', 'Humanities', 'ImageProcessing', 'Literature',
    'Maps', 'Math', 'NumericalAnalysis', 'MedicalSoftware', 'Physics',
    'Robotics', 'Spirituality', 'Sports', 'ParallelComputing', 'Amusement',
    'Archiving', 'Compression', 'Electronics', 'Emulator', 'Engineering',
    'FileTools', 'FileManager', 'TerminalEmulator', 'Filesystem', 'Monitor',
    'Security', 'Accessibility', 'Calculator', 'Clock', 'TextEditor',
    'Documentation', 'Adult', 'Core', 'KDE', 'GNOME', 'XFCE', 'GTK', 'Qt',
    'Motif', 'Java', 'ConsoleOnly',

    # Reserved Categories (not whitelisted)
    # http://standards.freedesktop.org/menu-spec/1.1/apas03.html
    # 'Screensaver', 'TrayIcon', 'Applet', 'Shell',
}


def sanitise_categories(untrusted_value):
    '''Sanitise Categories= entry of desktop file.
    Allow only categories explicitly listed by the specification
    '''
    untrusted_categories = (c.strip() for c in untrusted_value.split(';') if c)
    categories = (c for c in untrusted_categories if c in CATEGORIES_WHITELIST)

    return ';'.join(categories) + ';'


def get_appmenus(vm):
    '''Get appmenus from a *vm*. *vm* can be :py:obj:None to retrieve data
    from stdin - should be a `qubes.GetAppmenus` service in the VM connected
    to it.'''
    appmenus_line_limit_left = appmenus_line_count
    untrusted_appmenulist = []
    if vm is None:
        while appmenus_line_limit_left > 0:
            untrusted_line = sys.stdin.readline(appmenus_line_size)
            if not untrusted_line:
                break
            untrusted_appmenulist.append(untrusted_line.strip())
            appmenus_line_limit_left -= 1
        if appmenus_line_limit_left == 0:
            raise qubesadmin.exc.QubesException("Line count limit exceeded")
    else:
        p = vm.run_service('qubes.GetAppmenus')
        while appmenus_line_limit_left > 0:
            untrusted_line = p.stdout.readline(appmenus_line_size)
            if not untrusted_line:
                break
            try:
                untrusted_line = untrusted_line.decode('ascii')
                untrusted_appmenulist.append(untrusted_line.strip())
            except UnicodeDecodeError:
                # simply ignore non-ASCII lines
                pass
            appmenus_line_limit_left -= 1
        p.wait()
        p.stdout.close()
        if p.returncode != 0:
            raise qubesadmin.exc.QubesException(
                "Error getting application list")
        if appmenus_line_limit_left == 0:
            raise qubesadmin.exc.QubesException("Line count limit exceeded")

    appmenus = {}
    line_rx = re.compile(
        r"([a-zA-Z0-9._-]+?)(?:\.desktop)?:"
        r"([a-zA-Z0-9-]+(?:\[[a-zA-Z@_]+\])?)\s*=\s*(.*)")
    ignore_rx = re.compile(r".*([a-zA-Z0-9._-]+.desktop):(#.*|\s*)$")
    for untrusted_line in untrusted_appmenulist:
        # Ignore blank lines and comments
        if not untrusted_line or ignore_rx.match(untrusted_line):
            continue
        # use search instead of match to skip file path
        untrusted_m = line_rx.search(untrusted_line)
        if untrusted_m:
            name = untrusted_m.group(1)
            assert '/' not in name
            assert '\0' not in name

            untrusted_key = untrusted_m.group(2)
            assert '\0' not in untrusted_key
            assert '\x1b' not in untrusted_key
            assert '=' not in untrusted_key

            untrusted_value = untrusted_m.group(3).strip()
            # TODO add key-dependent asserts

            # Look only at predefined keys
            if untrusted_key in fields_regexp:
                if fields_regexp[untrusted_key].match(untrusted_value):
                    # now values are sanitized
                    key = untrusted_key
                    if key == 'Categories':
                        value = sanitise_categories(untrusted_value)
                    else:
                        value = untrusted_value

                    if name not in appmenus:
                        appmenus[name] = {}

                    appmenus[name][key] = value
                else:
                    print("Warning: ignoring key %r of %s" %
                        (untrusted_key, name), file=sys.stderr)
            # else: ignore this key

    return appmenus


def create_template(path, name, values, legacy):
    '''
    Create desktop entry template based on values in `values` and save it to
    `path`.
    :param path: Path where template should be saved
    :param values: dict with values retrieved from VM (as in Desktop Entry
    specification)
    :param legacy: create legacy template, for VM without qubes.StartApp service
    :return: None
    '''
    # check if all required fields are present
    if legacy:
        req_fields = required_fields_legacy
    else:
        req_fields = required_fields
    for key in req_fields:
        if key not in values:
            print("Warning: not creating/updating '%s' "
                  "because of missing '%s' key" % (path, key),
                  file=sys.stderr)
            return

    desktop_entry = ""
    desktop_entry += "[Desktop Entry]\n"
    desktop_entry += "Version=1.0\n"
    desktop_entry += "Type=Application\n"
    desktop_entry += "Terminal=false\n"
    desktop_entry += "X-Qubes-VmName=%VMNAME%\n"

    if 'Icon' in values:
        icon_file = os.path.splitext(os.path.split(path)[1])[0] + '.png'
        desktop_entry += "Icon={0}\n".format(os.path.join(
            '%VMDIR%', qubesappmenus.AppmenusSubdirs.icons_subdir, icon_file))
    else:
        desktop_entry += "Icon=%XDGICON%\n"

    for key in ["Name", "GenericName"]:
        if key in values:
            desktop_entry += "{0}=%VMNAME%: {1}\n".format(key, values[key])

    # force category X-Qubes-VM
    values["Categories"] = values.get("Categories", "") + "X-Qubes-VM;"

    for key in ["Comment", "Categories"]:
        if key in values:
            desktop_entry += "{0}={1}\n".format(key, values[key])

    if legacy:
        desktop_entry += "Exec=qvm-run -q -a %VMNAME% -- {0}\n".format(
            pipes.quote(values['Exec']))
        desktop_entry += \
            "X-Qubes-DispvmExec=qvm-run -q -a --dispvm=%VMNAME% -- {0}\n".\
            format(pipes.quote(values['Exec']))
    else:
        # already validated before, but make sure no one will break it
        assert ' ' not in name
        assert ';' not in name
        assert '%' not in name
        desktop_entry += "Exec=qvm-run -q -a --service -- %VMNAME% " \
                         "qubes.StartApp+{}\n".format(name)
        desktop_entry += \
            "X-Qubes-DispvmExec=qvm-run -q -a --service --dispvm=%VMNAME% " \
            "-- qubes.StartApp+{}\n".format(name)
    if not os.path.exists(path) or desktop_entry != open(path, "r").read():
        desktop_file = open(path, "w")
        desktop_file.write(desktop_entry)
        desktop_file.close()


def process_appmenus_templates(appmenusext, vm, appmenus):
    '''Get parsed appmenus and write appmenus templates from them.

    :param appmenusext: AppmenusExtension instance
    :param vm: VM from which appmenus were extracted
    :param appmenus: appmenus dictionary, indexed with entry basename
    '''
    old_umask = os.umask(0o002)

    legacy_appmenus = vm.features.check_with_template(
        'appmenus-legacy', False)

    templates_dir = appmenusext.templates_dirs(vm)[0]
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)

    template_icons_dir = appmenusext.template_icons_dirs(vm)[0]
    if not os.path.exists(template_icons_dir):
        os.makedirs(template_icons_dir)

    # Only create Start shortcut for standalone VMs. Otherwise we will use the
    # one from template VM.
    has_qubes_start = vm.klass != 'AppVM'

    if has_qubes_start:
        qubes_start_fname = os.path.join(templates_dir, 'qubes-start.desktop')
        if not os.path.exists(qubes_start_fname):
            with open(qubes_start_fname, 'wb') as qubes_start_f:
                vm.log.info("Creating Start")
                qubes_start_f.write(pkg_resources.resource_string(
                    __name__,
                    'qubes-start.desktop.template'))

    for appmenu_name in appmenus.keys():
        appmenu_path = os.path.join(
            templates_dir,
            appmenu_name) + '.desktop'
        if os.path.exists(appmenu_path):
            vm.log.info("Updating {0}".format(appmenu_name))
        else:
            vm.log.info("Creating {0}".format(appmenu_name))

        # TODO: icons support in offline mode
        # TODO if options.offline_mode:
        # TODO     new_appmenus[appmenu_name].pop('Icon', None)
        if 'Icon' in appmenus[appmenu_name]:
            # the following line is used for time comparison
            icondest = os.path.join(template_icons_dir,
                                    appmenu_name + '.png')

            try:
                icon = qubesimgconverter.Image. \
                    get_xdg_icon_from_vm(vm, appmenus[appmenu_name]['Icon'])
                if os.path.exists(icondest):
                    old_icon = qubesimgconverter.Image.load_from_file(icondest)
                else:
                    old_icon = None
                if old_icon is None or icon != old_icon:
                    icon.save(icondest)
            except Exception as e:  # pylint: disable=broad-except
                vm.log.warning('Failed to get icon for {0}: {1!s}'.
                    format(appmenu_name, e))

                if os.path.exists(icondest):
                    vm.log.warning('Found old icon, using it instead')
                else:
                    del appmenus[appmenu_name]['Icon']

        create_template(appmenu_path, appmenu_name,
            appmenus[appmenu_name], legacy_appmenus)

    # Delete appmenus of removed applications
    for appmenu_file in os.listdir(templates_dir):
        if not appmenu_file.endswith('.desktop'):
            continue

        # Keep the Start shortcut
        if has_qubes_start and appmenu_file == 'qubes-start.desktop':
            continue

        if appmenu_file[:-len('.desktop')] not in appmenus:
            vm.log.info("Removing {0}".format(appmenu_file))
            os.unlink(os.path.join(templates_dir,
                appmenu_file))

    os.umask(old_umask)


def retrieve_appmenus_templates(vm, use_stdin=True):
    '''Retrieve appmenus from the VM. If not running in offline mode,
    additionally retrieve application icons and store them into
    :py:metch:`template_icons_dir`.

    Returns: dict of desktop entries, each being dict itself.
    '''
    if not vm.is_running():
        raise qubesadmin.exc.QubesVMNotRunningError(
            "Appmenus can be retrieved only from running VM")

    new_appmenus = get_appmenus(vm if not use_stdin else None)

    return new_appmenus


def main(args=None):
    '''Main function of qvm-sync-appmenus tool'''
    env_vmname = os.environ.get("QREXEC_REMOTE_DOMAIN")

    args = parser.parse_args(args)

    if os.getuid() == 0 and not args.force_root:
        parser.error('This tool should not be executed as root. If you are '
                     'absolutely sure you know what you are doing, '
                     'use --force-root')

    if env_vmname:
        vm = args.app.domains[env_vmname]
    elif not args.domains:
        parser.error("You must specify at least the VM name!")
    else:
        vm = args.domains[0]

    if env_vmname is None or args.force_rpc:
        use_stdin = False
    else:
        use_stdin = True
    appmenusext = qubesappmenus.Appmenus()
    if not args.regenerate_only:
        new_appmenus = retrieve_appmenus_templates(vm, use_stdin=use_stdin)
        if not new_appmenus and vm.klass != "AppVM":
            vm.log.info("No appmenus received, terminating")
        else:
            process_appmenus_templates(appmenusext, vm, new_appmenus)
    appmenusext.appmenus_update(vm)
