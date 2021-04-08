#!/bin/sh

# This script will invoke Snyk for an image release:
#
#   Usage: <path-to>/post_push.sh <repo/image:tag>


set -e

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: post_push.sh <repo/image:tag>"
    exit 1
fi
RELEASE=$1

echo "######## Security Scan ########"
SEV_THRESHOLD=${SEV_THRESHOLD:-high}

if [ x"${SNYK_TOKEN}" = 'x' ]; then
    echo 'Security scan is interrupted because Snyk authentication token (SNYK_TOKEN) is not defined!'
    exit 1
fi

echo "Authenticating with Snyk..."
snyk auth -d $SNYK_TOKEN

echo "Enabling Snyk monitoring for image $IMAGE"
snyk container monitor -d $RELEASE --severity-threshold=$SEV_THRESHOLD

exit 0
