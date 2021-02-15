import argparse
import logging
import os
import sys
import subprocess

from releasemanager import ReleaseManager, str2bool



logging.basicConfig(level=logging.INFO)

BASE_VERSION = os.environ.get('BASE_VERSION') # Deprecated
START_VERSION = os.environ.get('START_VERSION') or BASE_VERSION
END_VERSION = os.environ.get('END_VERSION')

CONCURRENT_BUILDS = os.environ.get('CONCURRENT_BUILDS')
DEFAULT_RELEASE = str2bool(os.environ.get('DEFAULT_RELEASE'))
DOCKER_REPO = os.environ.get('DOCKER_REPO')
DOCKERFILE = os.environ.get('DOCKERFILE')
DOCKERFILE_BUILDARGS = os.environ.get('DOCKERFILE_BUILDARGS')
DOCKERFILE_VERSION_ARG = os.environ.get('DOCKERFILE_VERSION_ARG')
MAC_PRODUCT_KEY = os.environ.get('MAC_PRODUCT_KEY')

suffixes = os.environ.get('TAG_SUFFIXES')
if suffixes is not None:
    suffixes = suffixes.split(',')
TAG_SUFFIXES = suffixes

parser = argparse.ArgumentParser(description='Manage docker releases')
parser.add_argument('--create', dest='create', action='store_true')
parser.add_argument('--update', dest='update', action='store_true')
parser.add_argument('--create-eap', dest='create_eap', action='store_true')
parser.add_argument('--no-push', dest='no_push', action='store_true')
parser.add_argument('--test-script', dest='test_script', default='integration_test.sh', help='The full path to the test script that need to run before docker push.')

def main(args):
    if None in [START_VERSION, DOCKER_REPO, DOCKERFILE_VERSION_ARG, MAC_PRODUCT_KEY]:
        logging.error('START_VERSION, DOCKER_REPO, DOCKERFILE_VERSION_ARG, and MAC_PRODUCT_KEY must be defined!')
        sys.exit(1)

    manager = ReleaseManager(start_version=START_VERSION,
                             end_version=END_VERSION,
                             concurrent_builds=CONCURRENT_BUILDS,
                             default_release=DEFAULT_RELEASE,
                             docker_repo=DOCKER_REPO,
                             dockerfile=DOCKERFILE,
                             dockerfile_buildargs=DOCKERFILE_BUILDARGS,
                             dockerfile_version_arg=DOCKERFILE_VERSION_ARG,
                             mac_product_key=MAC_PRODUCT_KEY,
                             tag_suffixes=TAG_SUFFIXES,
                             no_push=args.no_push,
                             test_script=integration_test)
    if args.create:
        manager.create_releases()
    if args.update:
        manager.update_releases()
    if args.create_eap:
        manager.create_eap_releases()

if __name__ == '__main__':
    args = parser.parse_args()
    main(args)