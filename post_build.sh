#!/bin/sh

# This script will do the following:
#
#  * Invoke Snyk for an image
#  * Perform linting of the Dockerfile(s)
#  * Optionally, run functional tests if present.
#
#   Usage: <path-to>/post_build.sh <IMAGE-ID-OR-HASH>  ['true' if a release image] ['true' if tests should be run]
#
# The release image flag defaults to false, the testing flag to true.

set -e

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: post_build.sh <image tag or hash> ['true' if a release image]"
    exit 1
fi
IMAGE=$1
IS_RELEASE=${2:-false}
RUN_FUNCTESTS=${3:-true}


echo "######## Dockerfile Linting ########"
echo "Performing Dockerfile lint from the directory [`pwd`]"
DOCKER_LINT=${DOCKER_LINT:-'/usr/src/app/hadolint'}
for dockerfile in Dockerfile*; do
    echo "Linting ${dockerfile} ..."
    ${DOCKER_LINT} ${dockerfile}
done


echo "######## Security Scan ########"
SEV_THRESHOLD=${SEV_THRESHOLD:-high}

if [ x"${SNYK_TOKEN}" = 'x' ]; then
    echo 'Security scan is interrupted because Snyk authentication token (SNYK_TOKEN) is not defined!'
    exit 1
fi

echo "Authenticating with Snyk..."
snyk auth -d $SNYK_TOKEN

echo "Performing security scan for image $IMAGE (threshold=${SEV_THRESHOLD})"
echo "Performing security scan from the directory [`pwd`]"
snyk container test -d $IMAGE --severity-threshold=$SEV_THRESHOLD


echo "######## Integration Testing ########"
if [ $RUN_FUNCTESTS = true ]; then
    FUNCTEST_SCRIPT=${FUNCTEST_SCRIPT:-'./func-tests/run-functests'}
    if [ -x $FUNCTEST_SCRIPT ]; then
        echo "Invoking ${FUNCTEST_SCRIPT} ${IMAGE}"
        ${FUNCTEST_SCRIPT} $IMAGE
    else
        echo "Testing script ${FUNCTEST_SCRIPT} doesn't exist or is not executable; skipping."
    fi
else
    echo "Functest flag not set, skipping"
fi

exit 0
