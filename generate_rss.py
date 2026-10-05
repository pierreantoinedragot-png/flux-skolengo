import requests
import html
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

WORDPRESS_API = (
    "https://col58-genevoix.sd.ac-dijon.fr/"
    "wp-json/wp/v2/posts"
)

SITE_URL = "https://col58-genevoix.sd.ac-dijon.fr"
NOMBRE_ARTICLES = 20

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


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def first_image(content):
    """
    Récupère l'URL de la première image de l'article.
    """

    if not content:
        return None

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        content,
        re.IGNORECASE
    )

    if match:
        url = html.unescape(match.group(1))

        # On force HTTPS si WordPress fournit encore HTTP
        if url.startswith("http://"):
            url = "https://" + url[7:]

        return url

    return None


rss = Element(
    "rss",
    {
        "version": "2.0",
        "xmlns:media": "http://search.yahoo.com/mrss/"
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
    "Les dernières actualités du collège Maurice Genevoix de Decize."
)

SubElement(
    channel,
    "language"
).text = "fr-FR"

SubElement(
    channel,
    "generator"
).text = "Flux RSS personnalisé Skolengo"


for article in articles:

    if article.get("status") != "publish":
        continue

    item = SubElement(channel, "item")

    title = clean_text(
        article.get("title", {}).get("rendered", "")
    )

    SubElement(item, "title").text = title

    url = article.get("link", SITE_URL)

    SubElement(item, "link").text = url

    SubElement(
        item,
        "guid",
        {"isPermaLink": "true"}
    ).text = url

    date_string = article.get("date_gmt")

    if date_string:

        date = datetime.fromisoformat(
            date_string.replace("Z", "+00:00")
        )

        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        SubElement(
            item,
            "pubDate"
        ).text = format_datetime(date)

    description = clean_text(
        article.get("excerpt", {}).get("rendered", "")
    )

    if not description:
        description = clean_text(
            article.get("content", {}).get("rendered", "")
        )

    if len(description) > 500:
        description = description[:500].rstrip() + "…"

    SubElement(
        item,
        "description"
    ).text = description

    # Première image de l'article
    image_url = first_image(
        article.get("content", {}).get("rendered", "")
    )

    if image_url:

        SubElement(
            item,
            "media:content",
            {
                "url": image_url,
                "medium": "image",
                "type": "image/jpeg"
            }
        )


xml = tostring(
    rss,
    encoding="utf-8",
    xml_declaration=True
)

with open("rss.xml", "wb") as file:
    file.write(xml)

print(
    f"Flux RSS généré avec {len(articles)} articles."
)
