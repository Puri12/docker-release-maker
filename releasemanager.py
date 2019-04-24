import logging
import re

from git import Repo
import requests



def extract_version(release):
    pattern = re.compile(r'(\d+\.\d+\.\d+(\.\d+)?)')
    match = pattern.search(release)
    if match is not None:
        return match.group(1)


def mac_versions(product_key, offset=0, limit=50):
    mac_url = 'https://marketplace.atlassian.com'
    request_url = f'/rest/2/products/key/{product_key}/versions'
    params = {'offset': offset, 'limit': limit}
    while True:
        r = requests.get(mac_url + request_url, params=params)
        version_data = r.json()
        for version in version_data['_embedded']['versions']:
            yield version['name']
        if 'next' not in version_data['_links']:
            return
        request_url = version_data['_links']['next']['href']
        params = {}


def str2bool(v):
    if str(v).lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    return False



class ReleaseManager:

    def __init__(self, base_branch, mac_product_key, dockerfile_version_string, default_release, tag_suffixes=None):
        self.repo = Repo()
        self.origin = self.repo.remote()
        self.base_branch = base_branch
        self.base_version = self.base_branch.split('-')[1]
        try:
            self.base_suffix = self.base_branch.split('-')[2]
        except IndexError:
            self.base_suffix = None

        logging.info('Retrieving released versions from marketplace')
        self.product_versions = {
            v for v in mac_versions(mac_product_key)
            if v[:1] == self.base_version and all(d.isdigit() for d in v.split('.'))
        }
        self.dockerfile_version_string = dockerfile_version_string
        self.default_release = default_release

        if tag_suffixes is None:
            tag_suffixes = set()
        self.tag_suffixes = set(tag_suffixes)
        if self.base_suffix is not None:
            self.tag_suffixes.add(self.base_suffix)

    def create_releases(self):
        for release in self.unbuilt_releases():
            logging.info(f'Preparing {release}')
            version = extract_version(release)
            head = self.repo.create_head(release, self.base_branch)
            head.checkout()
            self.update_dockerfile(version)
            for tag in self.calculate_tags(version):
                logging.info(f'Tagging {release} as {tag}')
                self.repo.create_tag(tag, force=True)
            logging.info(f'Pushing branch {release}')
            self.origin.push(release)
            logging.info(f'Pushing tags for {release}')
            self.origin.push(tags=True, force=True)

    def update_releases(self):
        for release in self.existing_releases():
            logging.info(f'Updating {release} with new changes from {self.base_branch}')
            version = extract_version(release)
            self.repo.git.checkout(release)
            self.repo.git.merge(self.base_branch)
            for tag in self.calculate_tags(version):
                logging.info(f'Tagging {release} as {tag}')
                self.repo.create_tag(tag, force=True)
            logging.info(f'Pushing branch {release}')
            self.origin.push(release)
            logging.info(f'Pushing tags for {release}')
            self.origin.push(tags=True, force=True)

    def existing_releases(self):
        version_re = '\.\d+\.\d+(\.\d+)?'
        releases = set()
        if self.base_suffix is None:
            pattern = re.compile(fr'release/{self.base_version}{version_re}$')
        else:
            pattern = re.compile(fr'release/{self.base_version}{version_re}-{self.base_suffix}$')
        remote_heads = {r.remote_head for r in self.origin.refs}
        for head in remote_heads:
            if pattern.match(head):
                releases.add(head)
        return releases

    def unbuilt_releases(self):
        potential_releases = {self.release_branch_name(v) for v in self.product_versions}
        unbuilt = potential_releases - self.existing_releases()
        return unbuilt

    def release_branch_name(self, version):
        if self.base_suffix is None:
            return f'release/{version}'
        return f'release/{version}-{self.base_suffix}'

    def calculate_tags(self, version):
        tags = set()
        version_tags = {version}
        if self.latest_major(version):
            major_version = version.split('.')[0]
            version_tags.add(major_version)
        if self.latest_minor(version):
            major_minor_version = '.'.join(version.split('.')[:2])
            version_tags.add(major_minor_version)
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

    def update_dockerfile(self, version):
        logging.info(f'Updating {self.dockerfile_version_string} to {version} in Dockerfile')
        with open('Dockerfile', 'r+') as d:
            new_dockerfile = re.sub(f'({self.dockerfile_version_string}[=\\s])([\\d\\.]*)', f'\\g<1>{version}', d.read())
            d.seek(0)
            d.write(new_dockerfile)
            d.truncate()
        self.repo.index.add(['Dockerfile'])
        self.repo.index.commit(f'Rev image to {version}')

    def latest(self, version):
        versions = [v for v in self.product_versions]
        versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in versions[-1:]

    def latest_major(self, version):
        major_version = version.split('.')[0]
        major_versions = [v for v in self.product_versions if v.startswith(f'{major_version}.')]
        major_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in major_versions[-1:]

    def latest_minor(self, version):
        major_minor_version = '.'.join(version.split('.')[:2])
        minor_versions = [v for v in self.product_versions if v.startswith(f'{major_minor_version}.')]
        minor_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in minor_versions[-1:]

