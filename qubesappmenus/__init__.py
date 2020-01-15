#!/usr/bin/python3
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2013  Marek Marczykowski <marmarek@invisiblethingslab.com>
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

'''Handle menu entries for starting applications in qubes'''

import subprocess
import sys
import os
import os.path
import shutil
import logging

import itertools
import pkg_resources
import xdg.BaseDirectory

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.vm

import qubesimgconverter


basedir = os.path.join(xdg.BaseDirectory.xdg_data_home, 'qubes-appmenus')

class DispvmNotSupportedError(qubesadmin.exc.QubesException):
    '''Creating Disposable VM menu entries not supported by this template'''
    def __init__(self, msg=None):
        if msg is None:
            msg = 'Creating Disposable VM menu entries ' \
                  'not supported by this template'
            super(DispvmNotSupportedError, self).__init__(msg)


class AppmenusSubdirs:
    '''Common directory names'''
    # pylint: disable=too-few-public-methods
    templates_subdir = 'apps.templates'
    template_icons_subdir = 'apps.tempicons'
    subdir = 'apps'
    icons_subdir = 'apps.icons'
    template_templates_subdir = 'apps-template.templates'
    whitelist = 'whitelisted-appmenus.list'


class Appmenus(object):
    '''Main class for menu entries handling'''
    def templates_dirs(self, vm):
        """

        :type vm: qubes.vm.qubesvm.QubesVM
        """
        dirs = []
        my_dir = os.path.join(basedir, vm.name,
            AppmenusSubdirs.templates_subdir)
        dirs.append(my_dir)
        if hasattr(vm, 'template'):
            dirs.extend(self.templates_dirs(vm.template))
        return dirs

    def template_icons_dirs(self, vm):
        '''Directory for not yet colore icons'''
        dirs = []
        my_dir = os.path.join(basedir, vm.name,
            AppmenusSubdirs.template_icons_subdir)
        dirs.append(my_dir)
        if hasattr(vm, 'template'):
            dirs.extend(self.template_icons_dirs(vm.template))
        return dirs

    @staticmethod
    def template_for_file(template_dirs, name):
        '''Find first template named *name* in *template_dirs*'''
        for tpl_dir in template_dirs:
            path = os.path.join(tpl_dir, name)
            if os.path.exists(path):
                return path

    @staticmethod
    def appmenus_dir(vm):
        '''Desktop files generated for particular VM'''
        return os.path.join(basedir, str(vm), AppmenusSubdirs.subdir)

    @staticmethod
    def icons_dir(vm):
        '''Icon files generated (colored) for particular VM'''
        return os.path.join(basedir, str(vm), AppmenusSubdirs.icons_subdir)

    @staticmethod
    def whitelist_path(vm):
        '''File listing files wanted in menu'''
        return os.path.join(basedir, str(vm), AppmenusSubdirs.whitelist)

    @staticmethod
    def directory_template_name(vm, dispvm):
        '''File name of desktop directory entry template'''
        if dispvm:
            return 'qubes-dispvm.directory.template'
        if vm.klass == 'TemplateVM':
            return 'qubes-templatevm.directory.template'
        if vm.provides_network:
            return 'qubes-servicevm.directory.template'
        return 'qubes-vm.directory.template'

    @staticmethod
    def write_desktop_file(vm, source, destination_path, dispvm=False):
        """Format .desktop/.directory file

        :param vm: QubesVM object for which write desktop file
        :param source: desktop file template (path or template itself)
        :param destination_path: where to write the desktop file
        :param dispvm: create entries for launching in DispVM
        :return: True if target file was changed, otherwise False
        """
        if source.startswith('/'):
            with open(source) as f_source:
                source = f_source.read()
        if dispvm:
            if '\nX-Qubes-DispvmExec=' not in source and '\nExec=' in source:
                raise DispvmNotSupportedError()
            source = source.\
                replace('\nExec=', '\nX-Qubes-NonDispvmExec=').\
                replace('\nX-Qubes-DispvmExec=', '\nExec=')
        icon = vm.label.icon
        if dispvm:
            icon = icon.replace('appvm-', 'dispvm-')
        data = source.\
            replace("%VMNAME%", vm.name).\
            replace("%VMDIR%", os.path.join(basedir, vm.name)).\
            replace("%XDGICON%", icon)
        if os.path.exists(destination_path):
            with open(destination_path) as dest_f:
                current_dest = dest_f.read()
                if current_dest == data:
                    return False
        with open(destination_path, "w") as dest_f:
            dest_f.write(data)
        return True

    def get_available_filenames(self, vm):
        '''Yield filenames of available .desktop files'''
        templates_dirs = self.templates_dirs(vm)
        templates_dirs = (x for x in templates_dirs if os.path.isdir(x))
        if not templates_dirs:
            return

        listed = set()
        for template_dir in templates_dirs:
            for filename in os.listdir(template_dir):
                if filename in listed:
                    continue
                listed.add(filename)
                yield os.path.join(template_dir, filename)

    def get_available(self, vm, fields=None):
        '''Get available menu entries for given VM

        Returns a generator of lists that contain fields to be outputted'''
        # TODO icon path (#2885)
        for filename in self.get_available_filenames(vm):
            field_values = {}
            with open(filename) as file:
                name = None
                main_section = False
                for line in file:
                    if line.startswith('['):
                        main_section = line == '[Desktop Entry]\n'
                        continue
                    if not main_section:
                        continue
                    if '=' not in line:
                        continue
                    if line.startswith('Name=%VMNAME%: '):
                        name = line.partition('Name=%VMNAME%: ')[2].strip()
                        if not fields:
                            break
                    if fields:
                        [field_name, value] = \
                            [x.strip() for x in line.split('=', 1)]
                        if field_name in fields:
                            field_values[field_name] = value
            assert name is not None, \
                'template {!r} does not contain name'.format(filename)
            result = [os.path.basename(filename), name]
            if fields:
                for field in fields:
                    result.append(field_values.get(field, ''))
            yield result

    def appmenus_create(self, vm, force=False, refresh_cache=True):
        """Create/update .desktop files

        :param vm: QubesVM object for which create entries
        :param refresh_cache: refresh desktop environment cache; if false,
        must be refreshed manually later
        :param force: force re-registering files even if unchanged
        :return: None
        """

        if vm.features.get('internal', False):
            return
        if vm.klass == 'DispVM' and vm.auto_cleanup:
            return

        if hasattr(vm, 'log'):
            vm.log.info("Creating appmenus")
        appmenus_dir = self.appmenus_dir(vm)
        if not os.path.exists(appmenus_dir):
            os.makedirs(appmenus_dir)

        dispvm = vm.features.check_with_template('appmenus-dispvm', False)

        anything_changed = False
        directory_changed = False
        directory_file = os.path.join(appmenus_dir, vm.name + '-vm.directory')
        if self.write_desktop_file(vm,
                pkg_resources.resource_string(__name__,
                    self.directory_template_name(vm, dispvm)).decode(),
                directory_file,
                dispvm):
            anything_changed = True
            directory_changed = True
        appmenus = list(self.get_available_filenames(vm))
        changed_appmenus = []
        if os.path.exists(self.whitelist_path(vm)):
            with open(self.whitelist_path(vm)) as whitelist_f:
                whitelist = [x.rstrip() for x in whitelist_f]
            appmenus = [x for x in appmenus if os.path.basename(x) in whitelist]

        for appmenu in appmenus:
            appmenu_basename = os.path.basename(appmenu)
            if self.write_desktop_file(vm,
                    appmenu,
                    os.path.join(appmenus_dir,
                        '-'.join((vm.name, appmenu_basename))),
                    dispvm):
                changed_appmenus.append(appmenu_basename)
        if self.write_desktop_file(vm,
                pkg_resources.resource_string(
                    __name__, 'qubes-vm-settings.desktop.template'
                ).decode(),
                os.path.join(appmenus_dir,
                    '-'.join((vm.name, 'qubes-vm-settings.desktop')))):
            changed_appmenus.append('qubes-vm-settings.desktop')

        if changed_appmenus:
            anything_changed = True

        target_appmenus = ['-'.join((vm.name, os.path.basename(x)))
            for x in appmenus + ['qubes-vm-settings.desktop']]

        # remove old entries
        installed_appmenus = os.listdir(appmenus_dir)
        installed_appmenus.remove(os.path.basename(directory_file))
        appmenus_to_remove = set(installed_appmenus).difference(set(
            target_appmenus))
        if appmenus_to_remove:
            appmenus_to_remove_fnames = [os.path.join(appmenus_dir, x)
                for x in appmenus_to_remove]
            try:
                desktop_menu_cmd = ['xdg-desktop-menu', 'uninstall']
                if not refresh_cache:
                    desktop_menu_cmd.append('--noupdate')
                desktop_menu_cmd.extend(appmenus_to_remove_fnames)
                desktop_menu_env = os.environ.copy()
                desktop_menu_env['LC_COLLATE'] = 'C'
                subprocess.check_call(desktop_menu_cmd, env=desktop_menu_env)
            except subprocess.CalledProcessError:
                vm.log.warning("Problem removing old appmenus")

            for appmenu in appmenus_to_remove_fnames:
                try:
                    os.unlink(appmenu)
                except FileNotFoundError:
                    pass

        # add new entries
        if anything_changed or force:
            try:
                desktop_menu_cmd = ['xdg-desktop-menu', 'install']
                if not refresh_cache:
                    desktop_menu_cmd.append('--noupdate')
                desktop_menu_cmd.append(directory_file)
                if (directory_changed and not changed_appmenus) or force:
                    # only directory file changed, not actual entries;
                    # re-register all of them to force refresh
                    desktop_menu_cmd.extend(
                        os.path.join(appmenus_dir, x)
                        for x in target_appmenus)
                else:
                    desktop_menu_cmd.extend(
                        os.path.join(appmenus_dir, '-'.join((vm.name, x)))
                        for x in changed_appmenus)
                desktop_menu_env = os.environ.copy()
                desktop_menu_env['LC_COLLATE'] = 'C'
                subprocess.check_call(desktop_menu_cmd, env=desktop_menu_env)
            except subprocess.CalledProcessError:
                vm.log.warning("Problem creating appmenus for %s", vm.name)

        if refresh_cache:
            if 'KDE_SESSION_UID' in os.environ:
                subprocess.call(['kbuildsycoca' +
                                 os.environ.get('KDE_SESSION_VERSION', '4')])

    def appmenus_remove(self, vm, refresh_cache=True):
        '''Remove desktop files for particular VM

        Warning: vm may be either QubesVM object, or just its name (str).
        Actual VM may be already removed at this point.
        '''
        appmenus_dir = self.appmenus_dir(vm)
        if os.path.exists(appmenus_dir):
            if hasattr(vm, 'log'):
                vm.log.info("Removing appmenus")
            else:
                if logging.root.getEffectiveLevel() <= logging.INFO:
                    print("Removing appmenus for {!s}".format(vm),
                        file=sys.stderr)
            installed_appmenus = os.listdir(appmenus_dir)
            directory_file = os.path.join(self.appmenus_dir(vm),
                str(vm) + '-vm.directory')
            installed_appmenus.remove(os.path.basename(directory_file))
            if installed_appmenus:
                appmenus_to_remove_fnames = [os.path.join(appmenus_dir, x)
                    for x in installed_appmenus]
                try:
                    desktop_menu_cmd = ['xdg-desktop-menu', 'uninstall']
                    if not refresh_cache:
                        desktop_menu_cmd.append('--noupdate')
                    desktop_menu_cmd.append(directory_file)
                    desktop_menu_cmd.extend(appmenus_to_remove_fnames)
                    desktop_menu_env = os.environ.copy()
                    desktop_menu_env['LC_COLLATE'] = 'C'
                    subprocess.check_call(desktop_menu_cmd,
                        env=desktop_menu_env)
                except subprocess.CalledProcessError:
                    if hasattr(vm, 'log'):
                        vm.log.warning(
                            "Problem removing appmenus for %s", vm.name)

                    else:
                        print(
                            "Problem removing appmenus for {!s}".format(vm),
                            file=sys.stderr)
            shutil.rmtree(appmenus_dir)

        if refresh_cache:
            if 'KDE_SESSION_UID' in os.environ:
                subprocess.call(['kbuildsycoca' +
                                 os.environ.get('KDE_SESSION_VERSION', '4')])

    def appicons_create(self, vm, srcdirs=(), force=False):
        """Create/update applications icons"""
        if not srcdirs:
            srcdirs = self.template_icons_dirs(vm)
        if not srcdirs:
            return

        if vm.features.get('internal', False):
            return
        if vm.klass == 'DispVM' and vm.auto_cleanup:
            return

        whitelist = self.whitelist_path(vm)
        if os.path.exists(whitelist):
            with open(whitelist) as whitelist_f:
                whitelist = [line.strip() for line in whitelist_f]
        else:
            whitelist = None

        dstdir = self.icons_dir(vm)
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
        elif not os.path.isdir(dstdir):
            os.unlink(dstdir)
            os.makedirs(dstdir)

        if whitelist:
            expected_icons = [os.path.splitext(x)[0] + '.png'
                for x in whitelist]
        else:
            expected_icons = list(itertools.chain.from_iterable(
                os.listdir(srcdir)
                for srcdir in srcdirs
                if os.path.exists(srcdir)))

        for icon in expected_icons:
            src_icon = self.template_for_file(srcdirs, icon)
            if not src_icon:
                continue

            dst_icon = os.path.join(dstdir, icon)
            if not os.path.exists(dst_icon) or force or \
                    os.path.getmtime(src_icon) > os.path.getmtime(dst_icon):
                qubesimgconverter.tint(src_icon, dst_icon, vm.label.color)

        for icon in os.listdir(dstdir):
            if icon not in expected_icons:
                os.unlink(os.path.join(dstdir, icon))

    def appicons_remove(self, vm):
        '''Remove icons

        Warning: vm may be either QubesVM object, or just its name (str).
        Actual VM may be already removed at this point.
        '''
        if not os.path.exists(self.icons_dir(vm)):
            return
        shutil.rmtree(self.icons_dir(vm))

    def appmenus_init(self, vm, src=None):
        '''Initialize directory structure on VM creation, copying appropriate
        data from VM template if necessary

        :param src: source VM to copy data from
        '''
        os.makedirs(os.path.join(basedir, vm.name), exist_ok=True)
        clone_from_src = src is not None
        if src is None:
            try:
                src = vm.template
            except AttributeError:
                pass
        own_templates_dir = os.path.join(basedir, vm.name,
                AppmenusSubdirs.templates_subdir)
        own_template_icons_dir = os.path.join(basedir, vm.name,
                AppmenusSubdirs.template_icons_subdir)
        if src is None:
            os.makedirs(own_templates_dir, exist_ok=True)
            os.makedirs(os.path.join(basedir, vm.name,
                AppmenusSubdirs.template_icons_subdir), exist_ok=True)

        if src is None:
            vm.log.info("Creating appmenus directory: {0}".format(
                own_templates_dir))
            with open(
                    os.path.join(own_templates_dir, 'qubes-start.desktop'),
                    'wb') as qubes_start_f:
                qubes_start_f.write(pkg_resources.resource_string(__name__,
                    'qubes-start.desktop.template'))

        source_whitelist_filename = 'vm-' + AppmenusSubdirs.whitelist
        if src and os.path.exists(
                os.path.join(basedir, src.name, source_whitelist_filename)):
            vm.log.info("Creating default whitelisted apps list: {0}".
                    format(basedir + '/' + vm.name + '/' +
                           AppmenusSubdirs.whitelist))
            shutil.copy(
                os.path.join(basedir, src.name, source_whitelist_filename),
                os.path.join(basedir, vm.name, AppmenusSubdirs.whitelist))

        if clone_from_src:
            for whitelist in (
                    AppmenusSubdirs.whitelist,
                        'vm-' + AppmenusSubdirs.whitelist,
                        'netvm-' + AppmenusSubdirs.whitelist):
                if os.path.exists(os.path.join(basedir, src.name, whitelist)):
                    vm.log.info("Copying whitelisted apps list: {0}".
                        format(whitelist))
                    shutil.copy(os.path.join(basedir, src.name, whitelist),
                        os.path.join(basedir, vm.name, whitelist))

            vm.log.info("Creating/copying appmenus templates")
            src_dir = self.templates_dirs(src)[0]
            if os.path.isdir(src_dir):
                os.makedirs(own_templates_dir, exist_ok=True)
                for filename in os.listdir(src_dir):
                    shutil.copy(os.path.join(src_dir, filename),
                        own_templates_dir)
            src_dir = self.template_icons_dirs(src)[0]
            if os.path.isdir(src_dir):
                os.makedirs(own_template_icons_dir, exist_ok=True)
                for filename in os.listdir(src_dir):
                    shutil.copy(os.path.join(src_dir, filename),
                        own_template_icons_dir)

    @staticmethod
    def set_default_whitelist(vm, applications_list):
        '''Update default applications list for VMs created on this template

        :param vm: VM object
        :param applications_list: list of applications to include
        '''
        if not os.path.exists(os.path.join(basedir, vm.name)):
            return
        with open(os.path.join(basedir, str(vm),
                        'vm-' + AppmenusSubdirs.whitelist), 'w') as \
                default_whitelist:
            default_whitelist.write('\n'.join(applications_list))

    def set_whitelist(self, vm, applications_list):
        '''Update list of applications to be included in the menu

        :param vm: VM object
        :param applications_list: list of applications to include
        '''
        if not os.path.exists(os.path.join(basedir, vm.name)):
            return
        with open(self.whitelist_path(vm), 'w') as whitelist:
            whitelist.write('\n'.join(applications_list))

    def get_whitelist(self, vm):
        '''Retrieve list of applications to be included in the menu

        :param vm: VM object
        :return: list of applications (.desktop file names), or None if not set
        '''
        if not os.path.exists(self.whitelist_path(vm)):
            return None
        with open(self.whitelist_path(vm), 'r') as whitelist:
            for line in whitelist:
                line = line.strip()
                if not line:
                    continue
                yield line

    def appmenus_update(self, vm, force=False):
        '''Update (regenerate) desktop files and icons for this VM and (in
        case of template) child VMs'''
        self.appicons_create(vm, force=force)
        self.appmenus_create(vm, force=force, refresh_cache=False)
        if hasattr(vm, 'appvms'):
            for child_vm in vm.appvms:
                try:
                    self.appicons_create(child_vm, force=force)
                    self.appmenus_create(child_vm, refresh_cache=False)
                except Exception as e:  # pylint: disable=broad-except
                    child_vm.log.error("Failed to recreate appmenus for "
                                       "'{0}': {1}".format(child_vm.name,
                        str(e)))
        subprocess.call(['xdg-desktop-menu', 'forceupdate'])
        if 'KDE_SESSION_UID' in os.environ:
            subprocess.call([
                'kbuildsycoca' + os.environ.get('KDE_SESSION_VERSION', '4')])

parser = qubesadmin.tools.QubesArgumentParser()

parser_stdin_mode = parser.add_mutually_exclusive_group()

parser.add_argument('--init', action='store_true',
    help='Initialize directory structure for appmenus (on VM creation)')
parser.add_argument('--create', action='store_true',
    help='Create appmenus')
parser.add_argument('--remove', action='store_true',
    help='Remove appmenus')
parser.add_argument('--update', action='store_true',
    help='Update appmenus')
parser.add_argument('--get-available', action='store_true',
    help='Get list of applications available')
parser.add_argument('--get-whitelist', action='store_true',
    help='Get list of applications to include in the menu')
parser_stdin_mode.add_argument('--set-whitelist', metavar='PATH',
    action='store',
    help='Set list of applications to include in the menu,'
         'use \'-\' to read from stdin')
parser_stdin_mode.add_argument('--set-default-whitelist', metavar='PATH',
    action='store',
    help='Set default list of applications to include in menu '
         'for VMs based on this template,'
         'use \'-\' to read from stdin')
parser.add_argument('--source', action='store', default=None,
    help='Source VM to copy data from (for --init option)')
parser.add_argument('--force', action='store_true', default=False,
    help='Force refreshing files, even when looks up to date')
parser.add_argument('--i-understand-format-is-unstable', dest='fool',
    action='store_true',
    help='required pledge for --get-available')
parser.add_argument('domains', metavar='VMNAME', nargs='+',
    help='VMs on which perform requested actions')
parser.add_argument('--file-field', action='append', dest='fields',
    help='File field to append to output for --get-available; can be used'
         ' multiple times for multiple fields. This option changes output'
         ' format to pipe-("|") separated.')


def retrieve_list(path):
    '''Helper function to retrieve data from given path, or stdin if '-'
    specified, then return it as a list of lines.

    :param path: path or '-'
    :return: list of lines
    '''
    if path == '-':
        return sys.stdin.readlines()
    with open(path, 'r') as file:
        return file.readlines()


def main(args=None, app=None):
    '''main function for qvm-appmenus tool'''
    args = parser.parse_args(args=args, app=app)
    appmenus = Appmenus()
    if args.source is not None:
        args.source = args.app.domains[args.source]
    for vm in args.domains:
        # allow multiple actions
        # for remove still use just VM name (str), because VM may be already
        # removed
        if args.remove:
            appmenus.appmenus_remove(vm)
            appmenus.appicons_remove(vm)
            try:
                shutil.rmtree(os.path.join(basedir, str(vm)))
            except FileNotFoundError:
                pass
        # for other actions - get VM object
        if not args.remove:
            vm = args.app.domains[vm]
            if args.init:
                appmenus.appmenus_init(vm, src=args.source)
            if args.get_whitelist:
                whitelist = appmenus.get_whitelist(vm)
                print('\n'.join(whitelist))
            if args.set_default_whitelist:
                whitelist = retrieve_list(args.set_default_whitelist)
                appmenus.set_default_whitelist(vm, whitelist)
            if args.set_whitelist:
                whitelist = retrieve_list(args.set_whitelist)
                appmenus.set_whitelist(vm, whitelist)
            if args.create:
                appmenus.appicons_create(vm, force=args.force)
                appmenus.appmenus_create(vm)
            if args.update:
                appmenus.appmenus_update(vm, force=args.force)
            if args.get_available:
                if not args.fool:
                    parser.error(
                        'this requires --i-understand-format-is-unstable '
                        'and a sacrifice of one cute kitten')
                if not args.fields:
                    sys.stdout.write(''.join('{} - {}\n'.format(*available)
                                             for available in
                                             appmenus.get_available(vm)))
                else:
                    for result in appmenus.get_available(
                            vm, fields=args.fields):
                        print('|'.join(result))


if __name__ == '__main__':
    sys.exit(main())
