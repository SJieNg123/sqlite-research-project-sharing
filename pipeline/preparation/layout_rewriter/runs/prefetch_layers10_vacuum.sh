#!/bin/sh
exec /home/u03/sqlite-research-project-sharing/prefetch_vacuum/src/prefetch_layers \
  /home/u03/sqlite-research-project-sharing/layout_rewriter/runs/test_vacuum.db \
  /home/u03/sqlite-research-project-sharing/layout_rewriter/runs/classify_vacuum.csv \
  10 4096 >&2
