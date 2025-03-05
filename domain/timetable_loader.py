from urllib.parse import urlparse
import requests


def download_timetable_from_url(url: str, into_filename: str):
    o = urlparse(url)
    export_url = o._replace(
        fragment="",
        query="format=xlsx",
        path="/".join(o.path.split("/")[:4]) + "/export",
    ).geturl()

    resp = requests.get(export_url, timeout=10)
    with open(into_filename, "wb") as f:
        f.write(resp.content)
