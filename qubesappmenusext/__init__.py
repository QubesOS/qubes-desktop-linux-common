# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.
import contextlib
import subprocess
import grp
import logging
import asyncio
from collections import defaultdict

import qubes.ext
from qubes.utils import sanitize_stderr_for_log


class AppmenusExtension(qubes.ext.Extension):
    def __init__(self, *args):
        super(AppmenusExtension, self).__init__(*args)
        self.log = logging.getLogger('appmenus')
        self.vm_tasks = defaultdict(list)

    async def run_as_user(self, command):
        """
        Run given command (in subprocess.Popen acceptable format) as default
        normal user

        :param command: list for subprocess.Popen
        :return: None
        """
        try:
            qubes_group = grp.getgrnam('qubes')
            user = qubes_group.gr_mem[0]
        except KeyError as e:
            self.log.warning('Default user not found: ' + str(e))
            return

        proc = await asyncio.create_subprocess_exec(
            'runuser', '-u', user, '--', 'env', 'DISPLAY=:0',
            *command)
        await proc.wait()
        if proc.returncode != 0:
            self.log.warning('Command \'%s\' failed', ' '.join(command))

    async def update_appmenus(self, vm):
        guivm = vm.guivm
        if not guivm:
            self.log.warning("VM for '%s' does not have GUI VM, not updating menu", vm.name)
            return
        if not guivm.is_running():
            self.log.warning("GUI VM for '%s' is not running, queueing menu update", vm.name)
            # please no async code between those two calls
            current_queue = guivm.features.get('menu-update-pending-for', '').split(' ')
            if vm.name not in current_queue:
                guivm.features['menu-update-pending-for'] = ' '.join(current_queue + [vm.name])
            return
        self.log.info("Updating appmenus for '%s' in '%s'", vm.name, guivm.name)
        if guivm.klass == 'AdminVM' or guivm.features.check_with_template("supported-rpc.qubes.UpdateAppMenusFor", None):
            try:
                await guivm.run_service_for_stdio("qubes.UpdateAppMenusFor+" + vm.name)
            except subprocess.CalledProcessError as e:
                self.log.error("Failed to update appmenus for '%s' in '%s': %s",
                    vm.name, guivm.name, sanitize_stderr_for_log(e.stderr))
        else:
            # older desktop-linux-common
            try:
                await guivm.run_for_stdio("qvm-appmenus --update --quiet --force -- " + vm.name)
            except subprocess.CalledProcessError as e:
                self.log.error("Failed to update appmenus for '%s' in '%s': %s",
                    vm.name, guivm.name, sanitize_stderr_for_log(e.stderr))

    async def remove_appmenus(self, vm_name, guivm):
        if not guivm:
            self.log.warning("VM for '%s' does not have GUI VM, not removing menu", vm_name)
            return
        if not guivm.is_running():
            self.log.warning("GUI VM for '%s' is not running, queueing menu removal", vm_name)
            # please no async code between those two calls
            current_queue = guivm.features.get('menu-remove-pending-for', '').split(' ')
            if vm_name not in current_queue:
                guivm.features['menu-remove-pending-for'] = ' '.join(current_queue + [vm_name])
            return
        self.log.info("Removing appmenus for '%s' in '%s'", vm_name, guivm.name)
        if guivm.klass == 'AdminVM' or guivm.features.check_with_template("supported-rpc.qubes.RemoveAppMenusFor", None):
            try:
                await guivm.run_service_for_stdio("qubes.RemoveAppMenusFor+" + vm_name)
            except subprocess.CalledProcessError as e:
                self.log.error("Failed to remove appmenus for '%s' in '%s': %s",
                    vm_name, guivm.name, sanitize_stderr_for_log(e.stderr))
        else:
            # older desktop-linux-common
            try:
                await guivm.run_for_stdio("qvm-appmenus --remove --quiet -- " + vm_name)
            except subprocess.CalledProcessError as e:
                self.log.error("Failed to remove appmenus for '%s' in '%s': %s",
                    vm_name, guivm.name, sanitize_stderr_for_log(e.stderr))

    @qubes.ext.handler('domain-create-on-disk')
    async def create_on_disk(self, vm, event):
        await self.update_appmenus(vm)

    @qubes.ext.handler('domain-clone-files')
    async def clone_disk_files(self, vm, event, src):
        await self.run_as_user(
            ['qvm-appmenus', '--quiet', '--init', '--create', '--source=' + src.name,
            vm.name])

    async def collect_pending_tasks(self, vm):
        """Wait for any pending tasks to complete"""
        tasks = self.vm_tasks[vm.name]
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)
        with contextlib.suppress(KeyError):
            del self.vm_tasks[vm.name]

    def collect_done_tasks(self, vm):
        """Collect only done tasks, no async code"""
        if vm.name not in self.vm_tasks:
            return
        tasks = self.vm_tasks[vm.name]
        new_tasks = []
        for task in list(tasks):
            if task.done():
                try:
                    task.result()
                except Exception as e:  # pylint: disable=broad-except
                    vm.log.warning("Appmenu operation failed for '%s': %s",
                        vm.name, str(e))
            else:
                new_tasks.append(task)
        if new_tasks:
            self.vm_tasks[vm.name] = new_tasks
        else:
            del self.vm_tasks[vm.name]

    @qubes.ext.handler('domain-remove-from-disk')
    async def remove_from_disk(self, vm, event):
        # wait for any pending appmenu operations to complete
        # before removing appmenus
        await self.collect_pending_tasks(vm)
        await self.remove_appmenus(vm.name, vm.guivm)

    @qubes.ext.handler('property-set:label')
    def label_setter(self, vm, event, **kwargs):
        self.collect_done_tasks(vm)
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('property-set:provides_network')
    def provides_network_setter(self, vm, event, **kwargs):
        self.collect_done_tasks(vm)
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('property-set:guivm')
    def provides_network_setter(self, vm, event, name, newvalue, oldvalue=None):
        self.collect_done_tasks(vm)
        if oldvalue and oldvalue != newvalue:
            self.vm_tasks[vm.name].append(
                asyncio.ensure_future(self.remove_appmenus(vm.name, oldvalue)))
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('domain-feature-delete:appmenus-dispvm')
    def on_feature_del_appmenus_dispvm(self, vm, event, feature):
        self.collect_done_tasks(vm)
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('domain-feature-set:appmenus-dispvm')
    def on_feature_set_appmenus_dispvm(self, vm, event, feature,
            value, oldvalue=None):
        self.collect_done_tasks(vm)
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('domain-feature-set:menu-items')
    def on_feature_set_appmenus_dispvm(self, vm, event, feature,
            value, oldvalue=None):
        self.collect_done_tasks(vm)
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('domain-feature-delete:internal')
    def on_feature_del_internal(self, vm, event, feature):
        self.collect_done_tasks(vm)
        self.vm_tasks[vm.name].append(
            asyncio.ensure_future(self.update_appmenus(vm)))

    @qubes.ext.handler('domain-feature-set:internal')
    def on_feature_set_internal(self, vm, event, feature, value,
            oldvalue=None):
        self.collect_done_tasks(vm)
        if value:
            self.vm_tasks[vm.name].append(
                asyncio.ensure_future(self.remove_appmenus(vm.name, vm.guivm)))

    @qubes.ext.handler('domains-start')
    async def on_domain_start(self, vm, event, **kwargs):
        """Process queued menu updates"""
        pending_update = vm.features.get('menu-update-pending-for', '').split(' ')
        pending_remove = vm.features.get('menu-remove-pending-for', '').split(' ')
        if pending_update or pending_remove:
            vm.log.info("Processing pending menu updates")
            for to_remove in pending_remove:
                await self.remove_appmenus(to_remove, guivm=vm)
            del vm.features['menu-update-pending-for']
            for to_update in pending_update:
                if to_update not in vm.app.domains:
                    # removed in the meantime, and should be handled
                    # by the loop above
                    continue
                await self.update_appmenus(vm.app.domains[to_update])
            del vm.features['menu-update-pending-for']

    @qubes.ext.handler('domain-shutdown')
    async def on_domain_shutdown(self, vm, event, **kwargs):
        """Collect any async tasks

        Use this async handler to collect pending tasks, if any
        """
        await self.collect_pending_tasks(vm)
        for vm in vm.app.domains:
            self.collect_done_tasks(vm)

    @qubes.ext.handler('template-postinstall')
    async def on_template_postinstall(self, vm, event):
        await self.run_as_user(['qvm-sync-appmenus', vm.name])
