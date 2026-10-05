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


def normalize_url(url):
    if not url:
        return None

    url = html.unescape(url).strip()

    if url.startswith("//"):
        url = "https:" + url

    elif url.startswith("http://"):
        url = "https://" + url[7:]

    return url


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def image_type_from_url(url):
    """
    Détermine le type MIME de l'image à partir de son URL.
    """

    url = url.lower().split("?")[0]

    if url.endswith(".png"):
        return "image/png"

    if url.endswith(".webp"):
        return "image/webp"

    if url.endswith(".gif"):
        return "image/gif"

    if url.endswith(".avif"):
        return "image/avif"

    if url.endswith(".svg"):
        return "image/svg+xml"

    return "image/jpeg"


def first_image_from_content(content):
    """
    Cherche une image dans le HTML du contenu.
    """

    if not content:
        return None

    # 1. src="..."
    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        content,
        re.IGNORECASE
    )

    if match:
        return normalize_url(match.group(1))

    # 2. data-src="..."
    match = re.search(
        r'<img[^>]+data-src=["\']([^"\']+)["\']',
        content,
        re.IGNORECASE
    )

    if match:
        return normalize_url(match.group(1))

    # 3. srcset="..."
    match = re.search(
        r'<img[^>]+srcset=["\']([^"\']+)["\']',
        content,
        re.IGNORECASE
    )

    if match:
        srcset = match.group(1)

        # On prend la première URL du srcset
        first = srcset.split(",")[0].strip()
        url = first.split(" ")[0]

        return normalize_url(url)

    return None


def get_article_image(article):
    """
    Cherche l'image de l'article.

    Priorité :
    1. image à la une WordPress
    2. première image du contenu
    """

    embedded = article.get("_embedded", {})

    featured = embedded.get(
        "wp:featuredmedia",
        []
    )

    # -----------------------------------------------------
    # 1. IMAGE À LA UNE
    # -----------------------------------------------------

    if featured:

        media = featured[0]

        source_url = media.get(
            "source_url"
        )

        if source_url:

            url = normalize_url(
                source_url
            )

            mime_type = media.get(
                "mime_type"
            )

            if not mime_type:
                mime_type = image_type_from_url(
                    url
                )

            return url, mime_type

    # -----------------------------------------------------
    # 2. PREMIÈRE IMAGE DU CONTENU
    # -----------------------------------------------------

    content = article.get(
        "content",
        {}
    ).get(
        "rendered",
        ""
    )

    url = first_image_from_content(
        content
    )

    if url:

        return (
            url,
            image_type_from_url(url)
        )

    return None, None


# =========================================================
# RÉCUPÉRATION WORDPRESS
# =========================================================

params = {
    "per_page": NOMBRE_ARTICLES,
    "orderby": "date",
    "order": "desc",
    "status": "publish",
    "_embed": "wp:featuredmedia"
}

response = requests.get(
    WORDPRESS_API,
    params=params,
    timeout=30
)

response.raise_for_status()

articles = response.json()


# =========================================================
# CRÉATION DU RSS
# =========================================================

rss = Element(
    "rss",
    {
        "version": "2.0",
        "xmlns:media": "http://search.yahoo.com/mrss/"
    }
)

channel = SubElement(
    rss,
    "channel"
)

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


nombre_articles = 0
nombre_images = 0


# =========================================================
# ARTICLES
# =========================================================

for article in articles:

    if article.get("status") != "publish":
        continue

    nombre_articles += 1

    item = SubElement(
        channel,
        "item"
    )

    # -----------------------------------------------------
    # TITRE
    # -----------------------------------------------------

    title = clean_text(
        article.get(
            "title",
            {}
        ).get(
            "rendered",
            ""
        )
    )

    SubElement(
        item,
        "title"
    ).text = title

    # -----------------------------------------------------
    # URL
    # -----------------------------------------------------

    url = article.get(
        "link",
        SITE_URL
    )

    SubElement(
        item,
        "link"
    ).text = url

    # -----------------------------------------------------
    # GUID
    # -----------------------------------------------------

    SubElement(
        item,
        "guid",
        {
            "isPermaLink": "true"
        }
    ).text = url

    # -----------------------------------------------------
    # DATE
    # -----------------------------------------------------

    date_string = article.get(
        "date_gmt"
    )

    if date_string:

        date = datetime.fromisoformat(
            date_string.replace(
                "Z",
                "+00:00"
            )
        )

        if date.tzinfo is None:
            date = date.replace(
                tzinfo=timezone.utc
            )

        SubElement(
            item,
            "pubDate"
        ).text = format_datetime(date)

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    description = clean_text(
        article.get(
            "excerpt",
            {}
        ).get(
            "rendered",
            ""
        )
    )

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

    if len(description) > 500:

        description = (
            description[:500].rstrip()
            + "…"
        )

    SubElement(
        item,
        "description"
    ).text = description

    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    image_url, image_type = get_article_image(
        article
    )

    if image_url:

        SubElement(
            item,
            "media:content",
            {
                "url": image_url,
                "medium": "image",
                "type": image_type
            }
        )

        nombre_images += 1

        print(
            f"IMAGE : {title} -> {image_url}"
        )

    else:

        print(
            f"PAS D'IMAGE : {title}"
        )


# =========================================================
# ÉCRITURE
# =========================================================

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


print("")
print(
    f"Articles : {nombre_articles}"
)

print(
    f"Images trouvées : {nombre_images}/{nombre_articles}"
)
