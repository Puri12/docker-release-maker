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

The easiest way to configure Docker Release Maker is to set the desired options
on the command-line, and then call `make-releases.py --create` to create new
releases or `make-releases.py --update` to update all releases. The
`--create-eap` flag can also be used to create EAP releases if they're
available.

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
            - echo ${DOCKER_PASSWORD} | docker login --username ${DOCKER_USERNAME} --password-stdin
            - >
              python make-releases.py 
                --update
                --start-version='7.13'
                --end-version='9'
                --default-release
                --dockerfile-buildargs='ARTEFACT_NAME=atlassian-jira-software,BASE_IMAGE=adoptopenjdk:8-hotspot'
                --dockerfile-version-arg='JIRA_VERSION'
                --mac-product-key='jira-software'
                --tag-suffixes=''
                --concurrent-builds='1'
                --job-offset='0'
                --jobs-total='12'
                --docker-repos='atlassian/jira-software'
                --push
```

Note that in the example above, `docker login` is called directly and Docker Release Maker
simply uses the existing authentication.

More comprehensive examples can be found in the Atlassian Docker image
repositories, e.g: https://bitbucket.org/atlassian-docker/docker-atlassian-jira/src/master/bitbucket-pipelines.yml

### Required parameters

* `--start-version`

   The floor value of versions to build images for (inclusive). This can be any level of
   precision, e.g. '8', '8.1', or '8.1.2'.

* `--end-version`

   The ceiling value of versions to build images for (exclusive). This can be any level of
   precision, e.g. '9', '9.1', or '9.1.2'. If not set, this will default to the major
   version component of `--start-version` + 1. 

* `--base-version`

   The major version to build images for (deprecated). If `--start-version` is set, this is
   ignored.

* `--docker-repo`

   The Docker Hub repository name. This is used both to check existing published tags,
   and to push new builds.

* `--dockerfile-version-arg`

   The build argument in the Dockerfile that specifies product version. The Dockerfile
   should use this to retrieve / install the correct product version.

* `--mac-product-key`

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

* `--concurrent-builds` (default: 1)

   The number of images to build concurrently. This may be increased to improve time to
   completion when building a large number of images, or reduced in constrained 
   environments. The default value should be optimal in a standard Bitbucket Pipelines
   environment.

* `--default-release` (default: false)

   Whether the build should be considered the default. When this is true, "plain" version 
   tags and the `latest` tag will be applied. This is useful when there are multiple 
   variations of an image available, e.g. based on different JDK versions or with 
   different base OS images, and one needs to be set as the default. In cases where no
   variants exist it is highly recommended that this be set to `true`. See "Tagging" for 
   more info on how tags are calculated and applied. 

* `--dockerfile` (default: Dockerfile)

   Specify a custom Dockerfile path to use. This can be useful if multiple Dockerfile
   variations exist in the one repo, e.g. secondary Alpine builds. The value can include
   folder paths, and should point to a specific Dockerfile name, e.g. 
   `path/to/Dockerfile-custom`

* `--dockerfile-buildargs` (default: none)

   Specify additional custom build arguments to be applied to images at build time. This
   can be used in a number of ways: to override the base image in templates that specify
   the base as a build arg; to specify custom versions of dependencies in images; etc.
   This relies on the Dockerfile supporting the build arguments. Build arguments should be
   specified as comma separated key=value pairs, e.g.
   `--dockerfile-buildargs='BASE_IMAGE=adoptopenjdk/openjdk11:slim,ADDITIONAL_PACKAGES=vim telnet'`

* `--tag-suffixes` (default: none)

   Additional suffixes to create suffixed tags for. When present, suffixed version tags
   will be applied. This should be a comma separated list of desired tag suffixes, e.g. 
   `TAG_SUFFIXES='ubuntu,jdk8'`. See "Tagging" for more info on how tags are calculated 
   and applied. 

* `--push` (default: false)

  Whether to push the image to the specified repo. Usually set to false on
  PRs/branches.

* `--post-build-hook`: (default: 'usr/src/app/post_build.sh')

  The script to run after the build of each image. If the script returns
  non-zero the release process will end. It defaults to the
  `post_build.sh` script in this repository. For more details on this
  script see the section below.

* `--post-push-hook`: (default: 'usr/src/app/post_push.sh')

  The script to run after the push of each image. If the script returns
  non-zero the release process will end. It defaults to the
  `post_push.sh` script in this repository. For more details on this
  script see the section below.

### Post build/push image validation scripts

As noted above, the release-manager will invoke certain scripts at the
post-build and post-push phases. These default to the included ones, but can be
overridden on the commandline:

#### Post Build Hook

This is invoked after the image is built but before it is pushed to the
repository. Its purpose is to run any functional, acceptance or security tests
that are required before release.

The script takes the following arguments (provided by the release-manager):

* The hash of the locally built image.
* An optional flag for if the script is being invoked in the context of a
  release rather than a branch or PR build (defaults to false).
* An optional flag that specifies whether the functional tests should be run
  (defaults to true)

The default script will perform the following actions:

* Invoke a linter for the Dockerfile(s). The linter used can be overridden by setting the `DOCKER_LINT`
  environment variable; this default to [hadolint](https://github.com/hadolint/hadolint). 
* Invoke [Snyk](https://snyk.io/) [local container testing](https://docs.snyk.io/products/snyk-container/snyk-cli-for-container-security)
  against the supplied image.
* If functional test flag is `true`, and the file `func-tests/run-functests` (in
  the product Docker repository) exists and is executable it is invoked with the
  image.  For an example of this see [the Jira container
  functests](https://bitbucket.org/atlassian-docker/docker-atlassian-jira/src/master/)
  functional testing script. Optionally, this script can be overridden via the
  environment variable `FUNCTEST_SCRIPT`.

#### Post Push Hook

This is invoked after the image is pushed to the repository. It's initial
purpose is to enable ongoing security monitoring of published images.

The script takes the following arguments (provided by the release-manager):

* The tag of the image to monitor (usually in `<repository>/<image-name>:<version>` format).

The default script will perform the following actions:

* Invokes the Snyk security scanner in [container monitoring mode](https://docs.snyk.io/products/snyk-container/snyk-cli-for-container-security).

## Tagging

One of the primary features of this tool is tagging support. At build time, all relevant
tags are calculated, and are added to a single image build. This ensures that there is
only a single published artefact for a given version, regardless of how many tags are
applied. 

For configurations where `--default-release` is `true` then "plain" version tags will be
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


`--tag-suffixes` may be applied to both default and non-default release configurations.
