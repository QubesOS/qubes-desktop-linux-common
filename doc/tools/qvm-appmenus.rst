============
qvm-appmenus
============

NAME
====
qvm-appmenus - handle menu entries stored by dom0 for applications in qubes

DESCRIPTION
===========
This command handles various tasks related to menu entries for qubes: from creating directory structure to updating and listing available applications. It is mostly useful in scripts and internal tools.
The most common usage scenarios are
``qvm-appmenus --update VMNAME`` to synchronize icons and .desktop files for a given VM

OPTIONS
=======
--verbose, -v
    increase verbosity

--quiet, -q
    decrease verbosity

--help
    show a help message and exit

--init [--source SOURCE_VMNAME]
    Initialize directory structure for given VM's appmenus in dom0. Used on VM creation. Copies necessary data from the template if needed.
    Optional parameter --source allows specifying a VM to copy data from. Source supersedes the VM's own template.

 --create
    Create/update (as needed) all application menu content: application icons and .desktop files.

--remove
    Remove .desktop files and icons for the given VM. The VM may no longer exist when this command is called.

--update
    Update (regenerate) .desktop files and icons for the VM and - if it's a template - all child VMs.

--force
    Force refreshing files, even if they seem up-to-date. Works with --create and --update.

--get-whitelist
    Get a list of .desktop files corresponding to applications to be included in the menu.

--set-whitelist PATH
    Set the list of applications to be included in the menu. The PATH can be either a path to file containing a list of .desktop files, or a single hyphen ('-') to read from standard input.

 --set-default-whitelist PATH
    Set the default list of applications to be included in the menus of VMs based on this template. Should only be used for TemplateVMs .The PATH can be either a path to file containing a list of .desktop files, or a single hyphen ('-') to read from standard input.

--get-available
    List all available applications for the VM.
    The applications are listed as hyphen-separated pairs consisting of file name and application name.

--file-field FIELDNAME
    .desktop file field to append to output for --get-available; can be used multiple times for multiple fields. This option changes output format to pipe-("|") separated.

AUTHORS
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Marta Marczykowska-Górecka <marmarta at invisiblethingslab dot com>
