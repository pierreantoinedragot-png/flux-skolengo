import requests
import html
import re
from datetime import datetime
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

# ============================================================
# CONFIGURATION
# ============================================================

WORDPRESS_API = (
    "https://col58-genevoix.sd.ac-dijon.fr/"
    "wp-json/wp/v2/posts"
)

SITE_URL = "https://col58-genevoix.sd.ac-dijon.fr"

NOMBRE_ARTICLES = 20

# ============================================================
# RÉCUPÉRATION DES ARTICLES
# ============================================================

params = {
    "per_page": NOMBRE_ARTICLES,
    "orderby": "date",
    "order": "desc",
    "status": "publish"
}

response = requests.get(
    WORDPRESS_API,
    params=params,
    timeout=20
)

response.raise_for_status()

articles = response.json()

# ============================================================
# NETTOYAGE DU TEXTE
# ============================================================

def clean_text(text):

    if not text:
        return ""

    # Suppression des balises HTML
    text = re.sub(r"<[^>]+>", " ", text)

    # Décodage des entités HTML
    text = html.unescape(text)

    # Nettoyage des espaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# CRÉATION DU RSS
# ============================================================

rss = Element(
    "rss",
    {
        "version": "2.0"
    }
)

channel = SubElement(rss, "channel")

SubElement(
    channel,
    "title"
).text = "Actualités du collège Maurice Genevoix"

SubElement(
    channel,
    "link"
).text = SITE_URL

SubElement(
    channel,
    "description"
).text = (
    "Les dernières actualités du collège "
    "Maurice Genevoix de Decize."
)

SubElement(
    channel,
    "language"
).text = "fr-FR"

SubElement(
    channel,
    "generator"
).text = "Flux RSS personnalisé Skolengo"


# ============================================================
# ARTICLES
# ============================================================

for article in articles:

    if article.get("status") != "publish":
        continue

    item = SubElement(channel, "item")

    # --------------------------------------------------------
    # TITRE
    # --------------------------------------------------------

    title = clean_text(
        article.get("title", {}).get("rendered", "")
    )

    SubElement(
        item,
        "title"
    ).text = title

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    url = article.get("link", SITE_URL)

    SubElement(
        item,
        "link"
    ).text = url

    # --------------------------------------------------------
    # GUID
    # --------------------------------------------------------

    post_id = article.get("id")

    SubElement(
        item,
        "guid",
        {
            "isPermaLink": "true"
        }
    ).text = url

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_string = article.get("date_gmt")

    if date_string:

        date_string = date_string.replace(
            "Z",
            "+00:00"
        )

        date = datetime.fromisoformat(
            date_string
        )

        SubElement(
            item,
            "pubDate"
        ).text = format_datetime(date)

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = clean_text(
        article.get(
            "excerpt",
            {}
        ).get(
            "rendered",
            ""
        )
    )

    # Si l'extrait est vide, prendre le début du contenu

    if not description:

        description = clean_text(
            article.get(
                "content",
                {}
            ).get(
                "rendered",
                ""
            )
        )

    # Limitation du résumé

    if len(description) > 500:

        description = (
            description[:500].rstrip()
            + "…"
        )

    SubElement(
        item,
        "description"
    ).text = description


# ============================================================
# ÉCRITURE DU FICHIER RSS
# ============================================================

xml = tostring(
    rss,
    encoding="utf-8",
    xml_declaration=True
)

with open(
    "rss.xml",
    "wb"
) as file:

    file.write(xml)

print(
    f"Flux RSS généré avec {len(articles)} articles."
)
