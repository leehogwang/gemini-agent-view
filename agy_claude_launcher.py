#!/bin/bash
# agy-av shell wrapper
# exec -a overwrites argv[0] so ps/top/htop shows "agy-av" instead of "python3"
exec -a agy-av /home/202421012/miniforge3/bin/python3 /home/202421012/.local/bin/agy-claude.py.bak "$@"
