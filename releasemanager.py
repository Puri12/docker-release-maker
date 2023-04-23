import concurrent.futures
import dataclasses
from enum import IntEnum
import json
import logging
import re
import time
import xml.etree.ElementTree as xmltree

import docker
import requests
import subprocess
import os

from retry import retry

RETRY_COUNT = 10
RETRY_DELAY = 1
RETRY_BACKOFF = 2


class Registry:
    DOCKER_REGISTRY = "docker-public.packages.atlassian.com"
    USERNAME = os.environ['DOCKER_BOT_USERNAME']
    PASSWORD = os.environ['DOCKER_BOT_PASSWORD']


class EnvironmentException(Exception):
    pass


class TestFailedException(Exception):
    pass


class VersionType(IntEnum):
    MILESTONE = 0
    BETA = 1
    RELEASE_CANDIDATE = 2
    RELEASE = 3


@dataclasses.dataclass(order=True, unsafe_hash=True)
class Version:
    major: [int, str] = 0
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


@dataclasses.dataclass
class TargetRepo:
    repo: str
    existing_tags: set[str]


# If this function encounters an Exception then retry for a max
# of ten attempts. Use a binary exponential backoff factor of 2
# to give the upstream dependency time to resolve its issues.
#
# 1,2,4,8,16,32,64,128,256 seconds is waited respectively before
# each retry
@retry(Exception, tries=RETRY_COUNT, delay=RETRY_DELAY, backoff=RETRY_BACKOFF)
def existing_tags(repo):
    logging.info(f'Retrieving Docker tags for {repo}')
    r = requests.get(f'https://{Registry.USERNAME}:{Registry.PASSWORD}@{Registry.DOCKER_REGISTRY}/v2/{repo}/tags/list')
    if r.status_code == requests.codes.not_found:
        return set()
    tag_data = r.json()
    tags = {t for t in tag_data["tags"]}
    return tags


def get_targets(repos):
    logging.info(f'Retrieving Docker tags for {repos}')
    targets = map(lambda repo: TargetRepo(repo, existing_tags(repo)), repos)
    return list(targets)


def release_filter(version):
    return all(d.isdigit() for d in version.split('.'))


@retry(Exception, tries=RETRY_COUNT, delay=RETRY_DELAY, backoff=RETRY_BACKOFF)
def fetch_mac_versions(product_key):
    mac_url = 'https://marketplace.atlassian.com'
    request_url = f'/rest/2/products/key/{product_key}/versions'
    params = {'offset': 0, 'limit': 50}
    versions = set()
    page = 1
    while True:
        logging.info(f'Retrieving Marketplace product versions for {product_key}: page {page}')
        r = requests.get(mac_url + request_url, params=params)
        version_data = r.json()
        for version in version_data['_embedded']['versions']:
            if release_filter(version['name']):
                logging.debug(f"Adding version {version['name']}")
                versions.add(version['name'])
        if 'next' not in version_data['_links']:
            break
        request_url = version_data['_links']['next']['href']
        page += 1
        params = {}
    logging.info(f'Found {len(versions)} versions')
    logging.debug(f'List of all versions from marketplace: {sorted(list(versions), reverse=True)}')
    return sorted(list(versions), reverse=True)


pac_url_map = {
    'bitbucket-mesh': 'bitbucket/mesh/mesh-distribution',
}


@retry(Exception, tries=RETRY_COUNT, delay=RETRY_DELAY, backoff=RETRY_BACKOFF)
def fetch_all_pac_versions(product_key):
    meta_url = f'https://packages.atlassian.com/maven-external/com/atlassian/{pac_url_map[product_key]}/maven-metadata.xml'
    r = requests.get(meta_url)
    xml = xmltree.fromstring(r.text)

    versions = list(map(lambda ve: ve.text, xml.findall('.//version')))

    return versions


def fetch_pac_release_versions(product_key):
    all_vers = fetch_all_pac_versions(product_key)
    versions = filter(release_filter, all_vers)
    return list(versions)


# Mesh is the only one not on Marketplace, so we use the Maven
# metadata on PAC to extract versions.
pac_release_api_map = {
    'bitbucket-mesh': fetch_pac_release_versions
}


def fetch_release_versions(product_key):
    lookup = pac_release_api_map.get(product_key, fetch_mac_versions)
    return lookup(product_key)


# PAC has everything, including random snapshot builds. Limit this to RC and milestone builds.
pac_eap_version_pattern = re.compile(r'\d+\.\d+\.\d+-(RC|M)\d+', re.IGNORECASE)


def pac_eap_filter(version):
    vmatch = pac_eap_version_pattern.match(version)
    return vmatch != None


def fetch_pac_eap_versions(product_key):
    all_vers = fetch_all_pac_versions(product_key)
    versions = filter(pac_eap_filter, all_vers)
    return list(versions)


mac_eap_version_pattern = re.compile(r'(\d+(?:\.\d+)+(?:-[a-zA-Z0-9]+)*)')
jira_product_key_mapper = {
    'jira': 'jira core',
    'jira-software': 'jira software',
    'jira-servicedesk': 'jira servicedesk',
}


@retry(Exception, tries=RETRY_COUNT, delay=RETRY_DELAY, backoff=RETRY_BACKOFF)
def fetch_mac_eap_versions(product_key):
    feed_key = product_key
    description_key = None
    if 'jira' in product_key:
        feed_key = 'jira'
        description_key = jira_product_key_mapper[product_key]
    elif product_key == 'bitbucket':
        feed_key = 'stash'
    logging.info(f'Retrieving EAP versions for {product_key}')
    r = requests.get(f'https://my.atlassian.com/download/feeds/eap/{feed_key}.json')
    data = json.loads(r.text[10:-1])
    versions = set()
    for item in data:
        if description_key is not None and description_key not in item['description'].lower():
            continue
        version = mac_eap_version_pattern.search(item['description']).group(1)
        versions.add(version)
    logging.info(f'Found {len(versions)} EAPs')
    return sorted(list(versions), reverse=True)


def fetch_eap_versions(product_key):
    if product_key == 'bitbucket-mesh':
        return fetch_pac_eap_versions(product_key)
    else:
        return fetch_mac_eap_versions(product_key)


def latest(version, avail_versions):
    versions = [v for v in avail_versions]
    versions.sort(key=lambda s: [int(u) for u in s.split('.')])
    return version in versions[-1:]


def latest_major(version, avail_versions):
    major_version = version.split('.')[0]
    major_versions = [v for v in avail_versions
                      if v.startswith(f'{major_version}.')]
    major_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
    return version in major_versions[-1:]


def latest_minor(version, avail_versions):
    major_minor_version = '.'.join(version.split('.')[:2])
    minor_versions = [v for v in avail_versions
                      if v.startswith(f'{major_minor_version}.')]
    minor_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
    return version in minor_versions[-1:]


def latest_eap(version, eap_versions):
    eap_versions = sorted(eap_versions, key=lambda s: Version(s))
    return version in eap_versions[-1:]


def str2bool(v):
    if str(v).lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    return False


def parse_buildargs(buildargs):
    return dict(item.split("=") for item in buildargs.split(","))


# This method will split a list of product versions across a batch count.
# For the given batch the corresponding list of product versions is
# returned.
def batch_job(product_versions, batch_count, batch):
    if len(product_versions) == 0:
        return product_versions
    batch_count = min(batch_count, len(product_versions))
    versions_per_batch = int(len(product_versions) / batch_count)
    leftover = len(product_versions) % batch_count
    extra_version = 1 if batch < leftover else 0
    start = batch * versions_per_batch + min(batch, leftover)
    end = start + versions_per_batch + extra_version
    return product_versions[start:end]


def run_script(script, *args):
    if not os.path.exists(script):
        msg = f"Script '{script}' does not exist; failing!"
        logging.error(msg)
        raise EnvironmentException(msg)

    # run provided test script - terminate with error if the test failed
    script_command = [script] + list(args)
    logging.info(f'Running script: "{script_command}"')
    proc = subprocess.run(script_command)
    if proc.returncode != 0:
        msg = f"Script '{script}' exited with non-zero ({proc.returncode}); failing!"
        logging.error(msg)
        raise TestFailedException(msg)


class ReleaseManager:

    def __init__(self, start_version, end_version, concurrent_builds, default_release,  default_eap,
                 docker_repos, dockerfile, dockerfile_buildargs, dockerfile_version_arg,
                 product_key, tag_suffixes, push_docker, post_build_hook, post_push_hook,
                 job_offset=None, jobs_total=None):
        self.start_version = Version(start_version)
        if end_version is not None:
            self.end_version = Version(end_version)
        else:
            self.end_version = Version(self.start_version.major + 1)
        self.concurrent_builds = int(concurrent_builds or 1)
        self.default_release = default_release
        self.default_eap = default_eap
        self.docker_cli = docker.from_env()

        self.tag_suffixes = set(tag_suffixes or set())
        self.target_repos = get_targets(docker_repos)

        self.dockerfile = dockerfile
        self.dockerfile_buildargs = dockerfile_buildargs
        self.dockerfile_version_arg = dockerfile_version_arg
        self.push_docker = push_docker
        self.post_push_hook = post_push_hook
        self.post_build_hook = post_build_hook
        self.job_offset = job_offset
        self.jobs_total = jobs_total

        self.avail_versions = fetch_release_versions(product_key)
        self.release_versions = [v for v in self.avail_versions
                                 if self.start_version <= Version(v) < self.end_version]
        self.eap_release_versions = [v for v in fetch_eap_versions(product_key)
                                     if self.start_version.major <= Version(v).major]

        self.max_retries = 5

        # If we're running batched just take 'our share'.
        if job_offset is not None and jobs_total is not None:
            self.release_versions = batch_job(self.release_versions, jobs_total, job_offset)
            self.eap_release_versions = batch_job(self.eap_release_versions, jobs_total, job_offset)

        logging.info(f'Will process release versions: {self.release_versions}')
        logging.info(f'Will process EAP versions: {self.eap_release_versions}')

    def create_releases(self):
        logging.info('##### Creating new releases #####')
        logging.info(f"Versions: {self.release_versions}")
        versions_to_build = self.unbuilt_versions(self.release_versions)
        return self.build_releases(versions_to_build)

    def update_releases(self):
        logging.info('##### Updating existing releases #####')
        versions_to_build = self.release_versions
        return self.build_releases(versions_to_build)

    def create_eap_releases(self):
        logging.info('##### Creating new EAP releases #####')
        logging.info(f"Versions: {self.eap_release_versions}")
        versions_to_build = self.unbuilt_versions(self.eap_release_versions)
        return self.build_releases(versions_to_build, is_prerelease=True)

    def build_releases(self, versions_to_build, is_prerelease=False):
        logging.info(
            f'Found {len(versions_to_build)} '
            f'release{"" if len(versions_to_build) == 1 else "s"} to build'
        )
        logging.info(f'Building with {self.concurrent_builds} threads')
        if self.dockerfile is not None:
            logging.info(f'Using docker file "{self.dockerfile}"')
        if self.concurrent_builds > 1:
            self._build_concurrent(versions_to_build, is_prerelease)
        else:
            for version in versions_to_build:
                self._build_release(version, is_prerelease)

    def _build_concurrent(self, versions_to_build, is_prerelease=False):
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.concurrent_builds
        )
        builds = []
        for version in versions_to_build:
            build = executor.submit(self._build_release, version, is_prerelease)
            builds.append(build)
        for build in concurrent.futures.as_completed(builds):
            exc = build.exception()
            if exc is not None:
                logging.error("Test job threw an exception; cancelling outstanding jobs...")
                executor.shutdown(wait=True, cancel_futures=True)
                raise exc

    def _push_release(self, release, retry=0, is_prerelease=False):
        if not self.push_docker:
            logging.info(f'Skipping push of tag "{release}"')
            return

        try:
            logging.info(f'Pushing tag "{release}"')
            self.docker_cli.images.push(release)
        except requests.exceptions.ConnectionError as e:
            if retry > self.max_retries:
                logging.error(f'Push failed for tag "{release}"')
                raise e
            logging.warning(f'Pushing tag "{release}" failed; retrying in {retry + 1}s ...')
            time.sleep(retry + 1)
            # retry push in case of error
            self._push_release(release, retry + 1, is_prerelease)
        else:
            logging.info(f'Pushing tag "{release}" succeeded!')
            self._run_post_push_hook(release, is_prerelease)
            return

    def _build_image(self, version, retry=0):
        buildargs = {self.dockerfile_version_arg: version}
        if self.dockerfile_buildargs is not None:
            buildargs.update(parse_buildargs(self.dockerfile_buildargs))
        buildargs_log_str = ', '.join(['{}={}'.format(*i) for i in buildargs.items()])
        logging.info(f'Building {version} image with buildargs: {buildargs_log_str}')
        try:
            image = self.docker_cli.images.build(path='.',
                                                 buildargs=buildargs,
                                                 dockerfile=self.dockerfile,
                                                 rm=True)[0]
            return image

        except docker.errors.BuildError as exc:
            if retry >= self.max_retries:
                logging.error(
                    f'Build with args '
                    f'{self.dockerfile_version_arg}={version} failed:\n\t{exc}'
                )
                for line in exc.build_log:
                    logging.error(f"Build Log: {line['stream'].strip()}")
                raise exc
        logging.warning(f'Build with args {buildargs_log_str} failed; retrying in 30 seconds...')
        time.sleep(30)  # wait 30s before retrying build after failure
        return self._build_image(version, retry=retry + 1)

    def _build_release(self, version, is_prerelease=False):
        logging.info(f"#### Building release {version}")

        image = self._build_image(version)

        # script will terminated with error if the test failed
        logging.info(f"#### Preparing the release {version}")
        self._run_post_build_hook(image, version)

        tags = self.calculate_tags(version)
        logging.info('##### Pushing the image tags')
        logging.info(f"TAGS FOR {version} ARE {tags}")
        for tag in tags:
            for target in self.target_repos:
                repo = f'docker-public.packages.atlassian.com/{target.repo}'
                release = f'{repo}:{tag}'

                logging.info(f'Tagging "{release}"')
                image.tag(repo, tag=tag)

                self._push_release(release, is_prerelease)

    def _run_post_build_hook(self, image, version):
        if self.post_build_hook is None or self.post_build_hook == '':
            logging.warning("Post-build hook is not set; skipping! ")
            return

        # Usage: post_build.sh <image-tag-or-hash> ['true' if release image]  ['true' if test candidate]
        is_release = str(self.push_docker).lower()
        test_candidate = str(latest_minor(version, self.avail_versions)).lower()

        run_script(self.post_build_hook, image.id, is_release, test_candidate)

    def _run_post_push_hook(self, release, is_prerelease=False):
        if self.post_push_hook is None or self.post_push_hook == '':
            logging.warning("Post-push hook is not set; skipping! ")
            return

        logging.info(f'Running hook: {self.post_push_hook}')
        run_script(self.post_push_hook, release, str(is_prerelease).lower())

    def unbuilt_versions(self, candidate_versions):
        # Only exclude tags that exist in all repos
        existing_tags = set.intersection(*map(lambda tr: tr.existing_tags, self.target_repos))
        if self.default_release:
            return list(set(candidate_versions) - existing_tags)

        versions = set()
        for v in candidate_versions:
            for suffix in self.tag_suffixes:
                tag = f'{v}-{suffix}'
                if tag not in existing_tags:
                    versions.add(v)
        logging.info(f"Found unbuilt: {versions}")
        return versions

    def calculate_tags(self, version):
        tags = set()
        version_tags = {version}
        if latest_major(version, self.avail_versions):
            major_version = version.split('.')[0]
            version_tags.add(major_version)
        if latest_minor(version, self.avail_versions):
            major_minor_version = '.'.join(version.split('.')[:2])
            version_tags.add(major_minor_version)
        if self.default_eap and latest_eap(version, self.eap_release_versions):
           version_tags.add('eap')
        if self.default_release:
            tags |= (version_tags)
            if latest(version, self.avail_versions):
                tags.add('latest')
        for suffix in self.tag_suffixes:
            for v in version_tags:
                suffix_tag = f'{v}-{suffix}'
                tags.add(suffix_tag)
            if latest(version, self.avail_versions):
                tags.add(suffix)
        return tags
