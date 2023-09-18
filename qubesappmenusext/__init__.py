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

import subprocess
import grp
import logging
import asyncio

import qubes.ext


class AppmenusExtension(qubes.ext.Extension):
    def __init__(self, *args):
        super(AppmenusExtension, self).__init__(*args)
        self.log = logging.getLogger('appmenus')

    async def run_as_user(self, command):
        '''
        Run given command (in subprocess.Popen acceptable format) as default
        normal user

        :param command: list for subprocess.Popen
        :return: None
        '''
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

    @qubes.ext.handler('domain-create-on-disk')
    async def create_on_disk(self, vm, event):
        await self.run_as_user(
            ['qvm-appmenus', '--quiet', '--init', '--create', vm.name])


    @qubes.ext.handler('domain-clone-files')
    async def clone_disk_files(self, vm, event, src):
        await self.run_as_user(
            ['qvm-appmenus', '--quiet', '--init', '--create', '--source=' + src.name,
            vm.name])

    @qubes.ext.handler('domain-remove-from-disk')
    async def remove_from_disk(self, vm, event):
        await self.run_as_user(
            ['qvm-appmenus', '--quiet', '--remove', vm.name])

    @qubes.ext.handler('property-set:label')
    def label_setter(self, vm, event, **kwargs):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-appmenus', '--quiet', '--force', '--update', vm.name]))

    @qubes.ext.handler('property-set:provides_network')
    def provides_network_setter(self, vm, event, **kwargs):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-appmenus', '--quiet', '--force', '--update', vm.name]))

    @qubes.ext.handler('domain-feature-delete:appmenus-dispvm')
    def on_feature_del_appmenus_dispvm(self, vm, event, feature):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-appmenus', '--quiet', '--force', '--update', vm.name]))

    @qubes.ext.handler('domain-feature-set:appmenus-dispvm')
    def on_feature_set_appmenus_dispvm(self, vm, event, feature,
            value, oldvalue=None):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-appmenus', '--quiet', '--force', '--update', vm.name]))

    @qubes.ext.handler('domain-feature-set:menu-items')
    def on_feature_set_appmenus_dispvm(self, vm, event, feature,
            value, oldvalue=None):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-appmenus', '--quiet', '--force', '--update', vm.name]))

    @qubes.ext.handler('domain-feature-delete:internal')
    def on_feature_del_internal(self, vm, event, feature):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-appmenus', '--quiet', '--create', vm.name]))

    @qubes.ext.handler('domain-feature-set:internal')
    def on_feature_set_internal(self, vm, event, feature, value,
            oldvalue=None):
        if value:
            asyncio.ensure_future(self.run_as_user(
                ['qvm-appmenus', '--quiet', '--remove', vm.name]))

    @qubes.ext.handler('template-postinstall')
    def on_template_postinstall(self, vm, event):
        asyncio.ensure_future(self.run_as_user(
            ['qvm-sync-appmenus', vm.name]))
