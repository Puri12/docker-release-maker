#!/bin/sh

# This script will untag EOLed Snyk project so their vulnerabilities will not show up in DCD filter
#
#   Usage: <path-to>/snyk-untag.sh --token=<snyk-personal-token> --org-id=<snyk-org-id> --regex-tag=<version|openjdk> [--product=<confluence-server|bitbucket-server..>]

set -e

if [ $# -lt 3 ]; then
    echo "Incorrect syntax. Usage: snyk-untag.sh --token=<snyk-personal-token> --org-id=<snyk-org-id> --regex-tag=<version|openjdk> [--product=<confluence-server|bitbucket-server..>]"
    exit 1
fi

for i in "$@"
do
case $i in
    --product=*)
    PRODUCT="${i#*=}"
    shift
    ;;
    --regex-tag=*)
    REGEX_TAG="${i#*=}"
    shift
    ;;
    --token=*)
    TOKEN="${i#*=}"
    shift
    ;;
    --org-id=*)
    ORG_ID="${i#*=}"
    shift
    ;;
    *)
      echo "Unknown option ${i}"
      exit 0
    ;;
esac
done

echo "Gathering related snyk projects..."
echo "----------------------------------"

SNYK_PROJECTS=()
PRODUCTS=()

if [[ -z "$PRODUCT" ]]
then
    PRODUCTS=("bitbucket-server" "bitbucket" "confluence-server" "confluence" "crowd" "jira-core" "jira-software"
                        "jira-servicemanagement" "jira-servicedesk" "bamboo" "bamboo-server" "bamboo-agent-base")
else
    PRODUCTS=("$PRODUCT")
fi

for PRODUCT in "${PRODUCTS[@]}";
do
    TAGS="$(echo "$(curl -s https://registry.hub.docker.com/v1/repositories/atlassian/$PRODUCT/tags | jq -r '.[].name' | grep $REGEX_TAG)")"

    if [[ ! -z "$TAGS" ]]
    then
        for TAG in $TAGS
        do
            SNYK_PROJECTS+=("atlassian/$PRODUCT:$TAG")
        done
    fi
done

for PROJECT in "${SNYK_PROJECTS[@]}"
do
    echo $PROJECT
done

echo "----------------------------------"
while true; do
    read -p "Please review the project lists and confirm to un-tag them (y/n): " yn
    case $yn in
        [Yy]* ) break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done

for PROJECT in "${SNYK_PROJECTS[@]}"
do
    PROJ_ID=$(curl -s -X POST \
         -H "Content-Type: application/json" \
         -H "Authorization:token $TOKEN" \
         -d "{\"filters\":{\"name\": \"$PROJECT\"}}" \
         https://snyk.io/api/v1/org/$ORG_ID/projects \
         | jq -r ".projects[] | select(.name==\"$PROJECT\")" \
         | jq -r ".id")

    if [ -z "$PROJ_ID" ]
    then
        echo "Skipped $PROJECT - not monitored by Snyk"
    else
        curl -s -o /dev/null -X POST \
            -H "Content-Type: application/json" \
            -H "Authorization:token $TOKEN" \
            -d '{"key": "team-name","value": "dc-deployment"}' \
            https://snyk.io/api/v1/org/$ORG_ID/project/$PROJ_ID/tags/remove
        echo "Un-tagged $PROJECT"
    fi

done

exit 0
