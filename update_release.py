import logging
import os
import re

from git import Repo

from versiontools import mac_versions, major_is_latest, minor_is_latest, version_is_latest, str2bool

BASE_BRANCH = os.environ.get('BASE_BRANCH')
BASE_VERSION = os.environ.get('BASE_VERSION')

DOCKER_REPO = os.environ.get('DOCKER_REPO')
DOCKERFILE_VERSION_STRING = os.environ.get('DOCKERFILE_VERSION_STRING')

GIT_USER = os.environ.get('GIT_USER')
GIT_EMAIL = os.environ.get('GIT_EMAIL')

MAC_PRODUCT_KEY = os.environ.get('MAC_PRODUCT_KEY')

TAG_SUFFIX = os.environ.get('TAG_SUFFIX')

if os.environ.get('SHOULD_CREATE_LATEST_TAG'):
    SHOULD_CREATE_LATEST_TAG = str2bool(os.environ.get('SHOULD_CREATE_LATEST_TAG'))
else:
    SHOULD_CREATE_LATEST_TAG = True

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    repo = Repo.init()
    origin = repo.remote()
    remote_heads = [r.remote_head for r in origin.refs]

    with repo.config_writer() as config:
        logging.info(f'Setting user to {GIT_USER} <{GIT_EMAIL}>')
        config.set_value('user', 'email', GIT_EMAIL)
        config.set_value('user', 'name', GIT_USER)

    logging.info('Retrieving released versions from marketplace')
    mac_versions = {v for v in mac_versions(MAC_PRODUCT_KEY) if v[:1] == BASE_VERSION}

    for head in remote_heads:
        if not head.startswith(f'release/{BASE_VERSION}'):
            continue
        if TAG_SUFFIX:
            if not head.endswith(TAG_SUFFIX):
                continue
        else:
            if not re.match(r'^release/\d+\.\d+\.\d+(\.\d+)?$', head):
                continue
        logging.info(f'Updating {head} with new changes from {BASE_BRANCH}')
        repo.git.checkout(head)
        version = head.replace('release/', '')
        major_minor_version = '.'.join(version.split('.')[:2])
        major_version = version.split('.')[0]
        repo.git.merge(BASE_BRANCH)
        repo.create_tag(version, force=True)

        if TAG_SUFFIX:
            version_without_suffix = re.sub(f"-{TAG_SUFFIX}", "", version)
            if major_is_latest(version_without_suffix, mac_versions):
                logging.info(f'Tagging {version} as {major_version}-{TAG_SUFFIX}')
                repo.create_tag(f'{major_version}-{TAG_SUFFIX}', force=True)
            if minor_is_latest(version_without_suffix, mac_versions):
                logging.info(f'Tagging {version} as {major_minor_version}-{TAG_SUFFIX}')
                repo.create_tag(f'{major_minor_version}-{TAG_SUFFIX}', force=True)
            if version_is_latest(version_without_suffix, mac_versions) and SHOULD_CREATE_LATEST_TAG:
                logging.info(f'Tagging {version} as latest')
                repo.create_tag('latest', force=True)
        else:
            if major_is_latest(version, mac_versions):
                logging.info(f'Tagging {version} as {major_version}')
                repo.create_tag(major_version, force=True)
            if minor_is_latest(version, mac_versions):
                logging.info(f'Tagging {version} as {major_minor_version}')
                repo.create_tag(major_minor_version, force=True)
            if version_is_latest(version, mac_versions) and SHOULD_CREATE_LATEST_TAG:
                logging.info(f'Tagging {version} as latest')
                repo.create_tag('latest', force=True)

    logging.info('Pushing branches')
    origin.push(all=True)
    logging.info('Pushing tags')
    origin.push(tags=True, force=True)
