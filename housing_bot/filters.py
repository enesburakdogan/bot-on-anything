# encoding:utf-8

from common import log


class ListingFilter:
    """Decides whether a listing matches the user's search criteria.

    All criteria are optional; an unset criterion never rejects a listing.
    Values that the scraper could not extract (0 / empty) are treated
    permissively so a parsing gap does not silently hide listings.
    """

    def __init__(self, search_conf):
        self.max_rent = search_conf.get("max_rent", 0)
        self.min_rent = search_conf.get("min_rent", 0)
        self.min_rooms = search_conf.get("min_rooms", 0)
        self.max_rooms = search_conf.get("max_rooms", 0)
        self.min_size = search_conf.get("min_size", 0)
        self.districts = [d.strip().lower() for d in search_conf.get("districts", []) if d.strip()]
        self.exclude_keywords = [k.strip().lower() for k in search_conf.get("exclude_keywords", []) if k.strip()]

    def accept(self, listing):
        reason = self._reject_reason(listing)
        if reason:
            log.debug("[HousingBot] filtered out {}: {}", listing.uid, reason)
            return False
        return True

    def _reject_reason(self, listing):
        if self.max_rent and listing.price and listing.price > self.max_rent:
            return "rent {} > max {}".format(listing.price, self.max_rent)
        if self.min_rent and listing.price and listing.price < self.min_rent:
            return "rent {} < min {}".format(listing.price, self.min_rent)
        if self.min_rooms and listing.rooms and listing.rooms < self.min_rooms:
            return "rooms {} < min {}".format(listing.rooms, self.min_rooms)
        if self.max_rooms and listing.rooms and listing.rooms > self.max_rooms:
            return "rooms {} > max {}".format(listing.rooms, self.max_rooms)
        if self.min_size and listing.size and listing.size < self.min_size:
            return "size {} < min {}".format(listing.size, self.min_size)

        if self.districts:
            haystack = " ".join([listing.district, listing.address, listing.title]).lower()
            if not any(d in haystack for d in self.districts):
                return "district not in whitelist"

        if self.exclude_keywords:
            haystack = " ".join([listing.title, listing.description]).lower()
            for kw in self.exclude_keywords:
                if kw in haystack:
                    return "contains excluded keyword '{}'".format(kw)
        return None
