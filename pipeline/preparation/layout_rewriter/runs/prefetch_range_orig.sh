#!/bin/sh
exec /home/u03/sqlite-research-project-sharing/prefetch_vacuum/src/prefetch \
  /home/u03/sqlite-research-project-sharing/layout_rewriter/runs/test.db \
  /home/u03/sqlite-research-project-sharing/layout_rewriter/runs/classify_before.csv \
  range >&2
