#!/bin/sh

# This script will untag EOL Snyk project so their vulnerabilities will not show up in DCD filter
#
#   Usage: <path-to>/snyk-untag.sh --token=<snyk-personal-token> --org-id=<snyk-organization-id> --regex-tag=<version|openjdk> [--project=<confluence-server|bitbucket-server..>]

set -e

if [ $# -lt 3 ]; then
    echo "Incorrect syntax. Usage: snyk-untag.sh --token=<snyk-personal-token> --org-id=<snyk-organization-id> --regex-tag=<version|openjdk> [--project=<confluence-server|bitbucket-server..>]"
    exit 1
fi

for i in "$@"
do
case $i in
    --project=*)
    PROJECT="${i#*=}"
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
      echo "ERROR: Unknown option ${i}"
      exit 0
    ;;
esac
done

echo "Gathering related snyk projects..."
echo "----------------------------------"

SNYK_PROJECTS=()
PROJECTS=()
DEFAULT_PROJECTS=("bitbucket-server" "bitbucket" "confluence-server" "confluence" "crowd" "jira-core" "jira-software"
                        "jira-servicemanagement" "jira-servicedesk" "bamboo" "bamboo-server" "bamboo-agent-base")

if [[ -z "$PROJECT" ]]
then
    PROJECTS=( "${DEFAULT_PROJECTS[@]}" )
else
    if [[ "$PROJECT" == *"bitbucket"* ]];
    then
        echo "Checking both bitbucket and bitbucket-server projects"
        PROJECTS=("bitbucket" "bitbucket-server")
    elif [[ "$PROJECT" == *"confluence"* ]];
    then
        echo "Checking both confluence and confluence-server projects"
        PROJECTS=("confluence" "confluence-server")
    elif [[ "$PROJECT" == *"jira-service"* ]];
    then
        echo "Checking both jira-servicemanagement and jira-servicedesk projects"
        PROJECTS=("jira-servicemanagement" "jira-servicedesk")
    elif [[ "$PROJECT" == *"jira"* ]];
    then
        echo "Checking all jira family projects: jira-core, jira-software, jira-servicemanagement and jira-servicedesk"
        PROJECTS=("jira-core" "jira-software" "jira-servicemanagement" "jira-servicedesk")
    elif [[ "$PROJECT" == *"bamboo"* ]];
    then
        echo "Checking both bamboo and bamboo-server projects"
        PROJECTS=("bamboo" "bamboo-server")
    elif [[ ! ${DEFAULT_PROJECTS[*]} =~ "$PROJECT" ]]
    then
        echo "ERROR: Project value must be one of these: ${DEFAULT_PROJECTS[@]}"
        exit 0
    else
        PROJECTS=("$PROJECT")
    fi
fi

if [[ ${PROJECTS[@]} == 0 ]];
then
    echo "No matched projects found"
    exit 0
fi

for PROJECT in "${PROJECTS[@]}";
do
    TAGS="$(echo "$(curl -s https://registry.hub.docker.com/v1/repositories/atlassian/$PROJECT/tags | jq -r '.[].name' | grep $REGEX_TAG)")"

    if [[ ! -z "$TAGS" ]]
    then
        for TAG in $TAGS
        do
            SNYK_PROJECTS+=("atlassian/$PROJECT:$TAG")
        done
    fi
done

for SNYK_PROJECT in "${SNYK_PROJECTS[@]}"
do
    echo $SNYK_PROJECT
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

for SNYK_PROJECT in "${SNYK_PROJECTS[@]}"
do
    PROJ_ID=$(curl -s -X POST \
         -H "Content-Type: application/json" \
         -H "Authorization:token $TOKEN" \
         -d "{\"filters\":{\"name\": \"$SNYK_PROJECT\"}}" \
         https://snyk.io/api/v1/org/$ORG_ID/projects \
         | jq -r ".projects[] | select(.name==\"$SNYK_PROJECT\")" \
         | jq -r ".id")

    if [ -z "$PROJ_ID" ]
    then
        echo "Skipped $SNYK_PROJECT - not monitored by Snyk"
    else
        curl -s -o /dev/null -X POST \
            -H "Content-Type: application/json" \
            -H "Authorization:token $TOKEN" \
            -d '{"key": "team-name","value": "dc-deployment"}' \
            https://snyk.io/api/v1/org/$ORG_ID/project/$PROJ_ID/tags/remove
        echo "Un-tagged $SNYK_PROJECT"
    fi

done

exit 0
