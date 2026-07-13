# encoding:utf-8

import requests

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class BaseSite:
    """Common behaviour for a housing site adapter.

    Subclasses implement:
      - search(): return a list of Listing objects for the configured search URLs
      - apply(listing, message): send an application/contact message, return
        (ok: bool, status: str). Only called when apply.enabled and not dry_run.
    """

    key = "base"

    def __init__(self, conf):
        self.conf = conf
        self.search_urls = conf.get("search_urls", [])
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })

    def get(self, url, **kwargs):
        kwargs.setdefault("timeout", 30)
        return self.session.get(url, **kwargs)

    def post(self, url, **kwargs):
        kwargs.setdefault("timeout", 30)
        return self.session.post(url, **kwargs)

    def search(self):
        raise NotImplementedError

    def apply(self, listing, message):
        raise NotImplementedError
