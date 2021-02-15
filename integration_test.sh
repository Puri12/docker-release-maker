#!/bin/bash

TEST_RESULT=0

check_for_failure() {
    exit_code=$1
    if [ $exit_code -ne 0 ]; then
        TEST_RESULT=1
    fi
}

if [[ -z "${SNYK_TOKEN}" ]]; then
    echo 'Security scan is interrupted because Snyk authentication token (SNYK_TOKEN) is not defined!.'
    exit 1
fi

# snyk Authentication
snyk auth $SNYK_TOKEN

# perform security scan - ignoring low and medium vulnerabilities
snyk container test $1 --severity-threshold=high
# evaluate the result
check_for_failure $?

#Next test can run here follow by evaluation for falure
#check_for_failure $?

exit $TEST_RESULT