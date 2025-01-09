#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 7 10:24:00 2024
# Copyright (C) 2024-present {nicolas.blanc} @ HEIG-VD
# This file is licensed under the GPL-3.0-only. See LICENSE file for details.
# Third-party libraries and their licenses are listed in the NOTICE.md file.
"""

# %%
from pathlib import Path

from geo2ifc.fetch_swissalti import run as run_fs
from geo2ifc.ifc_functions import run as run_ifc
from logging_config import logger

# %%
# Triggers and constants
BASEDIR = "/data"
# %%

# Parsing directories
directories = Path(BASEDIR).glob("*/")

# %%
if __name__ == "__main__":
    run_fs()
    run_ifc()

logger.info(f'Script "{__file__}" run successfully! Bye.')
# %%
