import itertools
import logging
import importlib
import os
import re
from unittest import mock

import docker
import pytest

from releasemanager import fetch_mac_eap_versions, existing_tags, fetch_mac_versions, fetch_pac_release_versions, fetch_pac_eap_versions, ReleaseManager, str2bool, Version, latest_minor, batch_job

class Dict2Class(object):
    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])

def test_existing_tags(refapp):
    tags = existing_tags(refapp['docker_repos'][0])
    assert len(tags) > 0
    assert isinstance(tags, set)
    assert all([isinstance(v, str) for v in tags])

def test_mac_release_versions(refapp):
    versions = fetch_mac_versions(refapp['mac_product_key'])
    assert len(versions) > 0
    assert isinstance(versions, list)
    assert all([i.isdigit() for v in versions for i in v.split('.')])

def test_pac_release_versions():
    versions = fetch_pac_release_versions('bitbucket-mesh')
    assert len(versions) > 0
    assert isinstance(versions, list)
    assert all([i.isdigit() for v in versions for i in v.split('.')])

def test_mac_eap_versions(refapp):
    versions = fetch_mac_eap_versions(refapp['mac_product_key'])
    assert isinstance(versions, list)

def test_pac_eap_versions():
    versions = fetch_pac_eap_versions('bitbucket-mesh')
    assert isinstance(versions, list)
    for v in versions:
        assert re.match(r'[\d\.]+-(rc|m)\d+', str.lower(v)) != None


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


def test_slice_job_short():
    versions = ['8.16.0-RC02', '8.16.0-RC01', '8.16.0-EAP03', '8.16.0-EAP02', '8.16.0-EAP01']
    assert batch_job(versions, 12, 0) == [versions[0]]
    assert batch_job(versions, 12, 1) == [versions[1]]
    assert batch_job(versions, 12, 2) == [versions[2]]
    assert batch_job(versions, 12, 3) == [versions[3]]
    assert batch_job(versions, 12, 4) == [versions[4]]

    assert batch_job(versions, 12, 9) == []
    assert batch_job(versions, 12, 5) == []
    assert batch_job(versions, 12, 11) == []

def test_slice_job_long():
     versions = [f"3.2.{i}" for i in range(68)]
     assert batch_job(versions, 12, 0) == versions[0:6]
     assert batch_job(versions, 12, 1) == versions[6:12]
     assert batch_job(versions, 12, 11) == versions[63:68]

     processed = []
     for off in range(12):
         processed += batch_job(versions, 12, off)
     assert processed == versions

def test_slice_includes_all_versions():
    versions = ['8.1.4', '8.1.3', '8.1.2', '8.1.1', '8.0.6', '8.0.5', '8.0.4', '8.0.3', '8.0.2', '8.0.1', '8.0.0']
    assert batch_job(versions, 8, 0) == versions[0:2]
    assert batch_job(versions, 8, 1) == versions[2:4]
    assert batch_job(versions, 8, 2) == versions[4:6]
    assert batch_job(versions, 8, 3) == versions[6:7]
    assert batch_job(versions, 8, 4) == versions[7:8]
    assert batch_job(versions, 8, 5) == versions[8:9]
    assert batch_job(versions, 8, 6) == versions[9:10]
    assert batch_job(versions, 8, 7) == versions[10:11]


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.get_targets')
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.7.7', '6.7.8'})
def test_calculate_tags(mocked_docker, mocked_get_targets, mocked_mac_versions, refapp):
    rm = ReleaseManager(**refapp)

    test_tag = '6.7.8'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6', '6.7', '6.7.8',
        '6-jdk11', '6.7-jdk11', '6.7.8-jdk11',
        '6-ubuntu', '6.7-ubuntu', '6.7.8-ubuntu',
        'latest', 'jdk11', 'ubuntu',
    }
    assert expected_tags == tags

    test_tag = '6.7.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.7.7',
        '6.7.7-jdk11',
        '6.7.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.6.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5', '5.6', '5.6.7',
        '5-jdk11', '5.6-jdk11', '5.6.7-jdk11',
        '5-ubuntu', '5.6-ubuntu', '5.6.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.4.3'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5.4', '5.4.3',
        '5.4-jdk11', '5.4.3-jdk11',
        '5.4-ubuntu', '5.4.3-ubuntu',
    }
    assert expected_tags == tags

    refapp['default_release'] = False
    rm = ReleaseManager(**refapp)

    test_tag = '6.7.8'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6-jdk11', '6.7-jdk11', '6.7.8-jdk11',
        '6-ubuntu', '6.7-ubuntu', '6.7.8-ubuntu',
        'jdk11', 'ubuntu'
    }
    assert expected_tags == tags

    test_tag = '6.7.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.7.7-jdk11',
        '6.7.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.6.7'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5-jdk11', '5.6-jdk11', '5.6.7-jdk11',
        '5-ubuntu', '5.6-ubuntu', '5.6.7-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '5.4.3'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '5.4-jdk11', '5.4.3-jdk11',
        '5.4-ubuntu', '5.4.3-ubuntu',
    }
    assert expected_tags == tags


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_create_releases(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.4',
        f'{refapp["docker_repos"][0]}:6.7.8'
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:5.6.7',
        f'{refapp["docker_repos"][0]}:6.7.7',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_update_releases(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.update_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.4',
        f'{refapp["docker_repos"][0]}:6.7.7',
        f'{refapp["docker_repos"][0]}:6.7.8',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:5.6.7',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.5.5', '6.7.7', '6.5.4-jdk11', '6.5.5-ubuntu'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.5.5', '6.7.7', '6.7.8'})
def test_create_competing_releases(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.4',
        f'{refapp["docker_repos"][0]}:6.7.8',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.5',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text

    refapp['default_release'] = False
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.7.7-jdk11',
        f'{refapp["docker_repos"][0]}:6.7.8-jdk11',
        f'{refapp["docker_repos"][0]}:6.5.4-ubuntu',
        f'{refapp["docker_repos"][0]}:6.5.4-jdk11',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'"{refapp["docker_repos"][0]}:5.6.7"',
        f'"{refapp["docker_repos"][0]}:6.7.7"',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value=set())
@mock.patch('releasemanager.fetch_mac_versions', return_value={'6.5.5', '6.7.7', '6.7.8'})
def test_raise_exceptions(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
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
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_custom_buildargs(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['dockerfile_buildargs'] = 'ARTEFACT=jira-software,BASE_IMAGE=adoptopenjdk/openjdk11:slim'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    assert 'ARTEFACT=jira-software' in caplog.text
    assert 'BASE_IMAGE=adoptopenjdk/openjdk11:slim' in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_create_releases_with_specified_dockerfile(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    custom_dockerfile = 'Dockerfile-test-123'
    refapp['dockerfile'] = 'Dockerfile-test-123'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    assert custom_dockerfile in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.4.4', '6.5.4', '6.7.7', '6.7.8'})
def test_start_version(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['start_version'] = '6.5'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.4',
        f'{refapp["docker_repos"][0]}:6.7.8',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:5.6.7',
        f'{refapp["docker_repos"][0]}:6.4.4',
        f'{refapp["docker_repos"][0]}:6.7.7',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.4.4', '6.5.4', '6.7.7', '6.7.8'})
def test_end_version(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['end_version'] = '6.7'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.4.4',
        f'{refapp["docker_repos"][0]}:6.5.4',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:5.6.7',
        f'{refapp["docker_repos"][0]}:6.7.7',
        f'{refapp["docker_repos"][0]}:6.7.8',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.6', '5.6.7', '6.4.4', '6.5.4', '6.7.7', '6.7.8'})
def test_min_end_version(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['start_version'] = '5.5'
    refapp['end_version'] = '6.7'
    rm = ReleaseManager(**refapp)
    rm.create_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:5.6.6',
        f'{refapp["docker_repos"][0]}:6.4.4',
        f'{refapp["docker_repos"][0]}:6.5.4',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:6.7.7',
        f'{refapp["docker_repos"][0]}:6.7.8',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_make_release_create(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)

    args = Dict2Class(refapp)
    args.create = True
    args.create_eap = False
    args.update = False
    args.docker_repos = ','.join(refapp['docker_repos'])

    mr = importlib.import_module("make-releases")
    mr.main(args)

    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.4',
        f'{refapp["docker_repos"][0]}:6.7.8'
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:5.6.7',
        f'{refapp["docker_repos"][0]}:6.7.7',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7'})
@mock.patch('releasemanager.fetch_mac_versions', return_value={'5.4.3', '5.6.7', '6.5.4', '6.7.7', '6.7.8'})
def test_make_release_update(mocked_docker, mocked_existing_tags, mocked_mac_versions, caplog, refapp):
    caplog.set_level(logging.INFO)

    args = Dict2Class(refapp)
    args.create = False
    args.create_eap = False
    args.update = True
    args.docker_repos = ','.join(refapp['docker_repos'])

    mr = importlib.import_module("make-releases")
    mr.main(args)

    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.5.4',
        f'{refapp["docker_repos"][0]}:6.7.7',
        f'{refapp["docker_repos"][0]}:6.7.8',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:5.4.3',
        f'{refapp["docker_repos"][0]}:5.6.7',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7', '6.0.0-RC1'})
@mock.patch('releasemanager.fetch_mac_eap_versions', return_value={'4.0.0-RC1', '6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2'})
def test_create_eap_releases(mocked_docker, mocked_existing_tags, mocked_eap_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)
    rm.create_eap_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.0.0-m55',
        f'{refapp["docker_repos"][0]}:6.0.0-RC2',
        'eap'
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:6.0.0-RC1',
        f'{refapp["docker_repos"][0]}:4.0.0-RC1',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags')
@mock.patch('releasemanager.fetch_mac_eap_versions', return_value={'6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2'})
def test_calculate_eap_tags(mocked_docker, mocked_existing_tags, mocked_eap_versions, refapp):
    rm = ReleaseManager(**refapp)

    test_tag = '6.0.0-RC1'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.0.0-RC1', '6.0.0-RC1-jdk11', '6.0.0-RC1-ubuntu',
    }
    assert expected_tags == tags

    test_tag = '6.0.0-RC2'
    tags = rm.calculate_tags(test_tag)
    expected_tags = {
        '6.0.0-RC2', '6.0.0-RC2-jdk11', '6.0.0-RC2-ubuntu',
        'eap', 'eap-jdk11', 'eap-ubuntu',
    }
    assert expected_tags == tags


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7', '6.0.0-RC1'})
@mock.patch('releasemanager.fetch_mac_eap_versions', return_value={'4.0.0-RC1', '6.0.0-RC1', '6.0.0-m55', '6.0.0-RC2', '7.0.0-RC2'})
def test_eap_version_ranges(mocked_docker, mocked_existing_tags, mocked_eap_versions, caplog, refapp):
    caplog.set_level(logging.INFO)
    refapp['start_version'] = '5.5'
    refapp['end_version'] = '6.7'
    rm = ReleaseManager(**refapp)
    rm.create_eap_releases()
    expected_tags = {
        f'{refapp["docker_repos"][0]}:6.0.0-RC2',
        f'{refapp["docker_repos"][0]}:6.0.0-RC2-jdk11',
        f'{refapp["docker_repos"][0]}:7.0.0-RC2',
    }
    unexpected_tags = {
        f'{refapp["docker_repos"][0]}:6.0.0-RC1',
        f'{refapp["docker_repos"][0]}:4.0.0-RC1',
    }
    for tag in expected_tags:
        assert tag in caplog.text
    for tag in unexpected_tags:
        assert tag not in caplog.text


@mock.patch('releasemanager.docker.from_env')
@mock.patch('releasemanager.existing_tags', return_value={'5.6.7', '6.7.7', '6.0.0-RC1'})
@mock.patch('releasemanager.fetch_mac_eap_versions', return_value={'5.9.9-RC1', '6.0.0-m55', '6.0.0-RC2', '6.0.0-EAP01'})
@mock.patch.object(ReleaseManager, '_push_release')
def test_create_eap_releases_flagged(mocked_method, mocked_docker, mocked_eap_versions, mocked_existing_tags, caplog, refapp):
    caplog.set_level(logging.INFO)
    rm = ReleaseManager(**refapp)

    rm.create_eap_releases()

    mocked_method.assert_any_call('docker-public.packages.atlassian.com/atlassian/bitbucket-server:6.0.0-EAP01', True)
    mocked_method.assert_any_call('docker-public.packages.atlassian.com/atlassian/bitbucket-server:6.0.0-EAP01-jdk11', True)
    mocked_method.assert_any_call('docker-public.packages.atlassian.com/atlassian/bitbucket-server:6.0.0-RC2', True)
    mocked_method.assert_any_call('docker-public.packages.atlassian.com/atlassian/bitbucket-server:6.0.0-RC2-jdk11', True)
    mocked_method.assert_any_call('docker-public.packages.atlassian.com/atlassian/bitbucket-server:6.0.0-m55', True)

