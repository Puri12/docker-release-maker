import logging
import os

from git import Repo

from versiontools import mac_versions, docker_tags, latest_mac_version, minor_is_latest


BASE_BRANCH = os.environ.get('BASE_BRANCH')
BASE_VERSION = os.environ.get('BASE_VERSION')

DOCKER_REPO = os.environ.get('DOCKER_REPO')
DOCKERFILE_VERSION_STRING = os.environ.get('DOCKERFILE_VERSION_STRING')

GIT_USER = os.environ.get('GIT_USER')
GIT_EMAIL = os.environ.get('GIT_EMAIL')

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

    for head in repo.heads:
        if not head.name.startswith(f'release/{BASE_VERSION}'):
            continue
        logging.info(f'Updating {head.name} with new changes from {BASE_BRANCH}')
        head.checkout()
        version = head.name.replace('release/', '')
        major_minor_version = '.'.join(version.split('.')[:2])
        repo.git.merge(BASE_BRANCH)
        repo.create_tag(version, force=True)
        if minor_is_latest(version, mac_versions):
            repo.create_tag(major_minor_version, force=True)
        if version == latest_mac_version:
            repo.create_tag('latest', force=True)
            repo.create_tag(BASE_VERSION, force=True)
    origin.push(all=True)
    origin.push(tags=True)
