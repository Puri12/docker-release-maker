import pytest


@pytest.fixture
def refapp():
    app = {
        'start_version': '6',
        'end_version': None,
        'concurrent_builds': '4',
        'default_release': True,
        'docker_repos': ['atlassian/bitbucket-server'],
        'dockerfile': None,
        'dockerfile_buildargs': None,
        'dockerfile_version_arg': 'BITBUCKET_VERSION',
        'mac_product_key': 'bitbucket',
        'tag_suffixes': 'jdk11,ubuntu'.split(','),
        'push_docker': True,
        'post_build_hook': None,
        'post_push_hook': None,
        'job_offset': None,
        'jobs_total': None,
    }
    return app
