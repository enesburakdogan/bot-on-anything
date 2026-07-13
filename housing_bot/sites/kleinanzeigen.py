# encoding:utf-8

import re

from bs4 import BeautifulSoup

from common import log
from housing_bot.listing import Listing
from housing_bot.sites.base import BaseSite

BASE_URL = "https://www.kleinanzeigen.de"
# Berlin rental flats (category 203, location 3331), offers only, first page
DEFAULT_SEARCH_URLS = [BASE_URL + "/s-wohnung-mieten/anzeige:angebote/berlin/c203l3331"]

CONTACT_URL = BASE_URL + "/s-anbieter-kontaktieren.json"


class KleinanzeigenSite(BaseSite):
    key = "kleinanzeigen"

    def __init__(self, conf):
        super().__init__(conf)
        if not self.search_urls:
            self.search_urls = DEFAULT_SEARCH_URLS
        self.contact = conf.get("contact", {})
        # Kleinanzeigen's login form is captcha-protected, so instead of
        # automating login we accept a cookie string copied from the user's
        # own logged-in browser session (dev tools -> request header Cookie).
        cookie_header = conf.get("cookies", "")
        if cookie_header:
            for part in cookie_header.split(";"):
                if "=" in part:
                    name, value = part.split("=", 1)
                    self.session.cookies.set(name.strip(), value.strip(), domain=".kleinanzeigen.de")

    # ---------- search ----------

    def search(self):
        listings = []
        for url in self.search_urls:
            try:
                resp = self.get(url)
                if resp.status_code != 200:
                    log.warn("[HousingBot][kleinanzeigen] search page {} -> HTTP {}", url, resp.status_code)
                    continue
                listings.extend(self._parse_search_page(resp.text))
            except Exception as e:
                log.warn("[HousingBot][kleinanzeigen] search failed for {}: {}", url, str(e))
        return listings

    def _parse_search_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for card in soup.select('[data-adid][data-href]'):
            listing = self._parse_card(card)
            if listing:
                results.append(listing)
        return results

    def _parse_card(self, card):
        ad_id = card.get("data-adid", "")
        href = card.get("data-href", "")
        if not ad_id or not href.startswith("/"):
            return None
        title_link = card.select_one("h2 a") or card.select_one('a[href^="/s-anzeige"]')
        title = title_link.get_text(strip=True) if title_link else ""
        if not title:
            # fall back to the URL slug, e.g. /s-anzeige/schoene-wohnung/123-203-3472
            slug = href.split("/")[2] if href.count("/") >= 2 else ""
            title = slug.replace("-", " ").strip()
        listing = Listing(
            site=self.key,
            listing_id=ad_id,
            url=BASE_URL + href,
            title=title,
        )

        loc = card.select_one(".aditem-main--top--left")
        if loc:
            # "13189 Pankow" -> district after the zip code
            loc_text = re.sub(r"\s+", " ", loc.get_text(" ", strip=True))
            listing.address = loc_text
            m = re.match(r"(\d{5})\s+(.*)", loc_text)
            if m:
                listing.district = m.group(2)

        desc = card.select_one(".aditem-main--middle--description")
        if desc:
            listing.description = desc.get_text(" ", strip=True)

        price_el = card.select_one(".aditem-main--middle--price-shipping--price")
        if price_el:
            m = re.search(r"([\d.]+)\s*€", price_el.get_text(strip=True))
            if m:
                listing.price = int(m.group(1).replace(".", ""))

        tags = card.select_one(".aditem-main--middle--tags")
        if tags:
            tags_text = tags.get_text(" ", strip=True)
            m = re.search(r"([\d.,]+)\s*m²", tags_text)
            if m:
                listing.size = float(m.group(1).replace(".", "").replace(",", "."))
            m = re.search(r"([\d,.]+)\s*Zi", tags_text)
            if m:
                listing.rooms = float(m.group(1).replace(",", "."))
        return listing

    # ---------- apply ----------

    def apply(self, listing, message):
        """Send a contact message via the ad page's contact form endpoint.

        Requires either a logged-in cookie session (config: cookies) or, for
        ads that allow guest contact, the applicant name fields below.
        """
        try:
            page = self.get(listing.url)
            if page.status_code != 200:
                return False, "ad_page_http_{}".format(page.status_code)
            soup = BeautifulSoup(page.text, "html.parser")
            csrf_meta = soup.select_one('meta[name="_csrf"]')
            csrf_header_meta = soup.select_one('meta[name="_csrf_header"]')
            if csrf_meta is None:
                return False, "no_csrf_token"
            csrf_header = csrf_header_meta["content"] if csrf_header_meta else "X-CSRF-TOKEN"

            form = soup.select_one("#viewad-contact-modal-form")
            data = {
                "adId": listing.listing_id,
                "adType": "unknown",
                "message": message,
            }
            if form is not None:
                for hidden in form.select('input[type="hidden"][name]'):
                    data.setdefault(hidden["name"], hidden.get("value", ""))
                data["adId"] = listing.listing_id
                data["message"] = message
            for field in ("contactFirstName", "contactLastName", "phoneNumber"):
                if self.contact.get(field):
                    data[field] = self.contact[field]

            headers = {
                csrf_header: csrf_meta["content"],
                "X-Requested-With": "XMLHttpRequest",
                "Referer": listing.url,
            }
            resp = self.post(CONTACT_URL, data=data, headers=headers)
            if resp.status_code == 200 and "error" not in resp.text.lower():
                log.info("[HousingBot][kleinanzeigen] application sent for {}", listing.uid)
                return True, "sent"
            log.warn("[HousingBot][kleinanzeigen] apply failed for {}: HTTP {} {}",
                     listing.uid, resp.status_code, resp.text[:300])
            if resp.status_code in (401, 403):
                return False, "login_required_refresh_cookies"
            return False, "http_{}".format(resp.status_code)
        except Exception as e:
            log.warn("[HousingBot][kleinanzeigen] apply error for {}: {}", listing.uid, str(e))
            return False, "error"
