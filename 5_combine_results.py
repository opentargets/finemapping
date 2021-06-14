#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Ed Mountjoy
#
'''
# Set SPARK_HOME and PYTHONPATH to use 2.4.0
export PYSPARK_SUBMIT_ARGS="--driver-memory 8g pyspark-shell"
export SPARK_HOME=/Users/em21/software/spark-2.4.0-bin-hadoop2.7
export PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-2.4.0-src.zip:$PYTHONPATH
'''

import pyspark.sql
from pyspark.sql.types import *
from pyspark.sql.functions import *
import yaml
import os
from shutil import copyfile
from glob import glob


def main():
    # Load analysis config file
    config_file = 'configs/analysis.config.yaml'
    with open(config_file, 'r') as in_h:
        config_dict = yaml.safe_load(in_h)

    # Make spark session
    # Using `ignoreCorruptFiles` will skip empty files
    spark = (
        pyspark.sql.SparkSession.builder
        .config("spark.sql.files.ignoreCorruptFiles", "true")
        .config("spark.master", "local[*]")
        .getOrCreate()
    )
    # sc = spark.sparkContext
    print('Spark version: ', spark.version)

    # Args
    in_top_loci_pattern = os.path.join(config_dict['finemapping_output_dir'],
                                       'output/study_id=*/phenotype_id=*/bio_feature=*/chrom=*/top_loci.json.gz')
    in_credset_pattern = os.path.join(config_dict['finemapping_output_dir'],
                                      'output/study_id=*/phenotype_id=*/bio_feature=*/chrom=*/credible_set.json.gz')

    out_top_loci = os.path.join(config_dict['finemapping_output_dir'], 'results/top_loci')
    if not os.path.exists(out_top_loci):
        os.makedirs(out_top_loci)

    out_credset = os.path.join(config_dict['finemapping_output_dir'], 'results/credset')
    if not os.path.exists(out_credset):
        os.makedirs(out_credset)

    # Process top loci 
    (
        spark.read.json(in_top_loci_pattern)
        .coalesce(1)
        .orderBy('study_id', 'phenotype_id', 'bio_feature',
                 'chrom', 'pos')
        .write.json(out_top_loci,
                    compression='gzip',
                    mode='overwrite')
    )
    
    # Copy to single file
    copyfile(
        glob(out_top_loci + '/part-*.json.gz')[0],
        out_top_loci + '.json.gz'
    )
    
    # Process cred set
    (
        spark.read.json(in_credset_pattern)
        .repartitionByRange('lead_chrom', 'lead_pos')
        .sortWithinPartitions('lead_chrom', 'lead_pos')
        .write.json(out_credset,
                    compression='gzip',
                    mode='overwrite')
    )
    


    return 0

if __name__ == '__main__':

    main()
