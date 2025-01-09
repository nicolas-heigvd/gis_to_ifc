#!/bin/bash

# Created on Fri Nov 10 14:08:00 2024
# Copyright (C) 2024-present {nicolas.blanc} @ HEIG-VD
# This file is licensed under the GPL-3.0-only. See LICENSE file for details.
# Third-party libraries and their licenses are listed in the NOTICE.md file.

export DEBIAN_FRONTEND=noninteractive

cd /code \
  && apt-get -yq update \
  && apt-get -yq install --no-install-recommends git \
  && git config --global --add safe.directory $(pwd)

pip install --trusted-host pypi.python.org --upgrade pre-commit \
  && pre-commit install --config .pre-commit-config.yml \
  && pre-commit run --config .pre-commit-config.yml --all-files \
  && echo "pre-commit hooks executed successfully!"
