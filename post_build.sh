#!/bin/sh

set -e
# This script will do the following:
#
#  * Invoke Snyk for an image
#  * Perform linting of the Dockerfile(s)
#  * Optionally, run functional tests if present.
#
#   Usage: <path-to>/post_build.sh <IMAGE-ID-OR-HASH>  ['true' if a release image] ['true' if tests should be run] [<path-to-.snyk-file>]
#
# The release image flag defaults to false, the testing flag to true.

function snyk_container_test() {
  echo "######## Snyk container testing ########"
  echo "Authenticating with Snyk..."
  snyk auth -d $SNYK_TOKEN
  
  echo "Performing security scan for image $IMAGE (threshold=${SEV_THRESHOLD})"
  echo "Performing security scan from the directory [`pwd`]"
  
  if [ -f "$SNYK_FILE" ]; then
      echo "Performing security scan with .snyk policy file"
      snyk container test -d $IMAGE \
           --severity-threshold=$SEV_THRESHOLD \
           --exclude-app-vulns \
           --policy-path=$SNYK_FILE
  else
      snyk container test -d $IMAGE \
           --severity-threshold=$SEV_THRESHOLD \
           --exclude-app-vulns
  fi
}

function call_snyk_with_retry() {
  set +e
  local max_retries=3
  local retries=${max_retries}
  local delay=1

  while (( retries > 0 )); do
      snyk_container_test
      exit_code=$?
      if [[ $exit_code -eq 0 ]]; then
          break
      elif [[ $exit_code -eq 1 ]]; then
          exit 1
      # https://docs.snyk.io/snyk-cli/commands/container-test#exit-codes
      elif [[ $exit_code -eq 2 || $exit_code -eq 3 ]]; then
        (( retries-- ))
        echo "Failed to perform Synk container test. Will retry in ${delay} seconds..."
        sleep $delay
      fi
  done

  if [[ $retries -eq 0 ]]; then
      echo "Snyk container testing failed after ${max_retries} retries."
      exit 1
  fi
  set -e
}

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: post_build.sh <image tag or hash> ['true' if a release image]"
    exit 1
fi
IMAGE=$1
RUN_FUNCTESTS=${3:-true}
SNYK_FILE=${4:-'.snyk'}


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

call_snyk_with_retry

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
