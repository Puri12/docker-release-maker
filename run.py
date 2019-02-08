import argparse
import logging
import os
import sys

from releasemanager import ReleaseManager, str2bool



logging.basicConfig(level=logging.INFO)

BASE_BRANCH = os.environ.get('BASE_BRANCH')
MAC_PRODUCT_KEY = os.environ.get('MAC_PRODUCT_KEY')
DOCKERFILE_VERSION_STRING = os.environ.get('DOCKERFILE_VERSION_STRING')
DEFAULT_RELEASE = str2bool(os.environ.get('DEFAULT_RELEASE'))
suffixes = os.environ.get('ADDITIONAL_TAG_SUFFIXES')
if suffixes is not None:
    suffixes = suffixes.split(',')
ADDITIONAL_TAG_SUFFIXES = suffixes

parser = argparse.ArgumentParser(description='Manage docker releases')
parser.add_argument('--create', dest='create', action='store_true')
parser.add_argument('--update', dest='update', action='store_true')



if __name__ == '__main__':
    if None in [MAC_PRODUCT_KEY, DOCKERFILE_VERSION_STRING]:
        logging.error('MAC_PRODUCT_KEY and DOCKERFILE_VERSION_STRING must be defined!')
        sys.exit(1)
    manager = ReleaseManager(base_branch=BASE_BRANCH,
                             mac_product_key=MAC_PRODUCT_KEY,
                             dockerfile_version_string=DOCKERFILE_VERSION_STRING,
                             default_release=DEFAULT_RELEASE,
                             tag_suffixes=ADDITIONAL_TAG_SUFFIXES)
    args = parser.parse_args()
    if args.create:
        manager.create_releases()
    if args.update:
        manager.update_releases()
