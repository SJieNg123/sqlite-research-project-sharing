#!/bin/sh
exec /home/u03/sqlite-research-project-sharing/prefetch_warmer/src/warmer /home/u03/sqlite-research-project-sharing/prefetch_access/runs/test.db "${WARM_HOTSET:-/home/u03/sqlite-research-project-sharing/prefetch_warmer/runs/hotset_internal.csv}" 4096
