#!/bin/bash

check_for_failure() {
    exit_code=$1
    if [ $exit_code -ne 0 ]; then
        TEST_RESULT=1
    fi
}

# snyk Authentication
snyk auth $SNYK_TOKEN

# perform security scan
snyk container test $1 --severity-threshold=high
# evaluate the result
check_for_failure $?

#Next test can run here follow by evaluation for falure
#check_for_failure $?

exit $TEST_RESULT