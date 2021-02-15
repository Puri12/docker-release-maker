import concurrent.futures
import dataclasses
from enum import IntEnum
import json
import logging
import re
import time

import docker
import requests
import subprocess
import sys
import os


class VersionType(IntEnum):
     MILESTONE = 0
     BETA = 1
     RELEASE_CANDIDATE = 2
     RELEASE = 3


@dataclasses.dataclass(order=True, unsafe_hash=True)
class Version:
    major: [int,str] = 0
    minor: int = 0
    patch: int = 0
    build: int = 0
    rtype: VersionType = VersionType.RELEASE
    v_raw: str = ''

    def __post_init__(self):
        if isinstance(self.major, str):
            self.v_raw = self.major
            version_str, _, rtype = self.major.partition('-')
            version_index = {i: int(v) for i, v in enumerate(version_str.split('.'))}
            self.major = version_index.get(0, self.major)
            self.minor = version_index.get(1, self.minor)
            self.patch = version_index.get(2, self.patch)
            self.build = version_index.get(3, self.build)
            if 'beta' in rtype.lower():
                self.rtype = VersionType.BETA
            elif rtype.lower().startswith('rc'):
                self.rtype = VersionType.RELEASE_CANDIDATE
            elif rtype.lower().startswith('m'):
                self.rtype = VersionType.MILESTONE
            else:
                self.rtype = VersionType.RELEASE

def docker_tags(repo):
    logging.info(f'Retrieving Docker tags for {repo}')
    r = requests.get(f'https://index.docker.io/v1/repositories/{repo}/tags')
    if r.status_code == requests.codes.not_found:
        return set()
    tag_data = r.json()
    tags = {t['name'] for t in tag_data}
    return tags


def mac_versions(product_key, offset=0, limit=50):
    logging.info(f'Retrieving Marketplace product versions for {product_key}')
    mac_url = 'https://marketplace.atlassian.com'
    request_url = f'/rest/2/products/key/{product_key}/versions'
    params = {'offset': offset, 'limit': limit}
    versions = set()
    while True:
        r = requests.get(mac_url + request_url, params=params)
        version_data = r.json()
        for version in version_data['_embedded']['versions']:
            if all(d.isdigit() for d in version['name'].split('.')):
                versions.add(version['name'])
        if 'next' not in version_data['_links']:
            break
        request_url = version_data['_links']['next']['href']
        params = {}
    return versions


eap_version_pattern = re.compile(r'(\d+(?:\.\d+)+(?:-[a-zA-Z0-9]+)*)')
jira_product_key_mapper = {
    'jira': 'jira core',
    'jira-software': 'jira software',
    'jira-servicedesk': 'jira servicedesk',
}


def eap_versions(product_key):
    feed_key = product_key
    description_key = None
    if 'jira' in product_key:
        feed_key = 'jira'
        description_key = jira_product_key_mapper[product_key]
    r = requests.get(f'https://my.atlassian.com/download/feeds/eap/{feed_key}.json')
    data = json.loads(r.text[10:-1])
    versions = set()
    for item in data:
        if description_key is not None and description_key not in item['description'].lower():
                continue
        version = eap_version_pattern.search(item['description']).group(1)
        versions.add(version)
    return versions


def str2bool(v):
    if str(v).lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    return False


def parse_buildargs(buildargs):
    return dict(item.split("=") for item in buildargs.split(","))


class ReleaseManager:

    def __init__(self, start_version, end_version, concurrent_builds, default_release,
                 docker_repo, dockerfile, dockerfile_buildargs, dockerfile_version_arg,
                 mac_product_key, tag_suffixes, push_docker, test_script):
        self.start_version = Version(start_version)
        if end_version is not None:
            self.end_version = Version(end_version)
        else:
            self.end_version = Version(self.start_version.major + 1)
        self.concurrent_builds = int(concurrent_builds or 4)
        self.default_release = default_release
        self.docker_cli = docker.from_env()
        self.docker_repo = docker_repo
        self.docker_tags = docker_tags(docker_repo)
        self.dockerfile = dockerfile
        self.dockerfile_buildargs = dockerfile_buildargs
        self.dockerfile_version_arg = dockerfile_version_arg
        self.push_docker = push_docker
        self.test_script = test_script
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.concurrent_builds
        )
        self.mac_versions = mac_versions(mac_product_key)
        self.eap_versions = eap_versions(mac_product_key)
        self.release_versions = {v for v in self.mac_versions
                                 if self.start_version <= Version(v) < self.end_version}
        self.eap_release_versions = {v for v in self.eap_versions
                                 if Version(v) < self.end_version}
        self.tag_suffixes = set(tag_suffixes or set())

    def create_releases(self):
        logging.info('##### Creating new releases #####')
        versions_to_build = self.unbuilt_release_versions()
        return self.build_releases(versions_to_build)

    def update_releases(self):
        logging.info('##### Updating existing releases #####')
        versions_to_build = self.release_versions
        return self.build_releases(versions_to_build)

    def create_eap_releases(self):
        logging.info('##### Creating new EAP releases #####')
        versions_to_build = self.unbuilt_eap_versions()
        return self.build_releases(versions_to_build)

    def build_releases(self, versions_to_build):
        logging.info(
            f'Found {len(versions_to_build)} '
            f'release{"" if len(versions_to_build)==1 else "s"} to build'
        )
        logging.info(f'Building with {self.concurrent_builds} threads')
        if self.dockerfile is not None:
            logging.info(f'Using docker file "{self.dockerfile}"')
        builds = []
        for version in versions_to_build:
            build = self.executor.submit(self._build_release, version)
            builds.append(build)
        for build in concurrent.futures.as_completed(builds):
            exc = build.exception()
            if exc is not None:
                raise exc

    def _push_release(self, release):
        if not self.push_docker:
            return
        max_retries = 5
        for i in range(1, max_retries+1):
            try:
                logging.info(f'Pushing tag "{release}"')
                self.docker_cli.images.push(release)
            except requests.exceptions.ConnectionError as e:
                if i > max_retries:
                    logging.error(f'Push failed for tag "{release}"')
                    raise e
                logging.warning(f'Pushing tag "{release}" failed; retrying in {i}s ...')
                time.sleep(i)
            else:
                logging.info(f'Pushing tag "{release}" succeeded!')
                break

    def _build_release(self, version):
        buildargs = {self.dockerfile_version_arg: version}
        if self.dockerfile_buildargs is not None:
            buildargs.update(parse_buildargs(self.dockerfile_buildargs))
        buildargs_log_str = ', '.join(['{}={}'.format(*i) for i in buildargs.items()])
        logging.info(f'Building {self.docker_repo} with buildargs: {buildargs_log_str}')
        try:
            image = self.docker_cli.images.build(path='.',
                                                 buildargs=buildargs,
                                                 dockerfile=self.dockerfile,
                                                 rm=True)[0]
        except docker.errors.BuildError as exc:
            logging.error(
                f'Build for {self.docker_repo} with '
                f'{self.dockerfile_version_arg}={version} failed:\n\t{exc}'
            )
            raise exc

        # script will terminated with error if the test failed
        self._run_test_script(image.id)

        for tag in self.calculate_tags(version):
            release = f'{self.docker_repo}:{tag}'
            image.tag(self.docker_repo, tag=tag)

            self._push_release(release)

    def _run_test_script(self, release):
        if self.test_script != None:
            print(f'Running integration test script: {self.test_script}')
            if os.path.exists(self.test_script):
                # Usage: integration_test.sh <image-tag-or-hash> ['true' if release image]
                script_command = [self.test_script, release, str(not self.no_push).lower()]

                # run provided test script - terminate with error if the test failed
                proc = subprocess.run(script_command)
                if proc.returncode != 0:
                    sys.exit(1)
            else:
                print ("**Integration test is bypassed! '{test_script}' is not found! ")

    def unbuilt_release_versions(self):
        if self.default_release:
            return self.release_versions - self.docker_tags
        versions = set()
        for v in self.release_versions:
            for suffix in self.tag_suffixes:
                tag = f'{v}-{suffix}'
                if tag not in self.docker_tags:
                    versions.add(v)
        logging.info(versions)
        return versions

    def unbuilt_eap_versions(self):
        if self.default_release:
            return self.eap_release_versions - self.docker_tags
        versions = set()
        for v in self.eap_release_versions:
            for suffix in self.tag_suffixes:
                tag = f'{v}-{suffix}'
                if tag not in self.docker_tags:
                    versions.add(v)
        logging.info(versions)
        return versions

    def calculate_tags(self, version):
        tags = set()
        version_tags = {version}
        if self.latest_major(version):
            major_version = version.split('.')[0]
            version_tags.add(major_version)
        if self.latest_minor(version):
            major_minor_version = '.'.join(version.split('.')[:2])
            version_tags.add(major_minor_version)
        if self.latest_eap(version):
           version_tags.add('eap')
        if self.default_release:
            tags |= (version_tags)
            if self.latest(version):
                tags.add('latest')
        for suffix in self.tag_suffixes:
            for v in version_tags:
                suffix_tag = f'{v}-{suffix}'
                tags.add(suffix_tag)
            if self.latest(version):
                tags.add(suffix)
        return tags

    def latest(self, version):
        versions = [v for v in self.mac_versions]
        versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in versions[-1:]

    def latest_major(self, version):
        major_version = version.split('.')[0]
        major_versions = [v for v in self.mac_versions
                          if v.startswith(f'{major_version}.')]
        major_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in major_versions[-1:]

    def latest_minor(self, version):
        major_minor_version = '.'.join(version.split('.')[:2])
        minor_versions = [v for v in self.mac_versions
                          if v.startswith(f'{major_minor_version}.')]
        minor_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in minor_versions[-1:]

    def latest_eap(self, version):
        eap_versions = sorted(self.eap_versions, key=lambda s: Version(s))
        return version in eap_versions[-1:]
