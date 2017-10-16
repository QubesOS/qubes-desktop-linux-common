%{!?version: %define version %(cat version)}

%define desktop_file_utils_version 0.9

Name:		qubes-desktop-linux-common
Version:	%{version}
Release:	1%{?dist}
Summary:	Common code used for multiple desktop environments' Qubes integration

Group:		Qubes
Vendor:		Invisible Things Lab
License:	GPL
URL:		http://www.qubes-os.org

BuildArch:	noarch
BuildRequires:	pandoc
%if 0%{?rhel} >= 7
BuildRequires:	python34
BuildRequires:	python34-devel
%else
BuildRequires:	python3
BuildRequires:	python3-devel
%endif
BuildRequires:	ImageMagick
BuildRequires: desktop-file-utils >= %{desktop_file_utils_version}
Requires:	xdotool
Requires:	xorg-x11-utils
%if 0%{?rhel} >= 7
Requires:	python34-qubesimgconverter
Requires:	python34-qubesadmin
Requires:	python34-pyxdg
%else
Requires:	python3-qubesimgconverter
Requires:	python3-qubesadmin
Requires:	python3-pyxdg
%endif
Requires:   qubes-manager

%define _builddir %(pwd)

%description
Common code used for multiple desktop environments' Qubes integration

%package -n qubes-menus
Summary: Configuration and data files for the desktop menus
Group: User Interface/Desktops
Requires(post): desktop-file-utils >= %{desktop_file_utils_version}
Requires(postun): desktop-file-utils >= %{desktop_file_utils_version}

## old nautilus contained start-here stuff
Conflicts: nautilus <= 2.0.3-1
## desktop files in redhat-menus point to icons in new artwork
Conflicts: redhat-artwork < 0.35
## old evolution packages point to a no-longer-existing symlink
Conflicts: evolution <= 2.4.1-5

Provides: redhat-menus
Obsoletes: redhat-menus

%description -n qubes-menus
This package contains the XML files that describe the menu layout for
GNOME and KDE, and the .desktop files that define the names and icons
of "subdirectories" in the menus.


%build
make
make -C doc manpages

%install
make DESTDIR=$RPM_BUILD_ROOT MANDIR=%{_mandir} install
make -C doc DESTDIR=$RPM_BUILD_ROOT MANDIR=%{_mandir} install

%post

for i in /usr/share/qubes/icons/*.png ; do
    xdg-icon-resource install --noupdate --novendor --size 48 $i
done
xdg-icon-resource forceupdate

#xdg-desktop-menu install /usr/share/qubes-appmenus/qubes-dispvm.directory /usr/share/qubes-appmenus/qubes-dispvm-*.desktop

%preun
if [ "$1" = 0 ] ; then
    # no more packages left

    for i in /usr/share/qubes/icons/*.png ; do
        xdg-icon-resource uninstall --novendor --size 48 $i
    done

    #xdg-desktop-menu uninstall /usr/share/qubes-appmenus/qubes-dispvm.directory /usr/share/qubes-appmenus/qubes-dispvm-*.desktop
fi


%files
%defattr(-,root,root,-)
%{_bindir}/qvm-xkill
%{_mandir}/man1/qvm-*.1*
%dir %{python3_sitelib}/qubesdesktop-*.egg-info
%{python3_sitelib}/qubesdesktop-*.egg-info/*
%dir %{python3_sitelib}/qubesappmenus
%dir %{python3_sitelib}/qubesappmenus/__pycache__
%{python3_sitelib}/qubesappmenus/__pycache__/*
%{python3_sitelib}/qubesappmenus/__init__.py
%{python3_sitelib}/qubesappmenus/receive.py
%{python3_sitelib}/qubesappmenus/qubes-vm-settings.desktop.template
%{python3_sitelib}/qubesappmenus/qubes-servicevm.directory.template
%{python3_sitelib}/qubesappmenus/qubes-templatevm.directory.template
%{python3_sitelib}/qubesappmenus/qubes-vm.directory.template
%{python3_sitelib}/qubesappmenus/qubes-dispvm.directory.template
%{python3_sitelib}/qubesappmenus/tests.py
%{python3_sitelib}/qubesappmenus/tests_integ.py
%{python3_sitelib}/qubesappmenus/test-data

%dir %{python3_sitelib}/qubesappmenusext
%dir %{python3_sitelib}/qubesappmenusext/__pycache__
%{python3_sitelib}/qubesappmenusext/__pycache__/*
%{python3_sitelib}/qubesappmenusext/__init__.py

/etc/qubes-rpc/qubes.SyncAppMenus
/usr/share/qubes-appmenus/qubes-dispvm-firefox.desktop
/usr/share/qubes-appmenus/qubes-dispvm-xterm.desktop
/usr/share/qubes-appmenus/qubes-dispvm.directory
/usr/share/qubes-appmenus/qubes-start.desktop
/usr/share/qubes-appmenus/hvm
/usr/share/qubes/icons/*.png
/usr/bin/qvm-sync-appmenus
/usr/bin/qvm-appmenus

%files -n qubes-menus
%defattr(-,root,root)
%doc qubes-menus/README
%dir %{_sysconfdir}/xdg/menus
%dir %{_sysconfdir}/xdg/menus/applications-merged
%dir %{_sysconfdir}/xdg/menus/preferences-merged
%dir %{_sysconfdir}/xdg/menus/preferences-post-merged
%dir %{_sysconfdir}/xdg/menus/settings-merged
%config %{_sysconfdir}/xdg/menus/*.menu
%{_datadir}/desktop-directories/*.directory
