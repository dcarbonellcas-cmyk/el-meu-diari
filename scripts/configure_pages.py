"""Select the custom Pages workflow using the runner's existing Pages permission."""
import json
import os
import urllib.request

url = 'https://api.github.com/repos/' + os.environ['GH_REPO'] + '/pages'
headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
           'Accept': 'application/vnd.github+json',
           'X-GitHub-Api-Version': '2022-11-28',
           'Content-Type': 'application/json'}
with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
    site = json.load(response)
if site.get('build_type') != 'workflow':
    request = urllib.request.Request(url, headers=headers,
                                     data=json.dumps({'build_type': 'workflow'}).encode(), method='PUT')
    with urllib.request.urlopen(request, timeout=30) as response:
        site = json.load(response)
assert site.get('build_type') == 'workflow', 'Pages is not configured for the diary workflow'
print('Pages configured for the diary workflow')
