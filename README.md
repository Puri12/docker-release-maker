## Overview

The Atlassian Docker Release Maker is a tool for automating the building,
testing, tagging and publishing of Docker images for Atlassian's Server
products. It uses the Atlassian Marketplace and Docker Hub API's to determine
available and published versions, and has the ability to apply complex tagging
to images, pass custom build arguments to builds and select specified
Dockerfiles for building. As the generated Docker image is used as a run-time
image for Atlassian product Docker-image build & test pipelines it also includes
tools and dependencies, including Python test dependencies; see the
[Dockerfile](Dockerfile) and [requirements.txt](requirements.txt) for details.

## Configuration

Docker Release Maker can be run via Bitbucket Pipelines to create new images for
unreleased product versions, or to rebuild and update all published images. 

The easiest way to configure Docker Release Maker is to set the desired options as
environment variables, and then call `run.py --create` to create new releases or
`run.py --update` to update all releases. The `--create-eap` flag can also be used to
create EAP releases if they're available.

A typical Pipelines configuration looks like this:


```
image: atlassian/docker-release-maker:latest

pipelines:
  custom:
    new-releases:
      - step:
          name: Jira Software
          services:
            - docker
          script:
            - export START_VERSION='8'
            - export END_VERSION='9'
            - export CONCURRENT_BUILDS='4'
            - export DEFAULT_RELEASE='true'
            - export DOCKER_REPO='dchevell/jira-software'
            - export DOCKERFILE_BUILDARGS='ARTEFACT_NAME=atlassian-jira-software'
            - export DOCKERFILE_VERSION_ARG='JIRA_VERSION'
            - export MAC_PRODUCT_KEY='jira-software'
            - export TAG_SUFFIXES='jdk8,ubuntu'
            - echo ${DOCKER_PASSWORD} | docker login --username ${DOCKER_USERNAME} --password-stdin
            - python /usr/src/app/run.py --create
```

Note that in the example above, `docker login` is called directly and Docker Release Maker
simply uses the existing authentication.

A more comprehensive list of examples can be found in **bitbucket-pipelines.yml.example** 
inside this repository.


### Required parameters

* `START_VERSION`

   The floor value of versions to build images for (inclusive). This can be any level of
   precision, e.g. '8', '8.1', or '8.1.2'.

* `END_VERSION`

   The ceiling value of versions to build images for (exclusive). This can be any level of
   precision, e.g. '9', '9.1', or '9.1.2'. If not set, this will default to the major
   version component of `START_VERSION` + 1. 

* `BASE_VERSION`

   The major version to build images for (deprecated). If `START_VERSION` is set, this is
   ignored.

* `DOCKER_REPO`

   The Docker Hub repository name. This is used both to check existing published tags,
   and to push new builds.

* `DOCKERFILE_VERSION_ARG`

   The build argument in the Dockerfile that specifies product version. The Dockerfile
   should use this to retrieve / install the correct product version.

* `MAC_PRODUCT_KEY`

   The product key used by the Atlassian Marketplace API, to determine available releases. 
   Valid values include:
   * bamboo
   * bitbucket
   * confluence
   * crowd
   * fisheye
   * jira
   * jira-software
   * jira-servicedesk


### Optional parameters

* `CONCURRENT_BUILDS` (default: 4)

   The number of images to build concurrently. This may be increased to improve time to
   completion when building a large number of images, or reduced in constrained 
   environments. The default value should be optimal in a standard Bitbucket Pipelines
   environment.

* `DEFAULT_RELEASE` (default: false)

   Whether the build should be considered the default. When this is true, "plain" version 
   tags and the `latest` tag will be applied. This is useful when there are multiple 
   variations of an image available, e.g. based on different JDK versions or with 
   different base OS images, and one needs to be set as the default. In cases where no
   variants exist it is highly recommended that this be set to `true`. See "Tagging" for 
   more info on how tags are calculated and applied. 

* `DOCKERFILE` (default: Dockerfile)

   Specify a custom Dockerfile path to use. This can be useful if multiple Dockerfile
   variations exist in the one repo, e.g. secondary Alpine builds. The value can include
   folder paths, and should point to a specific Dockerfile name, e.g. 
   `path/to/Dockerfile-custom`

* `DOCKERFILE_BUILDARGS` (default: none)

   Specify additional custom build arguments to be applied to images at build time. This
   can be used in a number of ways: to override the base image in templates that specify
   the base as a build arg; to specify custom versions of dependencies in images; etc.
   This relies on the Dockerfile supporting the build arguments. Build arguments should be
   specified as comma separated key=value pairs, e.g.
   `DOCKERFILE_BUILDARGS='BASE_IMAGE=adoptopenjdk/openjdk11:slim,ADDITIONAL_PACKAGES=vim telnet'`

* `TAG_SUFFIXES` (default: none)

   Additional suffixes to create suffixed tags for. When present, suffixed version tags
   will be applied. This should be a comma separated list of desired tag suffixes, e.g. 
   `TAG_SUFFIXES='ubuntu,jdk8'`. See "Tagging" for more info on how tags are calculated 
   and applied. 

* `PUSH_DOCKER_IMAGE` (default: true)

  Whether to push the image to the specified repo. Usually set to false on
  PRs/branches.

* `INTEGRATION_TEST_SCRIPT`: (default: '/usr/src/app/integration_test.sh')

  The test script to run after the build of each image. If the script returns
  non-zero the release process will end. It defaults to the
  `integration_test.sh` script in this repository. This script performs security
  scanning using the same tooling used by Atlassian internally, and run the
  script `func-tests/run-functests` in the calling repository if available. The
  `run-functests` script should accept a single parameter, the target image hash
  or tag. See [the Jira container functests](https://bitbucket.org/atlassian-docker/docker-atlassian-jira/src/master/)
  for an example. Optionally, this script can be overridden via the environment
  variable `FUNCTEST_SCRIPT`.

## Tagging

One of the primary features of this tool is tagging support. At build time, all relevant
tags are calculated, and are added to a single image build. This ensures that there is
only a single published artefact for a given version, regardless of how many tags are
applied. 

For configurations where `DEFAULT_RELEASE` is `true` then "plain" version tags will be
added. Given the example version "6.5.4" the following plain tags may be created:


* `6.5.4`

   The full `major.minor.patch` version tag. This is always added.

* `6.5`

   The `major.minor` version tag. Only added if `6.5.4` is the most recent release 
   for this minor version.

* `6`

   The `major` version tag. Only added if `6.5.4` is the most recent release for this
   major version.

* `latest`

   The default Docker Hub tag (equivalent to no tag specified). Only added if `6.5.4` is
   the most release of the product.

It's highly recommended that at least one build be set to default to ensure plain tags
are created.


For configurations where `TAG_SUFFIXES` is defined then additional suffix tags will be 
added for each suffix. Given the example suffix "ubuntu" the following tags may be
created:

* `6.5.4-ubuntu`

   The full `major.minor.patch-suffix` version tag. This is always added.

* `6.5-ubuntu`

   The `major.minor-suffix` version tag. Only added if `6.5.4` is the most recent release 
   for this minor version.

* `6-ubuntu`

   The `major-suffix` version tag. Only added if `6.5.4` is the most recent release for
   this major version.

* `ubuntu`

   The default suffix tag. Only added if `6.5.4` is the most recent release of the
   product.


`TAG_SUFFIXES` may be applied to both default and non-default release configurations.
