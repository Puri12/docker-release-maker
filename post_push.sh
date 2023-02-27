#!/bin/sh

# This script will invoke Snyk for an image release:
#
#   Usage: <path-to>/post_push.sh <repo/image:tag>

function sync_container_monitoring() {
    echo "######## Snyk container Monitoring ########"
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
}

function call_snyk_with_retry() {
  set +e
  local max_retries=3
  local retries=${max_retries}
  local delay=1

  while (( retries > 0 )); do
      sync_container_monitoring
      exit_code=$?
      if [[ $exit_code -eq 0 ]]; then
          break
      else
        (( retries-- ))
        echo "Failed to setup Snyk container monitoring. Will retry in ${delay} seconds..."
        sleep $delay
      fi
  done

  if [[ $retries -eq 0 ]]; then
      echo "Snyk container monitoring failed after ${max_retries} retries."
      exit 1
  fi
  set -e
}

if [ $# -eq 0 ]; then
    echo "No docker image supplied. Syntax: post_push.sh <repo/image:tag> ['true' if prerelease version]"
    exit 1
fi
IMAGE=$1
IS_PRERELEASE=${2:-false}

if [ x"$IS_PRERELEASE" != "xtrue" ]; then
    call_snyk_with_retry
else
  echo "Image ${IMAGE} is flagged as pre-release, skipping Snyk monitoring."
  exit 0
fi
