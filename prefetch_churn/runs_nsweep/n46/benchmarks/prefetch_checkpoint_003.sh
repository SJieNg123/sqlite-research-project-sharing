#!/bin/sh
set -eu
exec /home/u03/sqlite-research-project-sharing/prefetch_vacuum/src/prefetch_layers /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n46/test_churn.db /home/u03/sqlite-research-project-sharing/prefetch_churn/runs_nsweep/n46/checkpoints/classify_pages_checkpoint_003.csv 46 4096
