all:
	@true

install:
	install -D -m0644 lightdm-10-qubes-wayland-off.conf \
		$(DESTDIR)/usr/share/lightdm/lightdm.conf.d/10-qubes-wayland-off.conf
	install -D -m0644 lightdm-15-qubes-wayland-on.conf \
		$(DESTDIR)/usr/share/lightdm/lightdm.conf.d/15-qubes-wayland-on.conf
	install -D -m0644 sddm-10-qubes-wayland-off.conf \
		$(DESTDIR)/usr/lib/sddm/sddm.conf.d/10-qubes-wayland-off.conf
	install -D -m0644 sddm-15-qubes-wayland-on.conf \
		$(DESTDIR)/usr/lib/sddm/sddm.conf.d/15-qubes-wayland-on.conf
