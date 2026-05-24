#!/bin/sh
set -eu
exec /home/u03/sqlite-research-project-sharing/prefetch_vacuum/src/prefetch_layers /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n5/test_churn.db /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n5/checkpoints/classify_pages_checkpoint_010.csv 5 4096
