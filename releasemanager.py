import logging
import re

import docker
import requests



def docker_tags(repo):
    logging.info(f'Retrieving Docker tags for {repo}')
    r = requests.get(f'https://index.docker.io/v1/repositories/{repo}/tags')
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


def str2bool(v):
    if str(v).lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    return False



class ReleaseManager:

    def __init__(self, base_version, default_release, docker_repo, dockerfile_version_arg, mac_product_key, tag_suffixes):
        self.base_version = base_version
        self.default_release = default_release
        self.docker_cli = docker.from_env()
        self.docker_repo = docker_repo
        self.docker_tags = docker_tags(docker_repo)
        self.dockerfile_version_arg = dockerfile_version_arg
        self.mac_versions = mac_versions(mac_product_key)
        self.release_versions = {v for v in self.mac_versions
                                 if v.startswith(f'{base_version}.')}
        self.tag_suffixes = set(tag_suffixes or set())

    def create_releases(self):
        versions_to_build = self.unbuilt_release_versions()
        return self.build_releases(versions_to_build)

    def update_releases(self):
        versions_to_build = self.release_versions
        return self.build_releases(versions_to_build)

    def build_releases(self, versions_to_build):
        logging.info(f'Found {len(versions_to_build)} release{"" if len(versions_to_build)==1 else "s"} to build')
        for version in versions_to_build:
            logging.info(f'Building {self.docker_repo} with {self.dockerfile_version_arg}={version}')
            buildargs = {self.dockerfile_version_arg: version}
            image = self.docker_cli.images.build(path='.', buildargs=buildargs, rm=True)[0]
            for tag in self.calculate_tags(version):
                release = f'{self.docker_repo}:{tag}'
                image.tag(self.docker_repo, tag=tag)
                logging.info(f'Pushing tag "{release}"')
                self.docker_cli.images.push(release)

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

    def latest(self, version):
        versions = [v for v in self.mac_versions]
        versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in versions[-1:]

    def latest_major(self, version):
        major_version = version.split('.')[0]
        major_versions = [v for v in self.mac_versions if v.startswith(f'{major_version}.')]
        major_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in major_versions[-1:]

    def latest_minor(self, version):
        major_minor_version = '.'.join(version.split('.')[:2])
        minor_versions = [v for v in self.mac_versions if v.startswith(f'{major_minor_version}.')]
        minor_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
        return version in minor_versions[-1:]

