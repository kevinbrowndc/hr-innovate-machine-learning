"""Private GitHub create-only archive. Administrators remain outside the trust boundary."""
import base64
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import quote

import requests


class Withheld(RuntimeError):
    """Safe, non-sensitive operational reason; never include response bodies."""


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


class GitHubArchive:
    def __init__(self, repository, token, branch="main", session=None):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository or "") or not token:
            raise Withheld("Private archive configuration missing")
        self.root = f"https://api.github.com/repos/{repository}"
        self.branch = branch
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}",
                                     "Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28"})
        meta = self.request("GET", "").json()
        if meta.get("private") is not True or meta.get("archived"):
            raise Withheld("Archive must be an active private repository")

    def request(self, method, path, **kwargs):
        try:
            response = self.session.request(method, self.root + path, timeout=40, **kwargs)
        except requests.RequestException:
            raise Withheld("Private archive unavailable") from None
        if response.status_code not in (200, 201, 404, 409, 422):
            raise Withheld("Private archive request rejected")
        if response.status_code == 404 and path == "":
            raise Withheld("Private archive not accessible")
        return response

    @staticmethod
    def path(key):
        if not re.fullmatch(r"[a-zA-Z0-9_./-]+", key) or ".." in key or key.startswith("/"):
            raise Withheld("Invalid archive key")
        return "/contents/" + quote(key, safe="/")

    def read(self, key):
        path = self.path(key)
        head = self.request("GET", path, params={"ref": self.branch})
        if head.status_code == 404:
            return None
        history = self.request("GET", "/commits", params={"path": key, "sha": self.branch, "per_page": 2})
        commits = history.json()
        if not isinstance(commits, list) or len(commits) != 1:
            raise Withheld("Archive record has been modified; manual audit required")
        commit = commits[0]
        original = self.request("GET", path, params={"ref": commit["sha"]})
        if original.json().get("sha") != head.json().get("sha"):
            raise Withheld("Archive history mismatch")
        obj = original.json()
        if obj.get("encoding") == "base64":
            body = base64.b64decode(obj["content"])
        else:
            raw = self.request("GET", path, params={"ref": commit["sha"]},
                               headers={"Accept": "application/vnd.github.raw+json"})
            body = raw.content
        if len(body) > 10_000_000:
            raise Withheld("Archive record exceeds size limit")
        created = datetime.fromisoformat(commit["commit"]["committer"]["date"].replace("Z", "+00:00"))
        return body, created

    def create(self, key, body):
        if self.read(key) is not None:
            raise Withheld("Archive record already exists; replacement prohibited")
        response = self.request("PUT", self.path(key), json={
            "message": "Append private pilot record", "branch": self.branch,
            "content": base64.b64encode(body).decode()})
        # No SHA, author or committer override: never an update, server timestamp only.
        if response.status_code != 201:
            raise Withheld("Archive creation conflict; no replacement attempted")
        saved = self.read(key)
        if saved is None or saved[0] != body:
            raise Withheld("Archive verification failed")
        return saved

    def json(self, key):
        record = self.read(key)
        return None if record is None else (json.loads(record[0]), record[1])
