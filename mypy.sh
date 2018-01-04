#!/bin/bash -eux

LS_FILES_PATH=${1:-}

MYPY_ARGS=" --py2 --ignore-missing-imports --follow-imports=silent"
MYPY_TAG="# type:"

EXCLUDE="(^bin/|mypy.sh$)"

export LC_ALL=C
FILES=$(git grep -l "$MYPY_TAG" | egrep -v "$EXCLUDE")

mypy ${MYPY_ARGS} ${FILES}
