#!/bin/sh
set -eu
exec /home/u03/sqlite-research-project-sharing/prefetch_vacuum/src/prefetch_layers /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n20/test_churn.db /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n20/checkpoints/classify_pages_checkpoint_005.csv 20 4096
