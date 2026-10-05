import re
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin


# ============================================================
# CONFIGURATION
# ============================================================

WORDPRESS_API = (
    "https://col58-genevoix.sd.ac-dijon.fr/"
    "wp-json/wp/v2/posts"
)

SITE_URL = "https://col58-genevoix.sd.ac-dijon.fr"

RSS_TITLE = "Actualités du collège Maurice Genevoix"

RSS_DESCRIPTION = (
    "Les dernières actualités du collège Maurice Genevoix de Decize."
)

OUTPUT_FILE = "rss.xml"

PER_PAGE = 100

MEDIA_NS = "http://search.yahoo.com/mrss/"

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


# ============================================================
# NAMESPACES
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

    if not text:
        return ""

    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def truncate(text, max_length=500):

    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length].rsplit(
        " ",
        1
    )[0] + "…"


def extract_image_from_html(content):

    if not content:
        return None

    # src
    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        return normalize_url(
            match.group(1)
        )

    # data-src
    match = re.search(
        r'<img[^>]+data-src=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        return normalize_url(
            match.group(1)
        )

    # data-lazy-src
    match = re.search(
        r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',
        content,
        flags=re.IGNORECASE
    )

    if match:
        return normalize_url(
            match.group(1)
        )

    # srcset
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

    embedded = post.get(
        "_embedded",
        {}
    )

    media_items = embedded.get(
        "wp:featuredmedia",
        []
    )

    if media_items:

        media = media_items[0]

        source_url = media.get(
            "source_url"
        )

        if source_url:

            return normalize_url(
                source_url
            )

    return None


def get_post_image(post):

    # 1. Image à la une
    image = get_featured_image(post)

    if image:
        return image

    # 2. Première image du contenu
    content = post.get(
        "content",
        {}
    ).get(
        "rendered",
        ""
    )

    return extract_image_from_html(
        content
    )


def parse_date(date_string):

    if not date_string:
        return datetime.now(
            timezone.utc
        )

    try:

        dt = datetime.fromisoformat(
            date_string.replace(
                "Z",
                "+00:00"
            )
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:

        return datetime.now(
            timezone.utc
        )


# ============================================================
# WORDPRESS
# ============================================================

print(
    "Récupération des articles WordPress..."
)

params = {
    "per_page": PER_PAGE,
    "page": 1,
    "orderby": "date",
    "order": "desc",
    "status": "publish",
    "_embed": "wp:featuredmedia"
}

response = session.get(
    WORDPRESS_API,
    params=params,
    timeout=30
)

response.raise_for_status()

posts = response.json()

print(
    f"Articles récupérés : {len(posts)}"
)


# ============================================================
# RSS
# ============================================================

rss = ET.Element(
    "rss",
    {
        "version": "2.0"
    }
)

channel = ET.SubElement(
    rss,
    "channel"
)


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
        post.get(
            "title",
            {}
        ).get(
            "rendered",
            ""
        )
    )

    link = normalize_url(
        post.get(
            "link",
            ""
        )
    )

    content = post.get(
        "content",
        {}
    ).get(
        "rendered",
        ""
    )

    description = truncate(
        clean_html(content),
        500
    )

    date_string = (
        post.get("date_gmt")
        or post.get("date")
    )

    publication_date = parse_date(
        date_string
    )

    image_url = get_post_image(
        post
    )

    # --------------------------------------------------------
    # ITEM
    # --------------------------------------------------------

    item = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        item,
        "title"
    ).text = title

    ET.SubElement(
        item,
        "link"
    ).text = link

    ET.SubElement(
        item,
        "guid",
        {
            "isPermaLink": "true"
        }
    ).text = link

    ET.SubElement(
        item,
        "pubDate"
    ).text = format_datetime(
        publication_date
    )

    ET.SubElement(
        item,
        "description"
    ).text = description


    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if image_url:

        images_found += 1

        mime_type = guess_mime_type(
            image_url
        )

        print(
            f"IMAGE : {title} -> {image_url}"
        )

        # Media RSS
        ET.SubElement(
            item,
            f"{{{MEDIA_NS}}}content",
            {
                "url": image_url,
                "medium": "image",
                "type": mime_type
            }
        )

        # Thumbnail
        ET.SubElement(
            item,
            f"{{{MEDIA_NS}}}thumbnail",
            {
                "url": image_url
            }
        )

        # Content RSS
        encoded = ET.SubElement(
            item,
            f"{{{CONTENT_NS}}}encoded"
        )

        encoded.text = (
            "<p>"
            + html.escape(description)
            + "</p>"
            + '<p><img src="'
            + html.escape(
                image_url,
                quote=True
            )
            + '" alt="'
            + html.escape(
                title,
                quote=True
            )
            + '" /></p>'
        )

    else:

        print(
            f"PAS D'IMAGE : {title}"
        )


# ============================================================
# ÉCRITURE
# ============================================================

tree = ET.ElementTree(
    rss
)

ET.indent(
    tree,
    space="  "
)

tree.write(
    OUTPUT_FILE,
    encoding="utf-8",
    xml_declaration=True
)


# ============================================================
# RÉSULTAT
# ============================================================

print()
print(
    "======================================"
)

print(
    "GÉNÉRATION DU FLUX TERMINÉE"
)

print(
    "======================================"
)

print(
    f"Articles : {len(posts)}"
)

print(
    f"Images trouvées : "
    f"{images_found}/{len(posts)}"
)

print(
    f"Fichier : {OUTPUT_FILE}"
)

print(
    "======================================"
)
