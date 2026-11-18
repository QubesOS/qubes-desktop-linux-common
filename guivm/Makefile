UNITDIR ?= /usr/lib/systemd/system

all:

install:
	install -D -m 0755 qubes-guivm-power-forward \
		$(DESTDIR)/usr/lib/qubes/qubes-guivm-power-forward
	install -D -m 0755 qubes-guivm-suspend \
		$(DESTDIR)/usr/lib/qubes/qubes-guivm-suspend
	install -D -m 0644 qubes-guivm-power-forward.service \
		$(DESTDIR)$(UNITDIR)/qubes-guivm-power-forward.service
	install -D -m 0644 30_qubes-guivm.conf \
		$(DESTDIR)$(UNITDIR)/systemd-suspend.service.d/30_qubes-guivm.conf
	install -D -m 0755 suspend-pre.sh \
		$(DESTDIR)/etc/qubes/suspend-pre.d/qubes-guivm-suspend.sh
	install -D -m 0755 suspend-post.sh \
		$(DESTDIR)/etc/qubes/suspend-post.d/qubes-guivm-suspend.sh
