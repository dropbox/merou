#!/bin/bash -eux

LS_FILES_PATH=${1:-}

EXCLUDE="(model_soup.py$)"

export LC_ALL=C
FILES=$(git ls-files $LS_FILES_PATH | grep '\.py$' | egrep -v  "$EXCLUDE" | tr '\n' '\0' | xargs -0 grep -ls '# type:' | cat)
STUBS=$(git ls-files $LS_FILES_PATH | grep '\.pyi$' | egrep -v  "$EXCLUDE" | cat)

mypy --silent-imports --py2 ${FILES} ${STUBS}
