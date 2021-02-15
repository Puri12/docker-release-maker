#!/bin/sh

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: integration_test.sh <docker image> ['true' if no a published image]"
    exit 1
fi
image=$1
no_push=${2:-false}

TEST_RESULT=0
check_for_failure() {
    if [ $1 -ne 0 ]; then
        TEST_RESULT=$1
    fi
}

# PATTERN to run integration tests:
# 1. test preparation commands
# 2. run test command
# 3. capture test result immediately after the test command (exit_code=$?)
# 4. evaluate test result (check_for_failure $exit_code)
# repeat those steps for next test

# TEST: SECURITY SCAN
# Test preparation
if [[ -z "${SNYK_TOKEN}" ]]; then
    echo 'Security scan is interrupted because Snyk authentication token ($SNYK_TOKEN) is not defined!'
    exit 1
fi
snyk auth $SNYK_TOKEN

echo Performing security scan for image $image (high-impact vulnerabilities only)
snyk container test $image --severity-threshold=high
exit_code=$?
check_for_failure $?

# If we're releasing the image we should enable monitoring:
if [ $no_push = false ]; then
    echo Enabling Snyk monitoring for image $image
    snyk container monitor $image --severity-threshold=high
else
    echo no_push flag set, skipping Snyk monitoring
fi

# TODO: Add integration testing here

exit $TEST_RESULT
