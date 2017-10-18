import json

import requests

def mac_versions(product_key, limit=100):
    params = {'limit': limit}
    r = requests.get(f'https://marketplace.atlassian.com/rest/2/products/key/{product_key}/versions',
                     params=params)
    version_data = json.loads(r.text)
    mac_versions = {v['name'] for v in version_data['_embedded']['versions']}
    return mac_versions


def docker_tags(repo):
    r = requests.get(f'https://index.docker.io/v1/repositories/{repo}/tags')
    tag_data = json.loads(r.text)
    tags = {t['name'] for t in tag_data}
    return tags


def minor_is_latest(version, all_versions):
    major_minor_version = '.'.join(version.split('.')[:2])
    minor_versions = [v for v in all_versions if v.startswith(major_minor_version)]
    minor_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
    return version in minor_versions[-1:]


def major_is_latest(version, all_versions):
    major_version = version.split('.')[0]
    major_versions = [v for v in all_versions if v.startswith(major_version)]
    major_versions.sort(key=lambda s: [int(u) for u in s.split('.')])
    return version in major_versions[-1:]


def version_is_latest(version, all_versions):
    versions = [v for v in all_versions]
    versions.sort(key=lambda s: [int(u) for u in s.split('.')])
    return version in versions[-1:]
