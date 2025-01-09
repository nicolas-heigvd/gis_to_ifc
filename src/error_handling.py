#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 7 10:24:00 2024
# Copyright (C) 2024-present {nicolas.blanc} @ HEIG-VD
# This file is licensed under the GPL-3.0-only. See LICENSE file for details.
# Third-party libraries and their licenses are listed in the NOTICE.md file.
"""

# %%
import atexit
import sys
from pathlib import Path

from logging_config import logger

# %%

exit_code = 0


@atexit.register
def exit_handler():
    if exit_code:
        print(
            f'Exiting the script "{__file__}" due to an error ({exit_code=}). '
            "Please review the log for any errors."
        )
    else:
        pass


# %%


def check_file(input_path: Path):
    """Check if a file exists, is not a directory, and is accessible.
    This is a helper function.

    Parameters:
    ----------
    input_path : Path
        The path to a file whose existence needs to be checked.

    Returns:
    -------
    nothing; the function exit the script if the path is not a valid file.
    """
    global exit_code
    exit_code = 1
    try:
        with open(input_path, "r"):
            exit_code = 0
    except FileNotFoundError:
        logger.error(f'File "{input_path}" does not exist.')
        sys.exit(1)
    except IsADirectoryError:
        logger.error(f'File "{input_path}" is a directory, not a file.')
        sys.exit(1)
    except PermissionError:
        logger.error(f'Permission denied to access "{input_path}".')
        sys.exit(1)
    except TypeError:
        logger.error(f'Invalid type for file "{input_path}".')
        sys.exit(1)
    except Exception as e:
        logger.error(
            f'An unexpected error occurred when trying to open file "{input_path}": {e}.'
        )
        sys.exit(1)
