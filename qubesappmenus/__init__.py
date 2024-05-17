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

"""Handle menu entries for starting applications in qubes"""
import contextlib
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

def vm_name_escape(vm_name: str) -> str:
    """Escape a VM name for use in a .desktop file name"""
    return ('_' + vm_name.replace('_', '_u')
                         .replace('-', '_d')
                         .replace('.', '_p'))

class DispvmNotSupportedError(qubesadmin.exc.QubesException):
    """Creating Disposable VM menu entries not supported by this template"""

    def __init__(self, msg=None):
        if msg is None:
            msg = 'Creating Disposable VM menu entries ' \
                  'not supported by this template'
            super().__init__(msg)


class AppmenusSubdirs:
    """Common directory names"""
    # pylint: disable=too-few-public-methods
    templates_subdir = 'apps.templates'
    template_icons_subdir = 'apps.tempicons'
    subdir = 'apps'
    icons_subdir = 'apps.icons'
    template_templates_subdir = 'apps-template.templates'
    whitelist = 'whitelisted-appmenus.list'


class Appmenus(object):
    """Main class for menu entries handling"""

    qubes_vm_desktop = 'org.qubes-os.vm'
    qubes_dispvm_desktop = 'org.qubes-os.dispvm'
    qubes_vm_desktop_settings = 'org.qubes-os.qubes-vm-settings'

    def templates_dirs(self, vm, template=None):
        """

        :type vm: qubes.vm.qubesvm.QubesVM
        :type template: qubes.vm.qubesvm.QubesVM
        """
        dirs = []
        my_dir = os.path.join(basedir, vm.name,
                              AppmenusSubdirs.templates_subdir)
        dirs.append(my_dir)
        if template:
            dirs.extend(self.templates_dirs(template))
        elif hasattr(vm, 'template'):
            dirs.extend(self.templates_dirs(vm.template))
        return dirs

    def template_icons_dirs(self, vm):
        """Directory for not yet colore icons"""
        dirs = []
        my_dir = os.path.join(basedir, vm.name,
                              AppmenusSubdirs.template_icons_subdir)
        dirs.append(my_dir)
        if hasattr(vm, 'template'):
            dirs.extend(self.template_icons_dirs(vm.template))
        return dirs

    @staticmethod
    def template_for_file(template_dirs, name):
        """Find first template named *name* in *template_dirs*"""
        for tpl_dir in template_dirs:
            path = os.path.join(tpl_dir, name)
            if os.path.exists(path):
                return path

    @staticmethod
    def appmenus_dir(vm):
        """Desktop files generated for particular VM"""
        return os.path.join(basedir, str(vm), AppmenusSubdirs.subdir)

    @staticmethod
    def icons_dir(vm):
        """Icon files generated (colored) for particular VM"""
        return os.path.join(basedir, str(vm), AppmenusSubdirs.icons_subdir)

    @staticmethod
    def whitelist_path(vm):
        """File listing files wanted in menu"""
        return os.path.join(basedir, str(vm), AppmenusSubdirs.whitelist)

    @staticmethod
    def directory_template_name(vm, dispvm):
        """File name of desktop directory entry template"""
        if dispvm:
            return 'qubes-dispvm.directory.template'
        if getattr(vm, 'template_for_dispvms', False):
            return 'qubes-templatedispvm.directory.template'
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
            with open(source, encoding='utf-8') as f_source:
                source = f_source.read()
        if dispvm:
            if '\nX-Qubes-DispvmExec=' not in source and '\nExec=' in source:
                raise DispvmNotSupportedError()
            source = source. \
                replace('\nExec=', '\nX-Qubes-NonDispvmExec='). \
                replace('\nX-Qubes-DispvmExec=', '\nExec='). \
                replace('\nName=%VMNAME%', '\nName=%VMNAME% (dvm)')
        if dispvm:
            # menu directory for creating new DispVMs is special
            icon = 'dispvm-' + vm.label.name
        else:
            icon = vm.icon
        data = source. \
            replace("%VMNAME%", vm.name). \
            replace("%VMDIR%", os.path.join(basedir, vm.name)). \
            replace("%XDGICON%", icon)
        if os.path.exists(destination_path):
            with open(destination_path, encoding='utf-8') as dest_f:
                current_dest = dest_f.read()
                if current_dest == data:
                    return False
        with open(destination_path, "w", encoding='utf-8') as dest_f:
            dest_f.write(data)
        return True

    def get_available_filenames(self, vm, template=None):
        """Yield filenames of available .desktop files"""
        templates_dirs = self.templates_dirs(vm, template)
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

    def get_available(self, vm, fields=None, template=None):
        """Get available menu entries for given VM

        Returns a generator of lists that contain fields to be outputted"""
        # TODO icon path (#2885)
        for filename in self.get_available_filenames(vm, template):
            field_values = {}
            with open(filename, encoding='utf-8') as file:
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
            if name is None:
                continue
            result = [os.path.basename(filename), name]
            if fields:
                for field in fields:
                    result.append(field_values.get(field, ''))
            yield result

    def desktop_name(self, vm, appmenu_basename: str, dispvm=False):
        """Return the basename of a ``.desktop`` file.

        :param vm: QubesVM object for the VM whose entry this is.
        :param appmenu_basename: The basename of the appmenu, as provided by
        the VM.  This is not marked as “untrusted” as it has already been
        validated.
        """
        assert appmenu_basename.endswith('.desktop')
        if dispvm:
            prefix = self.qubes_dispvm_desktop
        else:
            prefix = self.qubes_vm_desktop
        return '.'.join((prefix, vm_name_escape(str(vm)), appmenu_basename))

    def settings_name(self, vm):
        """Return the basename of the .desktop file for the “Qube Settings”
        menu entry of a given VM..

        :param vm: QubesVM object for the VM.
        """
        return '.'.join((self.qubes_vm_desktop_settings,
                         vm_name_escape(str(vm)),
                         'desktop'))

    def _do_remove_appmenus(self, vm, appmenus_to_remove, appmenus_dir,
            refresh_cache):
        """Remove old appmenus

        :param vm: QubesVM object for the VM.
        :param appmenus_to_remove: List of appmenus to remove.
        :param appmenus_dir: Appmenus directory.
        :param refresh_cache: Refresh the cache?
        """
        old_appmenus = set((fname for fname in appmenus_to_remove
                                  if self._is_old_path(fname)))
        new_appmenus = set(appmenus_to_remove).difference(old_appmenus)

        def _sort_entries(entry):
            return sorted(entry, key=lambda x: not x.endswith('.directory'))

        for bad_menus in (_sort_entries(old_appmenus),
                          _sort_entries(new_appmenus)):
            if bad_menus:
                appmenus_to_remove_fnames = [os.path.join(appmenus_dir, x)
                                             for x in bad_menus]
                try:
                    desktop_menu_cmd = ['xdg-desktop-menu', 'uninstall']
                    if not refresh_cache:
                        desktop_menu_cmd.append('--noupdate')
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

        try:
            dispvm = (vm.template_for_dispvms and
                      vm.features.get('appmenus-dispvm', False))
        except (qubesadmin.exc.QubesDaemonNoResponseError,
                qubesadmin.exc.QubesNoSuchPropertyError):
            dispvm = False
        self._appmenus_create_onedir(
            vm, force=force, refresh_cache=refresh_cache, dispvm=False,
            keep_dispvm=dispvm)

        if dispvm:
            self._appmenus_create_onedir(
                vm, force=force, refresh_cache=refresh_cache, dispvm=True)

    def _appmenus_create_onedir(self, vm, force=False, refresh_cache=True,
                                dispvm=False, keep_dispvm=False):
        """Create/update .desktop files

        :param vm: QubesVM object for which create entries
        :param refresh_cache: refresh desktop environment cache; if false,
        must be refreshed manually later
        :param force: force re-registering files even if unchanged
        :param dispvm: whether create entries for launching new DispVM
        :param keep_dispvm: do not remove DispVM-related files,
        to be used together with dispvm=False
        :return: None
        """

        appmenus_dir = self.appmenus_dir(vm)
        if not os.path.exists(appmenus_dir):
            os.makedirs(appmenus_dir)

        anything_changed = False
        directory_changed = False
        directory_file = self._directory_path(vm, dispvm=dispvm)
        if self.write_desktop_file(
                vm,
                pkg_resources.resource_string(
                    __name__,
                    self.directory_template_name(vm, dispvm)).decode(),
                directory_file,
                dispvm):
            anything_changed = True
            directory_changed = True
        appmenus = list(self.get_available_filenames(vm))
        changed_appmenus = []
        if 'menu-items' in vm.features:
            whitelist = vm.features['menu-items'].split(' ')
            appmenus = [x for x in appmenus if os.path.basename(x) in whitelist]
        elif os.path.exists(self.whitelist_path(vm)):
            with open(self.whitelist_path(vm), encoding='utf-8') as whitelist_f:
                whitelist = [x.rstrip() for x in whitelist_f]
            appmenus = [x for x in appmenus if os.path.basename(x) in whitelist]

        for appmenu in appmenus:
            appmenu_basename = os.path.basename(appmenu)
            fname = os.path.join(appmenus_dir,
                                 self.desktop_name(vm, appmenu_basename,
                                                   dispvm=dispvm))
            try:
                if self.write_desktop_file(vm, appmenu, fname, dispvm):
                    changed_appmenus.append(fname)
            except DispvmNotSupportedError:
                # remove DispVM-incompatible entries
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(fname)

        target_appmenus = [
            self.desktop_name(vm, os.path.basename(x), dispvm=dispvm)
            for x in appmenus]

        if not dispvm:
            vm_settings_fname = os.path.join(
                appmenus_dir, self.settings_name(vm))
            if self.write_desktop_file(
                    vm,
                    pkg_resources.resource_string(
                        __name__,
                        'qubes-vm-settings.desktop.template'
                    ).decode(),
                    vm_settings_fname):
                changed_appmenus.append(vm_settings_fname)
            target_appmenus.append(os.path.basename(vm_settings_fname))

        if changed_appmenus:
            anything_changed = True

        # remove old entries
        installed_appmenus = os.listdir(appmenus_dir)
        installed_appmenus.remove(os.path.basename(directory_file))
        appmenus_to_remove = set(installed_appmenus).difference(set(
            target_appmenus))
        if keep_dispvm:
            appmenus_to_remove = [
                x for x in appmenus_to_remove
                if not x.startswith(self.qubes_dispvm_desktop) and
                   not x.startswith('qubes-dispvm-directory_')]
        elif dispvm:
            appmenus_to_remove = [
                x for x in appmenus_to_remove
                if not x.startswith(self.qubes_vm_desktop) and
                   not x.startswith('qubes-vm-directory_') and
                   not x.startswith(self.qubes_vm_desktop_settings)]
        self._do_remove_appmenus(vm, appmenus_to_remove, appmenus_dir,
                refresh_cache)

        for appmenu in (os.path.join(appmenus_dir, x)
                for x in appmenus_to_remove):
            try:
                if hasattr(vm, 'log'):
                    vm.log.warning('Removing appmenu %r', appmenu)
                os.unlink(appmenu)
            except FileNotFoundError:
                pass

        # add new entries
        if anything_changed or force:
            # Only call ‘xdg-desktop-menu’ if it has at least one file argument
            do_anything = False
            try:
                desktop_menu_cmd = ['xdg-desktop-menu', 'install']
                if not refresh_cache:
                    desktop_menu_cmd.append('--noupdate')
                desktop_menu_cmd.append(directory_file)
                if (directory_changed and not changed_appmenus) or force:
                    # only directory file changed, not actual entries;
                    # re-register all of them to force refresh
                    if target_appmenus:
                        desktop_menu_cmd.extend(
                            os.path.join(appmenus_dir, x)
                            for x in target_appmenus)
                        do_anything = True
                elif changed_appmenus:
                    desktop_menu_cmd.extend(changed_appmenus)
                    do_anything = True
                if do_anything:
                    desktop_menu_env = os.environ.copy()
                    desktop_menu_env['LC_COLLATE'] = 'C'
                    subprocess.check_call(
                        desktop_menu_cmd,
                        env=desktop_menu_env)
            except subprocess.CalledProcessError:
                vm.log.warning("Problem creating appmenus for %s", vm.name)

        if refresh_cache:
            if 'KDE_SESSION_UID' in os.environ:
                subprocess.call(['kbuildsycoca' +
                                 os.environ.get('KDE_SESSION_VERSION', '4')])

    @staticmethod
    def _is_old_path(name):
        """
        Return if a path to a desktop name is for the old (<= R4.1)
        menu version.
        """
        return not (name.startswith('org.qubes-os.dispvm._') or
                    name.startswith('org.qubes-os.vm._') or
                    name.startswith('org.qubes-os.qubes-vm-settings._') or
                    name.startswith('qubes-vm-directory_') or
                    name.startswith('qubes-dispvm-directory_'))

    def _old_directory_path(self, vm):
        """Return the old path of the directory file for this VM
        """
        return os.path.join(self.appmenus_dir(vm), str(vm) + '.vm.directory')

    def _directory_path(self, vm, dispvm=False):
        """Return the path of the directory file for this VM
        """
        basename = 'qubes-dispvm-directory' if dispvm else 'qubes-vm-directory'
        return os.path.join(self.appmenus_dir(vm),
                            basename + vm_name_escape(str(vm)) + '.directory')

    def appmenus_remove(self, vm, refresh_cache=True):
        """Remove desktop files for particular VM

        Warning: vm may be either QubesVM object, or just its name (str).
        Actual VM may be already removed at this point.
        """
        appmenus_dir = self.appmenus_dir(vm)
        if os.path.exists(appmenus_dir):
            if hasattr(vm, 'log'):
                vm.log.info("Removing appmenus")
            else:
                if logging.root.getEffectiveLevel() <= logging.INFO:
                    print("Removing appmenus for {!s}".format(vm),
                          file=sys.stderr)
            installed_appmenus = os.listdir(appmenus_dir)
            self._do_remove_appmenus(vm, installed_appmenus, appmenus_dir,
                    refresh_cache)
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
        if 'menu-items' in vm.features:
            whitelist = vm.features['menu-items'].split(' ')
        elif os.path.exists(whitelist):
            with open(whitelist, encoding='utf-8') as whitelist_f:
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
        """Remove icons

        Warning: vm may be either QubesVM object, or just its name (str).
        Actual VM may be already removed at this point.
        """
        if not os.path.exists(self.icons_dir(vm)):
            return
        shutil.rmtree(self.icons_dir(vm))

    def appmenus_init(self, vm, src=None):
        """Initialize directory structure on VM creation, copying appropriate
        data from VM template if necessary

        :param vm:
        :param src: source VM to copy data from
        """
        prefix_dir = os.path.join(basedir, vm.name)
        os.makedirs(prefix_dir, exist_ok=True)
        clone_from_src = src is not None
        if src is None:
            try:
                src = vm.template
            except AttributeError:
                pass
        own_templates_dir = os.path.join(prefix_dir,
                                         AppmenusSubdirs.templates_subdir)
        own_template_icons_dir = os.path.join(
            prefix_dir, AppmenusSubdirs.template_icons_subdir)
        if src is None:
            os.makedirs(own_templates_dir, exist_ok=True)
            os.makedirs(os.path.join(prefix_dir,
                                     AppmenusSubdirs.template_icons_subdir),
                        exist_ok=True)

            vm.log.info("Creating appmenus directory: {0}".format(
                own_templates_dir))
            with open(
                    os.path.join(own_templates_dir, 'qubes-start.desktop'),
                    'wb') as qubes_start_f:
                qubes_start_f.write(pkg_resources.resource_string(
                    __name__,
                    'qubes-start.desktop.template'))

        source_whitelist_filename = 'vm-' + AppmenusSubdirs.whitelist
        if src and ('default-menu-items' in src.features or os.path.exists(
                os.path.join(prefix_dir, source_whitelist_filename))):
            vm.log.info("Creating default whitelisted apps list: {0}".
                        format(prefix_dir + '/' + AppmenusSubdirs.whitelist))
            if 'menu-items' not in vm.features:
                if 'default-menu-items' in src.features:
                    vm.features['menu-items'] = \
                        src.features['default-menu-items']
                else:
                    self.set_whitelist(vm, retrieve_list(os.path.join(
                        prefix_dir, source_whitelist_filename)))

        # NOTE: No need to copy whitelists from VM features as that is
        # automatically done with clones
        if clone_from_src:
            for prefix in ('', 'vm-', 'netvm-'):
                whitelist = prefix + AppmenusSubdirs.whitelist
                p = os.path.join(prefix_dir, whitelist)
                if os.path.exists(p) \
                        and (prefix + 'menu-items') not in vm.features:
                    vm.log.info("Copying whitelisted apps list: {0}".
                                format(whitelist))
                    vm.features[prefix + 'menu-items'] = \
                            ' '.join(retrieve_list(p))

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
        """Update default applications list for VMs created on this template

        :param vm: VM object
        :param applications_list: list of applications to include
        """
        vm.features['default-menu-items'] = ' '.join(applications_list)

    @staticmethod
    def get_default_whitelist(vm):
        """
        Get default applications list for VMs created on this template
        :param vm: VM object
        :return: list of applications in default whitelist
        """
        return vm.features.get('default-menu-items', '').split(' ')

    @staticmethod
    def set_whitelist(vm, applications_list):
        """Update list of applications to be included in the menu

        :param vm: VM object
        :param applications_list: list of applications to include
        """
        vm.features['menu-items'] = ' '.join(applications_list)

    def get_whitelist(self, vm):
        """Retrieve list of applications to be included in the menu

        :param vm: VM object
        :return: list of applications (.desktop file names), or None if not set
        """
        if 'menu-items' in vm.features:
            for entry in vm.features['menu-items'].split(' '):
                entry = entry.strip()
                if not entry:
                    continue
                yield entry
            return None
        if not os.path.exists(self.whitelist_path(vm)):
            return None
        with open(self.whitelist_path(vm), 'r', encoding='utf-8') as whitelist:
            for line in whitelist:
                line = line.strip()
                if not line:
                    continue
                yield line

    def appmenus_update(self, vm, force=False):
        """Update (regenerate) desktop files and icons for this VM and (in
        case of template) child VMs"""
        if not os.path.exists(os.path.join(basedir, vm.name)):
            self.appmenus_init(vm)
        self.appicons_create(vm, force=force)
        self.appmenus_create(vm, force=force, refresh_cache=False)
        if hasattr(vm, 'appvms'):
            for child_vm in vm.appvms:
                if getattr(child_vm, 'guivm') != vm.app.local_name:
                    continue
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


parser = qubesadmin.tools.QubesArgumentParser(show_forceroot=True)

parser_stdin_mode = parser.add_mutually_exclusive_group()

parser.add_argument(
    '--init', action='store_true',
    help='Initialize directory structure for appmenus (on VM creation)')
parser.add_argument(
    '--create', action='store_true',
    help='Create appmenus')
parser.add_argument(
    '--remove', action='store_true',
    help='Remove appmenus')
parser.add_argument(
    '--update', action='store_true',
    help='Update appmenus')
parser.add_argument(
    '--get-available', action='store_true',
    help='Get list of applications available')
parser.add_argument(
    '--get-whitelist', action='store_true',
    help='Get list of applications to include in the menu')
parser_stdin_mode.add_argument(
    '--set-whitelist', metavar='PATH',
    action='store',
    help='Set list of applications to include in the menu,'
         'use \'-\' to read from stdin')
parser_stdin_mode.add_argument(
    '--set-default-whitelist', metavar='PATH',
    action='store',
    help='Set default list of applications to include in menu '
         'for VMs based on this template,'
         'use \'-\' to read from stdin')
parser.add_argument(
    '--get-default-whitelist', action='store_true',
    help='Get default list of applications to include in menu '
         'for VMs based on this template'
)
parser.add_argument(
    '--source', action='store', default=None,
    help='Source VM to copy data from (for --init option)')
parser.add_argument(
    '--force', action='store_true', default=False,
    help='Force refreshing files, even when looks up to date')
parser.add_argument(
    '--i-understand-format-is-unstable', dest='fool',
    action='store_true',
    help='required pledge for --get-available')
parser.add_argument(
    '--file-field', action='append', dest='fields',
    help='File field to append to output for --get-available; can be used'
         ' multiple times for multiple fields. This option changes output'
         ' format to pipe-("|") separated.')
parser.add_argument(
    '--template', action='store',
    help='Use the following template for listed domains instead of their '
         'actual template. Requires --get-available.')
parser.add_argument(
    '--all', action='store_true', dest='all_domains',
    help='perform the action on all qubes')
parser.add_argument(
    'domains', metavar='VMNAME', nargs='*', default=[],
    help='VMs on which perform requested actions')


def retrieve_list(path):
    """Helper function to retrieve data from given path, or stdin if '-'
    specified, then return it as a list of lines.

    :param path: path or '-'
    :return: list of lines
    """
    if path == '-':
        return [x.rstrip() for x in sys.stdin.readlines()]
    with open(path, 'r', encoding='utf-8') as file:
        return [x.rstrip() for x in file.readlines()]


def main(args=None, app=None):
    """main function for qvm-appmenus tool"""
    args = parser.parse_args(args=args, app=app)
    if not args.all_domains and not args.domains:
        parser.error("one of the arguments --all VMNAME is required")
    appmenus = Appmenus()
    if args.source is not None:
        args.source = args.app.domains[args.source]
    if args.template is not None:
        args.template = args.app.domains[args.template]
    if args.all_domains:
        if args.remove:
            domains = [vm for vm in os.listdir(os.path.abspath(basedir))
                       if os.path.isdir(os.path.join(basedir, vm))]
        else:
            domains = args.app.domains
    else:
        domains = args.domains
    for vm in domains:
        if str(vm) == 'dom0':
            continue
        # allow multiple actions
        # for remove still use just VM name (str), because VM may be already
        # removed.
        if args.remove:
            if isinstance(vm, qubesadmin.vm.QubesVM):
                vm = vm.name
            appmenus.appmenus_remove(vm)
            appmenus.appicons_remove(vm)
            try:
                shutil.rmtree(os.path.join(basedir, str(vm)))
            except FileNotFoundError:
                pass
        # for other actions - get VM object
        if not args.remove:
            if not isinstance(vm, qubesadmin.vm.QubesVM):
                vm = args.app.domains[vm]
            if args.init:
                appmenus.appmenus_init(vm, src=args.source)
            if args.get_whitelist:
                whitelist = appmenus.get_whitelist(vm)
                print('\n'.join(whitelist))
            if args.set_default_whitelist:
                whitelist = retrieve_list(args.set_default_whitelist)
                appmenus.set_default_whitelist(vm, whitelist)
            if args.get_default_whitelist:
                default_whitelist = appmenus.get_default_whitelist(vm)
                print('\n'.join(default_whitelist))
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
                            vm, fields=args.fields, template=args.template):
                        print('|'.join(result))


if __name__ == '__main__':
    sys.exit(main())
