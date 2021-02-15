# required parameter: docker image to test
TEST_RESULT=0

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: integration_test.sh <docker image>"
    exit 1
fi

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
# Run test command: perform security scan - ignoring low and medium vulnerabilities
snyk container test $1 --severity-threshold=high
# capture test result:
exit_code=$?
# evaluate test result:
check_for_failure $exit_code

# Next test can start here following the mentioned pattern:


exit $TEST_RESULT