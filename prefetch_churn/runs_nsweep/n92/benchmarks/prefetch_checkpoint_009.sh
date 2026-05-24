#!/bin/sh
set -eu
exec /home/u03/sqlite-research-project-sharing/prefetch_vacuum/src/prefetch_layers /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n92/test_churn.db /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n92/checkpoints/classify_pages_checkpoint_009.csv 92 4096
