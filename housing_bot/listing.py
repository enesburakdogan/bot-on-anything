# encoding:utf-8

from dataclasses import dataclass, field


@dataclass
class Listing:
    """A single flat listing found on one of the supported sites."""
    site: str                    # site key, e.g. "wg_gesucht"
    listing_id: str              # site-local unique id
    url: str
    title: str = ""
    price: int = 0               # cold/total rent in EUR as shown on the list page, 0 = unknown
    size: float = 0.0            # living space in m2, 0 = unknown
    rooms: float = 0.0           # number of rooms, 0 = unknown
    district: str = ""           # e.g. "Neukölln"
    address: str = ""
    available_from: str = ""
    description: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def uid(self):
        """Globally unique id across sites, used for deduplication."""
        return "{}:{}".format(self.site, self.listing_id)

    def summary(self):
        parts = [self.title or "(no title)"]
        detail = []
        if self.price:
            detail.append("{} €".format(self.price))
        if self.size:
            detail.append("{:g} m²".format(self.size))
        if self.rooms:
            detail.append("{:g} oda".format(self.rooms))
        if self.district:
            detail.append(self.district)
        if detail:
            parts.append(" | ".join(detail))
        parts.append(self.url)
        return "\n".join(parts)
