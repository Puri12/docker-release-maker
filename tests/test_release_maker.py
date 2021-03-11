import logging
import os
from unittest import mock

import docker
import pytest

from releasemanager import docker_tags, eap_versions, mac_versions, ReleaseManager, str2bool, Version, latest_minor

def test_docker_tags(refapp):
    tags = docker_tags(refapp['docker_repo'])
    assert len(tags) > 0
    assert isinstance(tags, set)
    assert all([isinstance(v, str) for v in tags])


def test_mac_versions(refapp):
    versions = mac_versions(refapp['mac_product_key'])
    assert len(versions) > 0
    assert isinstance(versions, list)
    assert all([i.isdigit() for v in versions for i in v.split('.')])

def test_eap_versions(refapp):
    versions = eap_versions(refapp['mac_product_key'])
    assert isinstance(versions, list)

def test_version_sorting():
    x = Version('1.9.9')
    y = Version('1.20.0')
    z = Version('1.100')
    assert x < y < z

    x = Version('1')
    y = Version('1.99.99')
    z = Version('2')
    assert x < y < z

    x = Version('1.0.0-RC1')
    y = Version('1.0.0-RC2')
    z = Version('1')
    assert x < y < z

    x = Version('1.0.0-m1')
    y = Version('1.0.0-tinymcebeta')
    z = Version('1.0.0-RC1')
    assert x < y < z

def test_latest_minor():
    versions = ['5.4.3', '5.6.7', '5.6.9', '5.7.7', '5.7.8']
    assert not latest_minor("5.7.7", versions)
    assert latest_minor("5.7.8", versions)
    assert not latest_minor("5.6.7", versions)

@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags')
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.7.7', '6.7.8'})
def test_calculate_tags(mocked_docker, mocked_docker_tags, mocked_mac_versions, refapp):
    rm = ReleaseManager(**refapp)

    test_tag = '6.7.8'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6', '6.7', '6.7.8',
        '6-jdk8', '6.7-jdk8', '6.7.8-jdk8',
        '6-ubuntu', '6.7-ubuntu', '6.7.8-ubuntu',
        'latest', 'jdk8', 'ubuntu',
    }
    assert expected_tags == tags

    test_tag = '6.7.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.7.7',
        '6.7.7-jdk8',
        '6.7.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.6.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5', '5.6', '5.6.7',
        '5-jdk8', '5.6-jdk8', '5.6.7-jdk8',
        '5-ubuntu', '5.6-ubuntu', '5.6.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.4.3'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5.4', '5.4.3',
        '5.4-jdk8', '5.4.3-jdk8',
        '5.4-ubuntu', '5.4.3-ubuntu',
    }
    assert expected_tags == tags

    refapp['default_release'] = False
    rm = ReleaseManager(**refapp)

    test_tag = '6.7.8'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6-jdk8', '6.7-jdk8', '6.7.8-jdk8',
        '6-ubuntu', '6.7-ubuntu', '6.7.8-ubuntu',
        'jdk8', 'ubuntu'
    }
    assert expected_tags == tags

    test_tag = '6.7.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.7.7-jdk8',
        '6.7.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.6.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5-jdk8', '5.6-jdk8', '5.6.7-jdk8',
        '5-ubuntu', '5.6-ubuntu', '5.6.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.4.3'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5.4-jdk8', '5.4.3-jdk8',
        '5.4-ubuntu', '5.4.3-ubuntu',
    }
    assert expected_tags == tags


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_create_releases(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.5.4"',
        f'{refapp["docker_repo"]}:6.7.8'
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:5.4.3"',
        f'"{refapp["docker_repo"]}:5.6.7"',
        f'"{refapp["docker_repo"]}:6.7.7"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_update_releases(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.update_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.5.4"',
        f'"{refapp["docker_repo"]}:6.7.7"',
        f'"{refapp["docker_repo"]}:6.7.8"',
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:5.4.3"',
        f'"{refapp["docker_repo"]}:5.6.7"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.5.5', '6.7.7', '6.5.4-jdk11', '6.5.5-ubuntu'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.5.5', '6.7.7', '6.7.8'})
def test_create_competing_releases(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.5.4"',
        f'"{refapp["docker_repo"]}:6.7.8"',
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:6.5.5"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text

    refapp['default_release'] = False
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.7.7-jdk8"',
        f'"{refapp["docker_repo"]}:6.7.8-jdk8"',
        f'"{refapp["docker_repo"]}:6.5.4-ubuntu"',
        f'"{refapp["docker_repo"]}:6.5.4-jdk8"',
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:5.4.3"',
        f'"{refapp["docker_repo"]}:5.6.7"',
        f'"{refapp["docker_repo"]}:6.7.7"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value=set())
@mock.patch('releasemanager.mac_versions', return_value={'6.5.5', '6.7.7', '6.7.8'})
def test_raise_exceptions(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.docker_cli.images.build.side_effect = docker.errors.BuildError('Test failure message', [{'stream':'Build log'}])
    with pytest.raises(docker.errors.BuildError):
        rm.create_releases()
    expected_logs = {
        '6.5.5 failed',
        '6.7.8 failed',
        '6.7.7 failed',
        'Test failure message',
    }
    for logmsg in expected_logs:
        assert logmsg in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_custom_buildargs(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['dockerfile_buildargs'] = 'ARTEFACT=jira-software,BASE_IMAGE=adoptopenjdk/openjdk11:slim'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    assert 'ARTEFACT=jira-software' in caplog.text
    assert 'BASE_IMAGE=adoptopenjdk/openjdk11:slim' in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_create_releases_with_specified_dockerfile(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    custom_dockerfile = 'Dockerfile-test-123'
    refapp['dockerfile'] = 'Dockerfile-test-123'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    assert custom_dockerfile in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.4.4', '6.5.4', '6.7.7', '6.7.8'})
def test_start_version(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['start_version'] = '6.5'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repo"]}:6.5.4',
        f'{refapp["docker_repo"]}:6.7.8',
    }
    unexpected_tags = {
        f'{refapp["docker_repo"]}:5.4.3',
        f'{refapp["docker_repo"]}:5.6.7',
        f'{refapp["docker_repo"]}:6.4.4',
        f'{refapp["docker_repo"]}:6.7.7',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.4.4', '6.5.4', '6.7.7', '6.7.8'})
def test_end_version(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['end_version'] = '6.7'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repo"]}:6.4.4',
        f'{refapp["docker_repo"]}:6.5.4',
    }
    unexpected_tags = {
        f'{refapp["docker_repo"]}:5.4.3',
        f'{refapp["docker_repo"]}:5.6.7',
        f'{refapp["docker_repo"]}:6.7.7',
        f'{refapp["docker_repo"]}:6.7.8',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.6', '5.6.7', '6.4.4', '6.5.4', '6.7.7', '6.7.8'})
def test_min_end_version(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['start_version'] = '5.5'
    refapp['end_version'] = '6.7'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repo"]}:5.6.6',
        f'{refapp["docker_repo"]}:6.4.4',
        f'{refapp["docker_repo"]}:6.5.4',
    }
    unexpected_tags = {
        f'{refapp["docker_repo"]}:5.4.3',
        f'{refapp["docker_repo"]}:6.7.7',
        f'{refapp["docker_repo"]}:6.7.8',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_run_py_create(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    for key, value in refapp.items():
        if value is None:
            continue
        if isinstance(value, bool):
            os.environ[key.upper()] = str(value).lower()
        elif isinstance(value, list):
            os.environ[key.upper()] = ','.join(value)
        else:
            os.environ[key.upper()] = value
    os.environ['INTEGRATION_TEST_SCRIPT'] = ""

    from run import main, parser
    args = parser.parse_args(['--create'])
    main(args)

    expected_tags = {
        f'"{refapp["docker_repo"]}:6.5.4"',
        f'{refapp["docker_repo"]}:6.7.8'
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:5.4.3"',
        f'"{refapp["docker_repo"]}:5.6.7"',
        f'"{refapp["docker_repo"]}:6.7.7"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_run_py_update(mocked_docker, mocked_docker_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    for key, value in refapp.items():
        if value is None:
            continue
        if isinstance(value, bool):
            os.environ[key.upper()] = str(value).lower()
        elif isinstance(value, list):
            os.environ[key.upper()] = ','.join(value)
        else:
            os.environ[key.upper()] = value
    os.environ['INTEGRATION_TEST_SCRIPT'] = ""

    from run import main, parser
    args = parser.parse_args(['--update'])
    main(args)

    expected_tags = {
        f'"{refapp["docker_repo"]}:6.5.4"',
        f'"{refapp["docker_repo"]}:6.7.7"',
        f'"{refapp["docker_repo"]}:6.7.8"',
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:5.4.3"',
        f'"{refapp["docker_repo"]}:5.6.7"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7', '6.0.0-RC1'})
@mock.patch('releasemanager.eap_versions', return_value={'6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2'})
def test_create_eap_releases(mocked_docker, mocked_docker_tags, mocked_eap_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_eap_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.0.0-m55"',
        f'{refapp["docker_repo"]}:6.0.0-RC2',
        'eap'
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:6.0.0-RC1"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7', '6.0.0-RC1'})
@mock.patch('releasemanager.eap_versions', return_value={'6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2'})
def test_create_eap_releases(mocked_docker, mocked_docker_tags, mocked_eap_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_eap_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.0.0-m55"',
        f'{refapp["docker_repo"]}:6.0.0-RC2',
        'eap'
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:6.0.0-RC1"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags')
@mock.patch('releasemanager.eap_versions', return_value={'6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2'})
def test_calculate_eap_tags(mocked_docker, mocked_docker_tags, mocked_eap_versions, refapp):
    rm = ReleaseManager(**refapp)

    test_tag = '6.0.0-RC1'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.0.0-RC1', '6.0.0-RC1-jdk8', '6.0.0-RC1-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '6.0.0-RC2'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.0.0-RC2', '6.0.0-RC2-jdk8', '6.0.0-RC2-ubuntu',
        'eap', 'eap-jdk8', 'eap-ubuntu',
    }
    assert expected_tags == tags


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.docker_tags', return_value={'5.6.7', '6.7.7', '6.0.0-RC1'})
@mock.patch('releasemanager.eap_versions', return_value={'6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2', '7.0.0-RC2'})
def test_eap_version_ranges(mocked_docker, mocked_docker_tags, mocked_eap_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['start_version'] = '5.5'
    refapp['end_version'] = '6.7'
    rm = ReleaseManager(**refapp)
    rm.create_eap_releases()
    expected_tags = {
        f'"{refapp["docker_repo"]}:6.0.0-m55"',
        f'{refapp["docker_repo"]}:6.0.0-RC2'
    }
    unexpected_tags = {
        f'"{refapp["docker_repo"]}:6.0.0-RC1"',
        f'"{refapp["docker_repo"]}:7.0.0-RC2"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text
