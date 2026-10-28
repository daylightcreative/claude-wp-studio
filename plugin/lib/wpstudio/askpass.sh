#!/bin/sh
# SSH_ASKPASS helper: ssh runs this to get the password, which wpsite passes in the environment.
printf '%s\n' "$WPSTUDIO_SSH_PASSWORD"
