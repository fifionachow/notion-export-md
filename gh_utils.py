import requests
import json
import os

GH_API_REPO = "https://api.github.com/repos"

def create_pull_request(owner, repo, title, body=None, base="master", head="dev"):
    url = "{GH_API_REPO}/{owner}/{repo}/pulls"

    headers = {
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': f'Bearer {os.environ["GH_TOKEN"]}',
    'Content-Type': 'text/plain'
    }

    payload = {
        "head":f"{owner}:{head}",
        "base":base,
        "title": title
    }

    if body:
        payload['body'] = body

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    return response.url