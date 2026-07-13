# encoding:utf-8

from common import log

DEFAULT_TEMPLATE = (
    "Sehr geehrte Damen und Herren,\n\n"
    "ich habe Ihre Anzeige \"{title}\" gesehen und bin sehr an der Wohnung interessiert. "
    "Ich bin {name}, {occupation}, mit einem geregelten Einkommen. "
    "Gerne würde ich die Wohnung besichtigen. Alle Unterlagen (SCHUFA, Gehaltsnachweise, "
    "Mietschuldenfreiheitsbescheinigung) kann ich sofort vorlegen.\n\n"
    "Ich freue mich auf Ihre Rückmeldung.\n\n"
    "Mit freundlichen Grüßen\n"
    "{name}\n"
    "{phone}"
)


class MessageBuilder:
    """Builds the application message for a listing.

    Default mode fills a static template with applicant info and listing
    fields. If apply.ai.enabled is true, the configured bot-on-anything
    model (config.json -> model.type) is asked to personalize the message
    per listing, falling back to the template on any error.
    """

    def __init__(self, apply_conf):
        self.template = apply_conf.get("message_template") or DEFAULT_TEMPLATE
        self.applicant = apply_conf.get("applicant", {})
        ai_conf = apply_conf.get("ai", {})
        self.ai_enabled = bool(ai_conf.get("enabled"))
        self._model = None
        if self.ai_enabled:
            try:
                from model import model_factory
                import config as app_config
                model_type = app_config.conf().get("model", {}).get("type")
                self._model = model_factory.create_bot(model_type)
                log.info("[HousingBot] AI message personalization enabled via model: {}", model_type)
            except Exception as e:
                log.warn("[HousingBot] AI model init failed, falling back to template: {}", str(e))
                self.ai_enabled = False

    def build(self, listing):
        base = self._render_template(listing)
        if not self.ai_enabled or self._model is None:
            return base
        try:
            prompt = (
                "Du hilfst einem Wohnungssuchenden in Berlin. Formuliere die folgende "
                "Bewerbungsnachricht so um, dass sie konkret auf diese Anzeige eingeht. "
                "Bleibe höflich, ehrlich und kurz (max. 150 Wörter). Erfinde keine Fakten "
                "über den Bewerber.\n\n"
                "Anzeige: {title}\n{district} | {price} EUR | {size} m2 | {rooms} Zimmer\n"
                "Beschreibung: {description}\n\n"
                "Basisnachricht:\n{base}\n\n"
                "Gib NUR die fertige Nachricht aus."
            ).format(
                title=listing.title,
                district=listing.district,
                price=listing.price or "?",
                size=listing.size or "?",
                rooms=listing.rooms or "?",
                description=(listing.description or "")[:600],
                base=base,
            )
            reply = self._model.reply(prompt, {"from_user_id": "housing_bot", "session_id": listing.uid})
            if isinstance(reply, str) and len(reply.strip()) > 50:
                return reply.strip()
            log.warn("[HousingBot] AI reply unusable, using template for {}", listing.uid)
        except Exception as e:
            log.warn("[HousingBot] AI message generation failed for {}: {}", listing.uid, str(e))
        return base

    def _render_template(self, listing):
        fields = {
            "title": listing.title,
            "url": listing.url,
            "price": listing.price,
            "size": listing.size,
            "rooms": listing.rooms,
            "district": listing.district,
            "name": self.applicant.get("name", ""),
            "occupation": self.applicant.get("occupation", ""),
            "phone": self.applicant.get("phone", ""),
            "email": self.applicant.get("email", ""),
            "about": self.applicant.get("about", ""),
        }

        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        return self.template.format_map(_SafeDict(fields))
