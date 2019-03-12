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
import os
from glob import glob
from functools import reduce

def main():

    # Make spark session
    spark = pyspark.sql.SparkSession.builder.getOrCreate()
    # sc = spark.sparkContext
    print('Spark version: ', spark.version)

    # Args
    gwas_pval_threshold = 5e-8
    gwas_pattern = '/home/emountjoy_statgen/data/sumstats/gwas/*.parquet'
    mol_pattern = '/home/emountjoy_statgen/data/sumstats/molecular_trait/*.parquet'

    # Load GWAS dfs
    gwas_dfs = []
    for inf in glob(gwas_pattern):
        inf = os.path.abspath(inf)
        df = (
            spark.read.parquet(inf)
                .withColumn('pval_threshold', lit(gwas_pval_threshold))
                .withColumn('input_name', lit(inf))
                .withColumn('Biofeature', lit(None))
        )
        gwas_dfs.append(df)
    
    # Load molecular trait dfs
    mol_dfs = []
    for inf in glob(mol_pattern):
        inf = os.path.abspath(inf)
        df = (
            spark.read.parquet(inf)
            .withColumn('pval_threshold', (0.05 / col('num_tests')))
            .withColumn('pval_threshold', when(col('pval_threshold') > gwas_pval_threshold,
                                            col('pval_threshold'))
                        .otherwise(gwas_pval_threshold))
            .drop('num_tests')
            .withColumn('input_name', lit(inf))
        )
        mol_dfs.append(df)

    # Take union
    df = reduce(
        pyspark.sql.DataFrame.unionByName,
        gwas_dfs + mol_dfs
    )
    
    # Process
    df = (
        df.filter(col('pval') < col('pval_threshold'))
          .select('type', 'study_id', 'phenotype_id', 'biofeature', 'gene_id', 'chrom', 'pval_threshold', 'input_name')
        #   .filter(col('chrom') == '22') # DEBUG
          .distinct()
    )

    # Write
    (
        df.coalesce(1)
          .write.json('tmp/filtered_input.json',
                      mode='overwrite')
    )

    # input_file_name

    return 0

if __name__ == '__main__':

    main()