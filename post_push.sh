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

# Quick check if this is a 'full' (i.e. major.minor.patch) version:
THIRD=`echo $RELEASE | cut -d: -f2 | cut -d. -f3`
if [ x"$THIRD" != "x" ]; then
    FULL_VER=true
fi

if [ "$FULL_VER" != "true" ]; then
    echo "Version $RELEASE is not a full version tag, skipping security monitoring"
    exit 0
fi

echo "######## Security Image Monitoring ########"
SEV_THRESHOLD=${SEV_THRESHOLD:-high}

if [ x"${SNYK_TOKEN}" = 'x' ]; then
    echo 'Security scan is interrupted because Snyk authentication token (SNYK_TOKEN) is not defined!'
    exit 1
fi

echo "Authenticating with Snyk..."
snyk auth -d $SNYK_TOKEN

echo "Enabling Snyk monitoring for image $RELEASE"
# Note: A quirk of Snyk is that if we release a new version of the
# same container (e.g. mycontainer:1.0.1 → mycontainer:1.0.2), the
# former version will be removed and no longer monitored. As we
# need to support multiple concurrent versions of the same
# container (e.g. EAPs), we also set the project name, which will
# create a separate monitoring project for each version. We need
# to replace the ':' version delimiter to prevent Snyk attempting
# to parse it.
PROJECT=`echo $RELEASE | tr ':.' '-'`
snyk container monitor -d \
     --severity-threshold=$SEV_THRESHOLD \
     --project-name=$PROJECT \
     $RELEASE

exit 0
