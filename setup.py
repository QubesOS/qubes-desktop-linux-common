# vim: fileencoding=utf-8

import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='qubesdesktop',
        version=open('version').read().strip(),
        author='Invisible Things Lab',
        author_email='woju@invisiblethingslab.com',
        description='Qubes desktop-linux-common package',
        license='GPL2+',
        url='https://www.qubes-os.org/',

        packages=('qubesappmenus', 'qubesappmenusext', 'qubesclipboard',),

        package_data = {
            'qubesappmenus': ['test-data/*', '*.template'],
        },

        entry_points={
            'console_scripts': [
                'qvm-sync-appmenus = qubesappmenus.receive:main',
                'qvm-appmenus = qubesappmenus:main',
                'qubes-dom0-copy-to-clipboard = qubesclipboard:main',
            ],
            'qubes.ext': [
                'qubesappmenus = qubesappmenusext:AppmenusExtension',
            ],
            'qubes.tests.extra': [
                'qubesappmenus = qubesappmenus.tests:list_tests',
                'qubesappmenus_integ = qubesappmenus.tests_integ:list_tests',
                'qubesclipboard = qubesclipboard.tests:list_tests',
            ],
        }
    )
