#!/bin/sh

# This script will invoke Snyk for an image release:
#
#   Usage: <path-to>/post_push.sh <repo/image:tag>

set -e

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: post_push.sh <repo/image:tag> ['true' if prerelease version]"
    exit 1
fi
IMAGE=$1
IS_PRERELEASE=${2:-false}

if [ x"$IS_PRERELEASE" != "xtrue" ]; then
    local retries=3
    local delay=10

    while (( retries > 0 )); do
        sync_container_monitoring
        if [[ $? -eq 0 ]]; then
            break
        fi
        (( retries-- ))
        echo "Failed to setup Snyk container monitoring. Will retry in 10 seconds..."
        sleep $delay
    done

    if [[ $retries -eq 0 ]]; then
        echo "Snyk container monitoring failed after $retries retries."
        return 1
    fi
fi

echo "Image ${IMAGE} is flagged as pre-release, skipping Snyk monitoring."
exit 0


function sync_container_monitoring() {
    echo "######## Security Scan ########"
    SEV_THRESHOLD=${SEV_THRESHOLD:-high}

    if [ x"${SNYK_TOKEN}" = 'x' ]; then
        echo 'Security scan is interrupted because Snyk authentication token (SNYK_TOKEN) is not defined!'
        exit 1
    fi

    echo "Authenticating with Snyk..."
    snyk auth -d $SNYK_TOKEN

    echo "Enabling Snyk monitoring for image $IMAGE."
    # Note: A quirk of Snyk is that if we release a new version of the
    # same container (e.g. mycontainer:1.0.1 → mycontainer:1.0.2), the
    # former version will be removed and no longer monitored. As we need
    # to support multiple concurrent versions of the same container
    # (e.g. EAPs), we also set the project name, which will create a
    # separate monitoring project for each version.
    snyk container monitor -d \
         --severity-threshold=$SEV_THRESHOLD \
         --exclude-app-vulns \
         --project-name=$IMAGE \
         --project-tags=team-name=dc-deployment \
         $IMAGE

    exit 0
}