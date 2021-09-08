#!/bin/sh

set -e

SHDIR=$(dirname $0)

pip install -q -r ${SHDIR}/requirements.txt

HADOLINT_VERSION=2.1.0
HADOLINT_URL=https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-Linux-x86_64
url -sL ${HADOLINT_URL} -o /usr/local/bin/hadolint
chmod +x /usr/local/bin/hadolint
