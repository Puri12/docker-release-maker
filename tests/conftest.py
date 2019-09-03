import pytest


@pytest.fixture
def refapp():
    app = {
        'min_version': '6',
        'max_version': None,
        'concurrent_builds': '4',
        'default_release': True,
        'docker_repo': 'atlassian/bitbucket-server',
        'dockerfile': None,
        'dockerfile_buildargs': None,
        'dockerfile_version_arg': 'BITBUCKET_VERSION',
        'mac_product_key': 'bitbucket',
        'tag_suffixes': 'jdk8,ubuntu'.split(','),
    }
    return app
