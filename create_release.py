import logging
import os
import re

from git import Repo

from versiontools import mac_versions, docker_tags, latest_mac_version, minor_is_latest


BASE_BRANCH = os.environ.get('BASE_BRANCH')
BASE_VERSION = os.environ.get('BASE_VERSION')

DOCKER_REPO = os.environ.get('DOCKER_REPO')
DOCKERFILE_VERSION_STRING = os.environ.get('DOCKERFILE_VERSION_STRING')

GIT_EMAIL = os.environ.get('GIT_EMAIL')
GIT_USER = os.environ.get('GIT_USER')

MAC_PRODUCT_KEY = os.environ.get('MAC_PRODUCT_KEY')


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    repo = Repo.init()
    origin = repo.remote()
    with repo.config_writer() as config:
        logging.info(f'Setting user to {GIT_USER} <{GIT_EMAIL}>')
        config.set_value('user', 'email', GIT_EMAIL)
        config.set_value('user', 'name', GIT_USER)

    mac_versions = {v for v in mac_versions(MAC_PRODUCT_KEY) if v[:1] == BASE_VERSION}
    latest_mac_version = latest_mac_version(MAC_PRODUCT_KEY)
    docker_versions = docker_tags(DOCKER_REPO)

    unbuilt_versions = mac_versions - docker_versions

    for version in unbuilt_versions:
        logging.info(f'Preparing new release for {version}')
        major_minor_version = '.'.join(version.split('.')[:2])
        release_name = f'release/{version}'
        if release_name in repo.heads:
            logging.warn(f'{release_name} already exists')
            continue
        head = repo.create_head(release_name, BASE_BRANCH)
        with open('Dockerfile', 'r+') as d:
            new_dockerfile = re.sub(f'({DOCKERFILE_VERSION_STRING}[=\\s])([\\d\\.]*)', f'\\g<1>{version}', d.read())
            d.seek(0)
            d.write(new_dockerfile)
            d.truncate()

        repo.index.add(['Dockerfile'])
        repo.index.commit(f'Rev image to {version}')
        repo.create_tag(version)
        if minor_is_latest(version, mac_versions):
            repo.create_tag(major_minor_version)
        if version == latest_mac_version:
            repo.create_tag('latest')
            repo.create_tag(BASE_VERSION)
    origin.push(all=True)
    origin.push(tags=True)


