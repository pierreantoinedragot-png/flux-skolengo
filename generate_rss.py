import requests
import html
import re
from email.utils import format_datetime
from datetime import datetime


WP_URL = "https://col58-genevoix.sd.ac-dijon.fr/wp-json/wp/v2/posts"

params = {
    "per_page": 10,
    "orderby": "date",
    "order": "desc",
    "_embed": "wp:featuredmedia"
}


# --------------------------------------------------
# Récupération des articles WordPress
# --------------------------------------------------

response = requests.get(WP_URL, params=params, timeout=30)
response.raise_for_status()

posts = response.json()


# --------------------------------------------------
# Recherche de l'image
# --------------------------------------------------

def get_image(post):

    # 1. Image mise en avant WordPress
    embedded = post.get("_embedded", {})
    media = embedded.get("wp:featuredmedia", [])

    if media:
        image = media[0].get("source_url")

        if image:
            return image.replace("http://", "https://")

    # 2. Sinon : première image trouvée dans l'article
    content = post.get("content", {}).get("rendered", "")

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        content,
        re.IGNORECASE
    )

    if match:
        return html.unescape(
            match.group(1)
        ).replace("http://", "https://")

    return ""


# --------------------------------------------------
# Création du flux RSS
# --------------------------------------------------

rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/">

<channel>

<title>Actualités du collège Maurice Genevoix</title>
<link>https://col58-genevoix.sd.ac-dijon.fr</link>
<description>Les dernières actualités du collège Maurice Genevoix de Decize.</description>
<language>fr-FR</language>
<generator>Flux RSS personnalisé Skolengo</generator>
"""


# --------------------------------------------------
# Ajout des 10 articles
# --------------------------------------------------

for post in posts:

    title = re.sub(
        r"<.*?>",
        "",
        post["title"]["rendered"]
    )

    title = html.unescape(title)

    link = post["link"].replace(
        "http://",
        "https://"
    )

    date_string = post["date_gmt"]

    dt = datetime.fromisoformat(
        date_string.replace("Z", "+00:00")
    )

    pubdate = format_datetime(dt)

    content = post.get(
        "content",
        {}
    ).get(
        "rendered",
        ""
    )

    # Suppression des scripts
    content = re.sub(
        r"<script.*?</script>",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL
    )

    content = content.replace(
        "http://",
        "https://"
    )

    # Texte pour description
    description = re.sub(
        r"<img[^>]*>",
        "",
        content,
        flags=re.IGNORECASE
    )

    description = re.sub(
        r"<[^>]+>",
        " ",
        description
    )

    description = html.unescape(
        description
    )

    description = re.sub(
        r"\s+",
        " ",
        description
    ).strip()

    # On limite le résumé
    if len(description) > 600:
        description = description[:600].rsplit(
            " ",
            1
        )[0] + "…"

    image = get_image(post)

    rss += """
<item>
"""

    rss += (
        "  <title>"
        + html.escape(title)
        + "</title>\n"
    )

    rss += (
        "  <link>"
        + html.escape(link)
        + "</link>\n"
    )

    rss += (
        "  <guid isPermaLink=\"true\">"
        + html.escape(link)
        + "</guid>\n"
    )

    rss += (
        "  <pubDate>"
        + pubdate
        + "</pubDate>\n"
    )

    rss += (
        "  <description><![CDATA["
        + description
        + "]]></description>\n"
    )

    # --------------------------------------------------
    # IMAGE POUR SKOLENGO
    # --------------------------------------------------

    if image:

        # Balise recommandée par Skolengo
        rss += (
            '  <enclosure url="'
            + html.escape(image, quote=True)
            + '" length="0" type="image/jpeg"/>\n'
        )

        # On conserve également les anciennes méthodes
        rss += (
            '  <media:content url="'
            + html.escape(image, quote=True)
            + '" medium="image" type="image/jpeg"/>\n'
        )

        rss += (
            '  <media:thumbnail url="'
            + html.escape(image, quote=True)
            + '"/>\n'
        )

        rss += """
  <content:encoded><![CDATA[
"""

        rss += (
            "<p>"
            + description
            + "</p>"
        )

        rss += (
            '<p><img src="'
            + html.escape(image, quote=True)
            + '" alt="'
            + html.escape(title, quote=True)
            + '" /></p>'
        )

        rss += """
  ]]></content:encoded>
"""

    rss += """
</item>
"""


rss += """
</channel>
</rss>
"""


# --------------------------------------------------
# Écriture du fichier
# --------------------------------------------------

with open(
    "rss.xml",
    "w",
    encoding="utf-8"
) as f:

    f.write(rss)


# --------------------------------------------------
# Informations dans GitHub Actions
# --------------------------------------------------

print(
    "RSS généré avec",
    len(posts),
    "articles."
)

for post in posts:

    image = get_image(post)

    if image:
        print(
            "IMAGE + ENCLOSURE :",
            post["title"]["rendered"]
        )
        print(
            "  ->",
            image
        )

    else:
        print(
            "PAS D'IMAGE :",
            post["title"]["rendered"]
        )

print("Fichier rss.xml créé.")
