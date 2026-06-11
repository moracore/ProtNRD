#!/bin/bash

set -eo pipefail

PROJECT_DIR="/users/sggnewto/_ProtNRD/"
LOG_DIR="${PROJECT_DIR}/slurm_logs"
mkdir -p "${LOG_DIR}"

echo "Changing to project directory: ${PROJECT_DIR}"
cd "${PROJECT_DIR}" || { echo "Error: Project directory not found"; exit 1; }

echo "Submitting Pipeline 1 (Joins)..."
JOB1_ID=$(sbatch --parsable p1.sh)
if [[ -z "$JOB1_ID" ]]; then
    echo "Error submitting p1.sh"
    exit 1
fi
echo "Pipeline 1 submitted. Job ID: ${JOB1_ID}"

echo "Submitting Pipeline 2 (Cache), dependent on Job ${JOB1_ID}..."
JOB2_ID=$(sbatch --parsable --dependency=afterok:${JOB1_ID} p2.sh)
if [[ -z "$JOB2_ID" ]]; then
    echo "Error submitting p2.sh"
    exit 1
fi
echo "Pipeline 2 submitted. Job ID: ${JOB2_ID}"

echo "Submitting Pipeline 3 (Cleanup), dependent on Job ${JOB2_ID}..."
JOB3_ID=$(sbatch --parsable --dependency=afterok:${JOB2_ID} p3.sh)
if [[ -z "$JOB3_ID" ]]; then
    echo "Error submitting p3.sh"
    exit 1
fi
echo "Pipeline 3 submitted. Job ID: ${JOB3_ID}"

echo ""
echo "Successfully submitted all v0.8 pipeline jobs."
echo "  Step 1 (Joins):   ${JOB1_ID}"
echo "  Step 2 (Cache):   ${JOB2_ID} (depends on ${JOB1_ID})"
echo "  Step 3 (Cleanup): ${JOB3_ID} (depends on ${JOB2_ID})"
echo "Use 'squeue -u $USER' to monitor job status."