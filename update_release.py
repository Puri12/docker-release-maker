import logging
import os

from git import Repo

from versiontools import mac_versions, docker_tags, latest_mac_version, major_is_latest, minor_is_latest


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
    remote_heads = [r.remote_head for r in origin.refs]

    with repo.config_writer() as config:
        logging.info(f'Setting user to {GIT_USER} <{GIT_EMAIL}>')
        config.set_value('user', 'email', GIT_EMAIL)
        config.set_value('user', 'name', GIT_USER)

    mac_versions = {v for v in mac_versions(MAC_PRODUCT_KEY) if v[:1] == BASE_VERSION}
    latest_mac_version = latest_mac_version(MAC_PRODUCT_KEY)

    for head in remote_heads:
        if not head.startswith(f'release/{BASE_VERSION}'):
            continue
        logging.info(f'Updating {head} with new changes from {BASE_BRANCH}')
        repo.git.checkout(head)
        version = head.replace('release/', '')
        major_minor_version = '.'.join(version.split('.')[:2])
        major_version = version.split('.')[0]
        repo.git.merge(BASE_BRANCH)
        repo.create_tag(version, force=True)
        if major_is_latest(version, mac_versions):
            logging.info(f'Tagging {version} as {major_version}')
            repo.create_tag(major_version, force=True)
        if minor_is_latest(version, mac_versions):
            logging.info(f'Tagging {version} as {major_minor_version}')
            repo.create_tag(major_minor_version, force=True)
        if version == latest_mac_version:
            logging.info(f'Tagging {version} as latest')
            repo.create_tag('latest', force=True)
    logging.info('Pushing branches')
    origin.push(all=True)
    logging.info('Pushing tags')
    origin.push(tags=True, force=True)
