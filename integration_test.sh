#!/bin/sh

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: integration_test.sh <image tag or hash> ['true' if a release image]"
    exit 1
fi
image=$1
is_release=${2:-false}

TEST_RESULT=0
check_for_failure() {
    if [ $1 -ne 0 ]; then
        echo "Operation failed; flagging and continuing."
        TEST_RESULT=$1
    fi
}

echo "######## Security Scan ########"
SEV_THRESHOLD=high

if [ x"${SNYK_TOKEN}" = 'x' ]; then
    echo 'Security scan is interrupted because Snyk authentication token (SNYK_TOKEN) is not defined!.'
    exit 1
fi

echo "Authenticating with Snyk..."
snyk auth $SNYK_TOKEN

echo "Performing security scan for image $image (threshold=${SEV_THRESHOLD})"
snyk container test $image --severity-threshold=$SEV_THRESHOLD
exit_code=$?
check_for_failure $exit_code

# If we're releasing the image we should enable monitoring:
if [ $is_release = true ]; then
    echo "Enabling Snyk monitoring for image $image"
    snyk container monitor $image --severity-threshold=$SEV_THRESHOLD
    exit_code=$?
    check_for_failure $exit_code
else
    echo "Publish flag is not set, skipping Snyk monitoring"
fi

# TODO: Add integration testing here
#echo "######## Integration Testing ########"

exit $TEST_RESULT
