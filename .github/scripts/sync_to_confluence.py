import os
import re
import sys
import requests
import markdown
from pathlib import Path

BASE_URL = os.environ["CONFLUENCE_BASE_URL"]
EMAIL = os.environ["CONFLUENCE_EMAIL"]
TOKEN = os.environ["CONFLUENCE_API_TOKEN"]
SPACE_KEY = os.environ["CONFLUENCE_SPACE_KEY"]

auth = (EMAIL, TOKEN)
api = f"{BASE_URL}/wiki/rest/api/content"


def find_page(title):
    r = requests.get(api, params={"title": title, "spaceKey": SPACE_KEY, "expand": "version"}, auth=auth)
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None


def create_page(title, html, parent_id=None):
    body = {
        "type": "page",
        "title": title,
        "space": {"key": SPACE_KEY},
        "body": {"storage": {"value": html, "representation": "storage"}},
    }
    if parent_id:
        body["ancestors"] = [{"id": parent_id}]
    r = requests.post(api, json=body, auth=auth)
    r.raise_for_status()
    return r.json()


def update_page(page_id, version, title, html):
    body = {
        "version": {"number": version + 1},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": html, "representation": "storage"}},
    }
    r = requests.put(f"{api}/{page_id}", json=body, auth=auth)
    r.raise_for_status()
    return r.json()


def get_or_create_parent(dir_name):
    title = f"[GitHub] {dir_name}"
    page = find_page(title)
    if page:
        return page["id"]
    created = create_page(title, f"<p>GitHub リポジトリの <code>{dir_name}</code> ディレクトリと同期</p>")
    return created["id"]


def md_to_html(content):
    return markdown.markdown(content, extensions=["tables", "fenced_code", "nl2br"])


def get_title(content, filepath):
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return Path(filepath).stem.replace("-", " ").replace("_", " ")


def sync_file(filepath):
    path = Path(filepath)
    content = path.read_text(encoding="utf-8")
    title = f"[GitHub] {get_title(content, filepath)}"
    html = md_to_html(content)

    # ディレクトリが ops/co-create/ のように階層があれば親ページを作る
    parent_id = None
    if path.parent != Path("."):
        parent_id = get_or_create_parent(str(path.parent))

    page = find_page(title)
    if page:
        update_page(page["id"], page["version"]["number"], title, html)
        print(f"Updated: {filepath} → '{title}'")
    else:
        create_page(title, html, parent_id)
        print(f"Created: {filepath} → '{title}'")


if __name__ == "__main__":
    changed = Path("changed_files.txt").read_text().splitlines()
    changed = [f for f in changed if f.strip() and f.endswith(".md") and Path(f).exists()]

    if not changed:
        print("同期対象のmdファイルなし")
        sys.exit(0)

    for f in changed:
        sync_file(f)
