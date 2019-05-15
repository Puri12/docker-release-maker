import logging
from unittest import mock

import pytest

from releasemanager import docker_tags, mac_versions, ReleaseManager, str2bool



def test_docker_tags(refapp):
    tags = docker_tags(refapp['docker_repo'])
    assert len(tags) > 0
    assert isinstance(tags, set)
    assert all([isinstance(v, str) for v in tags])


def test_mac_versions(refapp):
    versions = mac_versions(refapp['mac_product_key'])
    assert len(versions) > 0
    assert isinstance(versions, set)
    assert all([i.isdigit() for v in versions for i in v.split('.')])


@mock.patch('releasemanager.docker')
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


@mock.patch('releasemanager.docker')
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


@mock.patch('releasemanager.docker')
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


@mock.patch('releasemanager.docker')
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



