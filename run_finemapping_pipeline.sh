#!/usr/bin/env bash

python 1_scan_input_parquets.py
python 2_make_manifest.py
python 3_make_commands.py
bash 4_run_commands.sh
python 5_combine_results.py
python partition_top_loci_by_chrom.py