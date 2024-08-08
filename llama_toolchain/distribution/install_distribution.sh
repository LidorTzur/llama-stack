#!/bin/bash

# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

LLAMA_MODELS_DIR=${LLAMA_MODELS_DIR:-}
LLAMA_TOOLCHAIN_DIR=${LLAMA_TOOLCHAIN_DIR:-}
USE_TEST_PYPI=${USE_TEST_PYPI:-}

set -euo pipefail

# Define color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

error_handler() {
  echo "Error occurred in script at line: ${1}" >&2
  exit 1
}

# Set up the error trap
trap 'error_handler ${LINENO}' ERR

ensure_conda_env_python310() {
  local env_name="$1"
  local pip_dependencies="$2"
  local python_version="3.10"

  # Check if conda command is available
  if ! command -v conda &>/dev/null; then
    echo -e "${RED}Error: conda command not found. Is Conda installed and in your PATH?${NC}" >&2
    exit 1
  fi

  # Check if the environment exists
  if conda env list | grep -q "^${env_name} "; then
    echo "Conda environment '${env_name}' exists. Checking Python version..."

    # Check Python version in the environment
    current_version=$(conda run -n "${env_name}" python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)

    if [ "$current_version" = "$python_version" ]; then
      echo "Environment '${env_name}' already has Python ${python_version}. No action needed."
    else
      echo "Updating environment '${env_name}' to Python ${python_version}..."
      conda install -n "${env_name}" python="${python_version}" -y
    fi
  else
    echo "Conda environment '${env_name}' does not exist. Creating with Python ${python_version}..."
    conda create -n "${env_name}" python="${python_version}" -y
  fi

  eval "$(conda shell.bash hook)"
  conda deactivate && conda activate "${env_name}"

  PIP_ARGS=""
  if [ "$USE_TEST_PYPI" = "1" ]; then
    # these packages are damaged in test-pypi, so install them first
    pip install fastapi libcst
    PIP_ARGS="--extra-index-url https://test.pypi.org/simple/"
  fi
  # Re-installing llama-toolchain in the new conda environment
  if [ -n "$LLAMA_TOOLCHAIN_DIR" ]; then
    if [ ! -d "$LLAMA_TOOLCHAIN_DIR" ]; then
      echo -e "${RED}Warning: LLAMA_TOOLCHAIN_DIR is set but directory does not exist: $LLAMA_TOOLCHAIN_DIR${NC}" >&2
      exit 1
    fi

    echo "Installing from LLAMA_TOOLCHAIN_DIR: $LLAMA_TOOLCHAIN_DIR"
    pip install -e "$LLAMA_TOOLCHAIN_DIR"
  else
    pip install $PIP_ARGS llama-toolchain
  fi

  if [ -n "$LLAMA_MODELS_DIR" ]; then
    if [ ! -d "$LLAMA_MODELS_DIR" ]; then
      echo -e "${RED}Warning: LLAMA_MODELS_DIR is set but directory does not exist: $LLAMA_MODELS_DIR${NC}" >&2
      exit 1
    fi

    echo "Installing from LLAMA_MODELS_DIR: $LLAMA_MODELS_DIR"
    pip uninstall -y llama-models
    pip install -e "$LLAMA_MODELS_DIR"
  fi

  # Install pip dependencies
  if [ -n "$pip_dependencies" ]; then
    echo "Installing pip dependencies: $pip_dependencies"
    pip install $PIP_ARGS $pip_dependencies
  fi
}

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <environment_name> <distribution_name> <pip_dependencies>" >&2
  echo "Example: $0 my_env local-inline 'numpy pandas scipy'" >&2
  exit 1
fi

env_name="$1"
distribution_name="$2"
pip_dependencies="$3"

ensure_conda_env_python310 "$env_name" "$pip_dependencies"

echo -e "${GREEN}Successfully setup distribution environment. Configuring...${NC}"

python_interp=$(conda run -n "$env_name" which python)
$python_interp -m llama_toolchain.cli.llama distribution configure --name "$distribution_name"
