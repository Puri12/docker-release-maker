import argparse
import logging
import os
import sys

from releasemanager import ReleaseManager, str2bool



logging.basicConfig(level=logging.INFO)

BASE_VERSION = os.environ.get('BASE_VERSION')
DEFAULT_RELEASE = str2bool(os.environ.get('DEFAULT_RELEASE'))
DOCKER_REPO = os.environ.get('DOCKER_REPO')
DOCKERFILE_VERSION_ARG = os.environ.get('DOCKERFILE_VERSION_ARG')
MAC_PRODUCT_KEY = os.environ.get('MAC_PRODUCT_KEY')
suffixes = os.environ.get('TAG_SUFFIXES')
if suffixes is not None:
    suffixes = suffixes.split(',')
TAG_SUFFIXES = suffixes

parser = argparse.ArgumentParser(description='Manage docker releases')
parser.add_argument('--create', dest='create', action='store_true')
parser.add_argument('--update', dest='update', action='store_true')



if __name__ == '__main__':
    if None in [BASE_VERSION, DOCKER_REPO, DOCKERFILE_VERSION_ARG, MAC_PRODUCT_KEY]:
        logging.error('BASE_VERSION, DOCKER_REPO, DOCKERFILE_VERSION_ARG, and MAC_PRODUCT_KEY must be defined!')
        sys.exit(1)
    manager = ReleaseManager(base_version=BASE_VERSION,
                             default_release=DEFAULT_RELEASE,
                             docker_repo=DOCKER_REPO,
                             dockerfile_version_arg=DOCKERFILE_VERSION_ARG,
                             mac_product_key=MAC_PRODUCT_KEY,
                             tag_suffixes=TAG_SUFFIXES)
    args = parser.parse_args()
    if args.create:
        manager.create_releases()
    if args.update:
        manager.update_releases()
