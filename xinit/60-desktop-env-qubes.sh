#!/usr/bin/sh

# correctly export desktop environment
systemctl --user import-environment XDG_CURRENT_DESKTOP
