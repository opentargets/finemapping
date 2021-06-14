#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Ed Mountjoy
#

import gzip
import json
import os
from glob import glob

import yaml


def main():
    # Load analysis config file
    config_file = 'configs/analysis.config.yaml'
    with open(config_file, 'r') as in_h:
        config_dict = yaml.safe_load(in_h)

    # Args
    input_pattern = os.path.join(config_dict['finemapping_output_dir'], 'tmp/filtered_input/*.json.gz')
    out_json = 'configs/manifest.json.gz'
    valid_chrom = set([str(chrom) for chrom in range(1, 23)])
    method = 'conditional'

    # Path patterns (local)
    # out_path = '/Users/em21/Projects/genetics-finemapping/output/study_id={0}/phenotype_id={1}/bio_feature={2}/chrom={3}'
    # log_path = '/Users/em21/Projects/genetics-finemapping/logs/study_id={0}/phenotype_id={1}/bio_feature={2}/chrom={3}'
    # tmp_path = '/Users/em21/Projects/genetics-finemapping/tmp/study_id={0}/phenotype_id={1}/bio_feature={2}/chrom={3}'
    # ld_ref = '/Users/em21/Projects/reference_data/uk10k_2019Feb/3_liftover_to_GRCh38/output/{chrom}.ALSPAC_TWINSUK.maf01.beagle.csq.shapeit.20131101'

    # Path patterns (server)
    out_path = os.path.join(config_dict['finemapping_output_dir'],
                            'output/study_id={0}/phenotype_id={1}/bio_feature={2}/chrom={3}')
    if not os.path.exists(out_path):
        os.makedirs(out_path)

    log_path = os.path.join(config_dict['finemapping_output_dir'],
                            'logs/study_id={0}/phenotype_id={1}/bio_feature={2}/chrom={3}')
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    tmp_path = os.path.join(config_dict['finemapping_output_dir'],
                            'tmp/study_id={0}/phenotype_id={1}/bio_feature={2}/chrom={3}')
    if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)

    ld_ref = config_dict['linkage_disequilibrium_reference']

    # Create manifest
    manifest = []
    for in_record in read_json_records(input_pattern):

        # initiate output
        out_record = {}

        # Skip if chromosome is not valid
        if not in_record['chrom'] in valid_chrom:
            continue

        # Add study identifier arguments
        out_record['type'] = in_record.get('type')
        out_record['study_id'] = in_record.get('study_id')
        out_record['phenotype_id'] = in_record.get('phenotype_id', None)
        out_record['bio_feature'] = in_record.get('bio_feature', None)
        out_record['chrom'] = in_record.get('chrom')

        # Add input files
        out_record['in_pq'] = parse_input_name(in_record.get('input_name'))
        out_record['in_ld'] = ld_ref

        # Add output files
        out_record['out_top_loci'] = out_path.format(
            out_record['study_id'], out_record['phenotype_id'],
            out_record['bio_feature'], out_record['chrom']
        ) + '/top_loci.json.gz'
        out_record['out_credset'] = out_path.format(
            out_record['study_id'], out_record['phenotype_id'],
            out_record['bio_feature'], out_record['chrom']
        ) + '/credible_set.json.gz'
        out_record['out_log'] = log_path.format(
            out_record['study_id'], out_record['phenotype_id'],
            out_record['bio_feature'], out_record['chrom']
        ) + '/logfile.txt'
        out_record['tmpdir'] = tmp_path.format(
            out_record['study_id'], out_record['phenotype_id'],
            out_record['bio_feature'], out_record['chrom']
        )

        # Add method
        out_record['method'] = method
        out_record['pval_threshold'] = in_record.get('pval_threshold')

        manifest.append(out_record)

    # Write manifest as a json
    with gzip.open(out_json, 'w') as out_h:
        for record in manifest:
            out_h.write((json.dumps(record) + '\n').encode())

    return 0


def read_json_records(in_pattern):
    ''' Globs json inputs then yields all records as dicts.
        Expects inputs to be gzipped.
    '''
    for inf in glob(in_pattern):
        with gzip.open(inf, 'r') as in_h:
            for in_record in in_h:
                in_record = json.loads(in_record.decode().rstrip())
                yield in_record


def parse_input_name(s):
    ''' Parses the required input name. Spark's input_file_name() returns the
        nested parquet file, I need the top level parquet.
    '''
    # Strip nested parquet
    out_s = s.split('.parquet')[0] + '.parquet'
    # Stip file://
    out_s = out_s.replace('file://', '')
    return out_s


if __name__ == '__main__':
    main()
