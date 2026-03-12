#!/usr/bin/env bash
#
# Bootstrap script for roman-photoz.
#
# This script:
#   1. Creates a .env file with LEPHAREDIR and LEPHAREWORK
#   2. Downloads only the auxiliary data required by the roman config
#   3. Creates Roman filter files and a simulated catalog
#   4. Runs the informer stage to produce the model pickle
#   5. Removes LEPHAREDIR folders not needed by the estimator
#
# Usage:
#   bash bootstrap_roman_photoz.sh [--nobj N] [--simulated-catalog-filename FILE]
#
# Options:
#   --nobj N                          Number of objects in simulated catalog (default: 1000)
#   --simulated-catalog-filename FILE Simulated catalog filename (default: roman_simulated_catalog.parquet)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LEPHARE_DATA="${SCRIPT_DIR}/lephare_data"
LEPHARE_WORK="${SCRIPT_DIR}/lephare_work"

# Use PYTHON_RUNNER to control how python and CLI commands are invoked.
# Examples:
#   PYTHON_RUNNER="uv run" bash bootstrap_roman_photoz.sh   # uses uv
#   PYTHON_RUNNER="conda run -n myenv" bash ...             # uses conda
#   bash bootstrap_roman_photoz.sh                          # bare python/pip
PYTHON_RUNNER="${PYTHON_RUNNER:-}"

# --- Parse arguments ---
NOBJ=1000
SIMULATED_CATALOG_FILENAME="roman_simulated_catalog.parquet"

while [[ $# -gt 0 ]]; do
  case "$1" in
  --nobj)
    NOBJ="$2"
    shift 2
    ;;
  --simulated-catalog-filename)
    SIMULATED_CATALOG_FILENAME="$2"
    shift 2
    ;;
  *)
    echo "Unknown option: $1"
    exit 1
    ;;
  esac
done

# --- Step 1: Create or load .env file ---
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  echo "==> .env file already exists at ${SCRIPT_DIR}/.env — loading it."
  set -a
  source "${SCRIPT_DIR}/.env"
  set +a
else
  echo "==> Creating .env file..."
  cat >"${SCRIPT_DIR}/.env" <<EOF
LEPHAREDIR=${LEPHARE_DATA}
LEPHAREWORK=${LEPHARE_WORK}
EOF
  echo "    Written to ${SCRIPT_DIR}/.env"
  export LEPHAREDIR="${LEPHARE_DATA}"
  export LEPHAREWORK="${LEPHARE_WORK}"
fi

# Create directories
mkdir -p "${LEPHAREDIR}" "${LEPHAREWORK}"

# --- Step 2: Download auxiliary data ---
echo "==> Downloading LePhare auxiliary data..."
${PYTHON_RUNNER} python -c "
from lephare.data_retrieval import get_auxiliary_data
from roman_photoz.default_config_file import default_roman_config

get_auxiliary_data(
    lephare_dir='${LEPHAREDIR}',
    keymap=default_roman_config,
    additional_files=[
        'examples/COSMOS_MOD.list',  # needed for the simulated catalog
    ],
)
print('Auxiliary data download complete.')
"

# --- Step 3: Create simulated catalog (also creates Roman filter files) ---
echo "==> Creating simulated catalog and Roman filter files..."
${PYTHON_RUNNER} roman-photoz-create-simulated-catalog \
  --nobj "${NOBJ}" \
  --output-path "${LEPHAREWORK}" \
  --output-filename "${SIMULATED_CATALOG_FILENAME}"

CATALOG_PATH="${LEPHAREWORK}/${SIMULATED_CATALOG_FILENAME}"
echo "    Simulated catalog: ${CATALOG_PATH}"

# --- Step 4: Run the informer stage ---
# Remove stale informer artifacts to ensure a clean build.
# The model pickle stores an absolute run_dir path from the original
# informer run; if it's stale, the estimator will look in the wrong place.
MODEL_PICKLE="${LEPHAREWORK}/roman_model.pkl"
if [[ -f "${MODEL_PICKLE}" ]]; then
    echo "==> Removing stale model pickle: ${MODEL_PICKLE}"
    rm -f "${MODEL_PICKLE}"
fi
# LephareInformer creates its run directory at $LEPHAREWORK/../inform_roman
INFORMER_RUN_DIR="$(cd "${LEPHAREWORK}/.." && pwd)/inform_roman"
if [[ -d "${INFORMER_RUN_DIR}" ]]; then
    echo "==> Removing stale informer run directory: ${INFORMER_RUN_DIR}"
    rm -rf "${INFORMER_RUN_DIR}"
fi

echo "==> Running informer + estimator stage..."
${PYTHON_RUNNER} roman-photoz --input-filename "${CATALOG_PATH}"
echo "    Model written to: ${LEPHAREDIR}/roman_model.pkl"

# --- Step 5: Remove intermediate files and clean up LEPHAREDIR folders not needed by the estimator ---
echo "==> Removing intermediate files..."
rm -f "${CATALOG_PATH}" "${LEPHAREWORK}/roman_photoz.log"
echo "==> Cleaning up LEPHAREDIR (keeping only opa/, ext/, alloutputkeys.txt)..."
for item in "${LEPHAREDIR}"/*; do
  name="$(basename "${item}")"
  case "${name}" in
  opa | ext | vega | alloutputkeys.txt)
    echo "    Keeping: ${name}"
    ;;
  *)
    echo "    Removing: ${name}"
    rm -rf "${item}"
    ;;
  esac
done

echo ""
echo "==> Bootstrap complete."
echo "    .env file:    ${SCRIPT_DIR}/.env"
echo "    Model:        ${LEPHAREWORK}/roman_model.pkl"
echo "    LEPHAREDIR:   ${LEPHAREDIR} (trimmed to estimator essentials)"
echo "    LEPHAREWORK:  ${LEPHAREWORK}"
echo ""
echo "To use in a new shell session:"
echo "    source ${SCRIPT_DIR}/.env && export LEPHAREDIR LEPHAREWORK"
