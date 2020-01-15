all:
	python3 setup.py build


install:
	## Tools
	install -D -m755 tools/qvm-xkill $(DESTDIR)/usr/bin/qvm-xkill

	### Icons
	mkdir -p $(DESTDIR)/usr/share/qubes/icons
	for icon in icons/*.png; do \
		convert -resize 48 $$icon $(DESTDIR)/usr/share/qubes/$$icon; \
	done
	### Appmenus
	# force /usr/bin before /bin to have /usr/bin/python instead of /bin/python
	PATH="/usr/bin:$$PATH" python3 setup.py install $(PYTHON_PREFIX_ARG) -O1 --skip-build --root $(DESTDIR)

	mkdir -p $(DESTDIR)/etc/qubes-rpc/policy
	install -m 0755 qubesappmenus/qubes.SyncAppMenus $(DESTDIR)/etc/qubes-rpc/

	$(MAKE) -C qubes-menus install

clean:
	rm -rf qubesappmenus/__pycache__
	rm -rf qubesappmenusext/__pycache__
	rm -f .coverage
