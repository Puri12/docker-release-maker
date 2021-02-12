import pytest


@pytest.fixture
def refapp():
    app = {
        'start_version': '6',
        'end_version': None,
        'concurrent_builds': '4',
        'default_release': True,
        'docker_repo': 'atlassian/bitbucket-server',
        'dockerfile': None,
        'dockerfile_buildargs': None,
        'dockerfile_version_arg': 'BITBUCKET_VERSION',
        'mac_product_key': 'bitbucket',
        'tag_suffixes': 'jdk8,ubuntu'.split(','),
        'no_push': False,
        'test_script': 'ls',
    }
    return app
