import json

import requests

def mac_versions(product_key, limit=100):
    params = {'limit': limit}
    r = requests.get(f'https://marketplace.atlassian.com/rest/2/products/key/{product_key}/versions',
                     params=params)
    version_data = json.loads(r.text)
    mac_versions = {v['name'] for v in version_data['_embedded']['versions']}
    return mac_versions


def latest_mac_version(product_key):
    r = requests.get(f'https://marketplace.atlassian.com/rest/2/products/key/{product_key}/versions/latest')
    version_data = json.loads(r.text)
    latest = version_data['name']
    return latest


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

