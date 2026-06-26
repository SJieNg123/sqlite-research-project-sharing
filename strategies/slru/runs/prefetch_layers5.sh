#!/bin/sh
exec /home/u03/sqlite-research-project-sharing/prefetch_slru/runs/prefetch_layers \
  /home/u03/sqlite-research-project-sharing/prefetch_slru/runs/test.db \
  /home/u03/sqlite-research-project-sharing/prefetch_slru/runs/classify_orig.csv \
  5 4096 >&2
