import re
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from urllib.parse import urljoin


# ============================================================
# CONFIGURATION
# ============================================================

WORDPRESS_API = "https://col58-genevoix.sd.ac-dijon.fr/wp-json/wp/v2/posts"

SITE_URL = "https://col58-genevoix.sd-ac-dijon.fr"

RSS_TITLE = "Actualités du collège Maurice Genevoix"
RSS_DESCRIPTION = "Les dernières actualités du collège Maurice Genevoix de Decize."

OUTPUT_FILE = "rss.xml"

# Nombre maximum d'articles récupérés
PER_PAGE = 100

# Namespace Media RSS
MEDIA_NS = "http://search.yahoo.com/mrss/"

# Namespace Content
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


# ============================================================
# NAMESPACES XML
# ============================================================

ET.register_namespace("media", MEDIA_NS)
ET.register_namespace("content", CONTENT_NS)


# ============================================================
# SESSION HTTP
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Flux RSS Skolengo - College Maurice Genevoix"
})


# ============================================================
# OUTILS
# ============================================================

def normalize_url(url):
    """
    Transforme les URL HTTP en HTTPS et rend les URL absolues.
    """
    if not url:
        return None

    url = html.unescape(url).strip()

    if url.startswith("//"):
        url = "https:" + url

    elif url.startswith("/"):
        url = urljoin(SITE_URL, url)

    elif url.startswith("http://"):
        url = "https://" + url[7:]

    return url


def guess_mime_type(url):
    """
    Détermine le type MIME d'une image à partir de son extension.
    """
    if not url:
        return "image/jpeg"

    clean_url = url.lower().split("?")[0]

    if clean_url.endswith(".png"):
        return "image/png"

    if clean_url.endswith(".gif"):
        return "image/gif"

    if clean_url.endswith(".webp"):
        return "image/webp"

    if clean_url.endswith(".svg"):
        return "image/svg+xml"

    if clean_url.endswith(".avif"):
        return "image/avif"

    return "image/jpeg"


def clean_html(text):
    """
    Transforme un contenu HTML en texte simple.
    """
    if not text:
        return ""

    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text,
                  flags=re.IGNORECASE | re.DOTALL)

    text = re.sub(r"<style\b[^>]*>.*?</style>", "", text,
                  flags=re.IGNORECASE | re.DOTALL)

    text = re.sub(r"<[^>]+>", " ", text)

    text = html.unescape(text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def truncate(text, max_length=500):
    """
    Coupe proprement une description.
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length].rsplit(" ", 1)[0] + "…"


def extract_image_from_html(content):
    """
    Cherche la première image dans le contenu WordPress.

    Priorité :
    1. src
    2. data-src
    3. data-lazy-src
    4. srcset
    """

    if not content:
        return None

    # --------------------------------------------------------
    # src
    # --------------------------------------------------------

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        return normalize_url(match.group(1))

    # --------------------------------------------------------
    # data-src
    # --------------------------------------------------------

    match = re.search(
        r'<img[^>]+data-src=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        return normalize_url(match.group(1))

    # --------------------------------------------------------
    # data-lazy-src
    # --------------------------------------------------------

    match = re.search(
        r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        return normalize_url(match.group(1))

    # --------------------------------------------------------
    # srcset
    # --------------------------------------------------------

    match = re.search(
        r'<img[^>]+srcset=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        srcset = match.group(1)

        first_image = srcset.split(",")[0].strip()

        if first_image:
            url = first_image.split()[0]
            return normalize_url(url)

    return None


def get_featured_image(post):
    """
    Cherche l'image mise en avant via l'API REST WordPress.
    """

    embedded = post.get("_embedded", {})

    media_items = embedded.get("wp:featuredmedia", [])

    if media_items:

        media = media_items[0]

        source_url = media.get("source_url")

        if source_url:
            return normalize_url(source_url)

    return None


def get_post_image(post):
    """
    Cherche l'image de l'article.

    Priorité :
    1. image mise en avant WordPress
    2. première image du contenu
    """

    image = get_featured_image(post)

    if image:
        return image

    content = post.get("content", {}).get("rendered", "")

    return extract_image_from_html(content)


def parse_date(date_string):
    """
    Convertit la date WordPress en datetime UTC.
    """

    if not date_string:
        return datetime.utcnow()

    try:
        # Exemple :
        # 2026-10-02T18:05:02
        dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))

        # Si WordPress ne fournit pas de fuseau,
        # on considère la date comme UTC.
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except Exception:
        return datetime.utcnow()


# ============================================================
# RÉCUPÉRATION DES ARTICLES WORDPRESS
# ============================================================

params = {
    "per_page": PER_PAGE,
    "page": 1,
    "orderby": "date",
    "order": "desc",
    "_embed": "wp:featuredmedia"
}

print("Récupération des articles WordPress...")

try:

    response = session.get(
        WORDPRESS_API,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    posts = response.json()

except Exception as error:

    print("ERREUR lors de la récupération WordPress :")
    print(error)

    raise


print(f"Articles récupérés : {len(posts)}")


# ============================================================
# CRÉATION DU RSS
# ============================================================

rss = ET.Element(
    "rss",
    {
        "version": "2.0",
        "xmlns:media": MEDIA_NS,
        "xmlns:content": CONTENT_NS
    }
)

channel = ET.SubElement(rss, "channel")


# ------------------------------------------------------------
# INFORMATIONS DU FLUX
# ------------------------------------------------------------

ET.SubElement(
    channel,
    "title"
).text = RSS_TITLE

ET.SubElement(
    channel,
    "link"
).text = SITE_URL

ET.SubElement(
    channel,
    "description"
).text = RSS_DESCRIPTION

ET.SubElement(
    channel,
    "language"
).text = "fr-FR"

ET.SubElement(
    channel,
    "generator"
).text = "Flux RSS personnalisé Skolengo"


# ============================================================
# ARTICLES
# ============================================================

images_found = 0

for post in posts:

    title = clean_html(
        post.get("title", {}).get("rendered", "")
    )

    link = normalize_url(
        post.get("link", "")
    )

    post_content = post.get(
        "content", {}
    ).get(
        "rendered",
        ""
    )

    description = truncate(
        clean_html(post_content),
        500
    )

    date_string = post.get("date_gmt") or post.get("date")

    publication_date = parse_date(date_string)

    image_url = get_post_image(post)

    # --------------------------------------------------------
    # ITEM
    # --------------------------------------------------------

    item = ET.SubElement(channel, "item")

    ET.SubElement(
        item,
        "title"
    ).text = title

    ET.SubElement(
        item,
        "link"
    ).text = link

    guid = ET.SubElement(
        item,
        "guid",
        {"isPermaLink": "true"}
    )

    guid.text = link

    pub_date = ET.SubElement(
        item,
        "pubDate"
    )

    pub_date.text = format_datetime(publication_date)

    ET.SubElement(
        item,
        "description"
    ).text = description

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if image_url:

        images_found += 1

        mime_type = guess_mime_type(image_url)

        print(
            f"IMAGE : {title} -> {image_url}"
        )

        # Media RSS
        media_content = ET.SubElement(
            item,
            f"{{{MEDIA_NS}}}content",
            {
                "url": image_url,
                "medium": "image",
                "type": mime_type
            }
        )

        # Media RSS thumbnail
        ET.SubElement(
            item,
            f"{{{MEDIA_NS}}}thumbnail",
            {
                "url": image_url
            }
        )

        # ----------------------------------------------------
        # IMAGE ÉGALEMENT DANS content:encoded
        #
        # Cela améliore la compatibilité avec certains lecteurs
        # RSS qui ne prennent pas en charge Media RSS.
        # ----------------------------------------------------

        content_encoded = ET.SubElement(
            item,
            f"{{{CONTENT_NS}}}encoded"
        )

        content_encoded.text = (
            f'<p>{html.escape(description)}</p>'
            f'<p><img src="{html.escape(image_url, quote=True)}" '
            f'alt="{html.escape(title, quote=True)}" /></p>'
        )

    else:

        print(
            f"PAS D'IMAGE : {title}"
        )


# ============================================================
# ÉCRITURE DU FICHIER
# ============================================================

tree = ET.ElementTree(rss)

ET.indent(tree, space="  ")

tree.write(
    OUTPUT_FILE,
    encoding="utf-8",
    xml_declaration=True
)


# ============================================================
# RÉSUMÉ
# ============================================================

print()
print("======================================")
print("GÉNÉRATION DU FLUX TERMINÉE")
print("======================================")
print(f"Articles : {len(posts)}")
print(f"Images trouvées : {images_found}/{len(posts)}")
print(f"Fichier : {OUTPUT_FILE}")
print("======================================")
