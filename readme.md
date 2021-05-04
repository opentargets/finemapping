Open Target Genetics fine-mapping pipeline
==========================================

Fine-mapping pipeline for Open Targets Genetics. In brief, the method is:
1. Detect independent loci across the summary stat file using either (i) GCTA-cojo and a given plink file as an LD reference, (ii) distance based clumping. Method specified with `--method` argument.
2. If `--method conditional`, for each independent locus condition on all other surrounding loci (configurable with `cojo_wind`).
3. Perform approximate Bayes factor credible set analysis for each independent locus.

### Requirements
- Spark v2.4.0
- GCTA (>= v1.91.3) must be available in `$PATH`
- [conda](https://conda.io/docs/)
- GNU parallel

### Setup environment

```
git clone https://github.com/opentargets/genetics-finemapping.git
cd ~/genetics-finemapping
bash setup.sh
. ~/.profile # Reload profile so that conda works
conda env create -n finemap --file environment.yaml
```

### Configure pipeline

Many of the pipeline parameters must first be specified in the analysis config file: `configs/analysis.config.yaml`

### Run a single study

A single study can be fine-mapped using the single study wrapper

```
# Activate environment
source activate finemap

# Edit config file (this needs selecting with --config_file arg)
nano configs/analysis.config.yaml

# View args
$ python finemapping/single_study.wrapper.py --help
usage: single_study.wrapper.py [-h] --pq <file> --ld <file> --config_file
                               <file> --type <str> --study_id <str> --chrom
                               <str> [--phenotype_id <str>]
                               [--bio_feature <str>] --method
                               [conditional|distance] --pval_threshold <float>
                               --toploci <file> --credset <file> --log <file>
                               --tmpdir <file> [--delete_tmpdir]

optional arguments:
  -h, --help            show this help message and exit
  --pq <file>           Input: parquet file containing summary stats
  --ld <file>           Input: plink file to estimate LD from
  --config_file <file>  Input: analysis config file
  --type <str>          type to extract from pq
  --study_id <str>      study_id to extract from pq
  --chrom <str>         chrom to extract from pq
  --phenotype_id <str>  phenotype_id to extract from pq
  --bio_feature <str>   bio_feature to extract from pq
  --method [conditional|distance]
                        Which method to run, either with conditional analysis
                        (gcta-cojo) or distance based with conditional
  --pval_threshold <float>
                        P-value threshold to be considered "significant"
  --run_finemap         If True, then run FINEMAP
  --toploci <file>      Output: top loci json file
  --credset <file>      Output: credible set json file
  --finemap <file>      Output: finemap snp probabilities file
  --log <file>          Output: log file
  --tmpdir <file>       Output: temp dir
  --delete_tmpdir       Remove temp dir when complete

Note: The capability of running FINEMAP has been used but not extensively tested.
```

### Running the pipeline

#### Step 1: Prepare input data

[Prepare summary statistic files](https://github.com/opentargets/genetics-sumstat-data/), including ["significant" window extraction](https://github.com/opentargets/genetics-sumstat-data/tree/master/filters/significant_window_extraction) to reduce input size.

Prepare LD references in plink `bed|bim|fam` format, currently using [UK Biobank downsampled to 10K individuals and lifted over to GRCh38](https://github.com/opentargets/genetics-backend/tree/master/reference_data/uk_biobank_v3).

Download to local machine using `gsutil -m rsync`.
```
cd ~/genetics-finemapping
mkdir -p data/ukb_v3_downsampled10k
gsutil -m rsync gs://open-targets-ukbb/genotypes/ukb_v3_downsampled10k/ $HOME/genetics-finemapping/data/ukb_v3_downsampled10k/

mkdir -p $HOME/genetics-finemapping/data/filtered/significant_window_2mb/gwas
gsutil -m rsync -r gs://genetics-portal-dev-sumstats/filtered/significant_window_2mb/gwas_new/ $HOME/genetics-finemapping/data/filtered/significant_window_2mb/gwas/

```

#### Step 2: Prepare environment

```
# Set spark paths
export PYSPARK_SUBMIT_ARGS="--driver-memory 80g pyspark-shell"
export SPARK_HOME=/home/ubuntu/software/spark-2.4.0-bin-hadoop2.7
export PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-2.4.0-src.zip:$PYTHONPATH

conda-env create -n dsubenv -f dsub_env.yaml
source activate dsubenv

# Install docker (needed if we want to run dsub with --provider local)
sudo apt install docker.io
sudo usermod -a -G docker $USER  # Add current user to authorise docker group
# Need to re-connect to VM, then run...
docker run hello-world  # Test that docker works
```

#### Step 3: Make manifest file

The manifest file specifies all analyses to be run. The manifest is a JSON lines file with each line containing the following fields:

```json
{
  "type": "gwas",
  "study_id": "NEALE2_50_raw",
  "phenotype_id": null,
  "bio_feature": null,
  "chrom": "6",
  "in_pq": "/home/ubuntu/data/sumstats/filtered/significant_window_2mb/gwas/NEALE2_50_raw.parquet",
  "in_ld": "/home/ubuntu/data/genotypes/ukb_v3_downsampled10k_plink/ukb_v3_chr{chrom}.downsampled10k",
  "out_top_loci": "/home/ubuntu/results/finemapping/output/study_id=NEALE2_50_raw/phenotype_id=None/bio_feature=None/chrom=6/top_loci.json.gz",
  "out_credset": "/home/ubuntu/results/finemapping/output/study_id=NEALE2_50_raw/phenotype_id=None/bio_feature=None/chrom=6/credible_set.json.gz",
  "out_log": "/home/ubuntu/results/finemapping/logs/study_id=NEALE2_50_raw/phenotype_id=None/bio_feature=None/chrom=6/logfile.txt",
  "tmpdir": "/home/ubuntu/results/finemapping/tmp/study_id=NEALE2_50_raw/phenotype_id=None/bio_feature=None/chrom=6",
  "method": "conditional",
  "pval_threshold": 5e-08
}
```

Note that the wildcard `{chrom}` can be used in `in_ld` field.

The manifest file can be automatically generated using:

```
cd ~/genetics-finemapping

# Edit the Args and Paths in `1_scan_input_parquets.py`
nano 1_scan_input_parquets.py

# Reads variants filtered for p value, and outputs a single json record in
# tmp/filtered_input for each study/chromosome combination with at least one
# significant variant. Takes a couple of minutes for 200 GWAS.
python 1_scan_input_parquets.py

# Creates manifest file, one job per study/chromosome. Output path `configs/manifest.json.gz`
python 2_make_manifest.py
```

#### Step 4: Run pipeline

```
mkdir logs
tmux   # So run continues if connection is lost

# Edit args in `4_run_commands.sh` (e.g. number of cores) and then
time bash 4_run_commands.sh

# Exit tmux with Ctrl+b then d
```

The above command will run all analyses specified in the manifest using GNU parallel. It will create two files `commands_todo.txt.gz` and `commands_done.txt.gz` showing which analyses have not yet/already been done. The pipeline can be stopped at any time and restarted without repeating any completed analyses. You can safely regenerate the `commands_*.txt.gz` commands whilst the pipeline is running using `python 3_make_commands.py --quiet`.

If you get this error:
  ModuleNotFoundError: No module named 'dask'
then I've solved it just by deactivating conda and reactivating. This seems to happen especially when using tmux... I'm not sure why.

#### Step 5: Process the results

```
# Combine the results of all the individual analyses
# This step can be slow/inefficient due to Hadoop many small files problem
time python 5_combine_results.py

# Make a note as to what this finemapping run contained. E.g.:
echo "Run to add Covid-19 R4 GWAS results" > results/README.txt

# Copy the results to GCS
bash 6_copy_results_to_gcs.sh
```

### Other notes

I did a test run on two different VM instances where I fine-mapped 15 GWAS.
One VM had a balanced persistent disk (200 Gb), one had an SSD (200 Gb). Otherwise they both were N2-standard-8 configurations.
The result was that the SSD version took about 4% longer than the standard disk. I did not try with a local SSD, but I suspect that the disk makes no difference, since the pipeline is CPU-bound.

##### Useful commands

```
# Parse time taken for each run
grep "Time taken" logs/study_id=*/phenotype_id=*/bio_feature=*/chrom=*/logfile.txt
ls -rt logs/study_id=*/phenotype_id=*/bio_feature=*/chrom=*/logfile.txt | xargs grep "Time taken"

# List all
ls logs/study_id=*/phenotype_id=*/bio_feature=*/chrom=*/logfile.txt
```

##### Notes

- Currently fails for sex chromosomes
  - Need to replace X with 23 in plink file or when specifying gcta command
  - Need to impute sex in plink file for X for cojo to work
- Manifest NAs must be represented with "None"
- P-value threshold is specified in 1_scan_input_parquets.py. Set to 5e-8 for GWAS, and (0.05 / num_tests) for mol trait