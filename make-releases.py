import argparse
import logging
import os
import math
import sys
import subprocess

from releasemanager import ReleaseManager, str2bool


def parse_args():
    parser = argparse.ArgumentParser(description='Manage docker releases')
    parser.add_argument('--create', dest='create', action='store_true')
    parser.add_argument('--update', dest='update', action='store_true')
    parser.add_argument('--create-eap', dest='create_eap', action='store_true')

    parser.add_argument('--start-version', dest='start_version', required=True)
    parser.add_argument('--end-version', dest='end_version', default=math.inf)
    parser.add_argument('--docker-repos', dest='docker_repos', required=True,
                        help='A comma-separated list of repositories to push to.')

    parser.add_argument('--dockerfile-version-arg', dest='dockerfile_version_arg', required=True)
    parser.add_argument('--product-key', '--mac-product-key', dest='product_key', required=True)

    parser.add_argument('--concurrent-builds', dest='concurrent_builds', type=int, default=1)
    parser.add_argument('--default-release', dest='default_release', action='store_true')
    parser.add_argument('--default-eap', dest='default_eap', action='store_true')
    parser.add_argument('--dockerfile', dest='dockerfile', default='Dockerfile')
    parser.add_argument('--dockerfile-buildargs', dest='dockerfile_buildargs')
    parser.add_argument('--post-build-hook', dest='post_build_hook', default='/usr/src/app/post_build.sh')

    parser.add_argument('--push', dest='push_docker', action='store_true')
    parser.add_argument('--post-push-hook', dest='post_push_hook', default='/usr/src/app/post_push.sh')

    parser.add_argument('--job-offset', dest='job_offset', type=int, default=None)
    parser.add_argument('--jobs-total', dest='jobs_total', type=int, default=None)

    parser.add_argument('--tag-suffixes', dest='tag_suffixes')

    args = parser.parse_args()
    if args.tag_suffixes is not None:
        args.tag_suffixes = args.tag_suffixes.split(',')

    return args


def main(args):
    logging.basicConfig(level=logging.INFO)

    manager = ReleaseManager(start_version=args.start_version,
                             end_version=args.end_version,
                             concurrent_builds=args.concurrent_builds,
                             default_release=args.default_release,
                             default_eap=args.default_eap,
                             docker_repos=args.docker_repos.split(','),
                             dockerfile=args.dockerfile,
                             dockerfile_buildargs=args.dockerfile_buildargs,
                             dockerfile_version_arg=args.dockerfile_version_arg,
                             product_key=args.product_key,
                             tag_suffixes=args.tag_suffixes,
                             push_docker=args.push_docker,
                             post_build_hook=args.post_build_hook,
                             post_push_hook=args.post_push_hook,
                             job_offset=args.job_offset,
                             jobs_total=args.jobs_total)
    if args.create:
        manager.create_releases()
    if args.update:
        manager.update_releases()
    if args.create_eap:
        manager.create_eap_releases()

if __name__ == '__main__':
    args = parse_args()
    main(args)
