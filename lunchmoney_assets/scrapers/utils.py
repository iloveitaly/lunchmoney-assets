import hashlib
import json
import re

HASH_LENGTH = 12

CURRENCY_STRIP_PATTERN = re.compile(
    r"""
    [^0-9.]  # match any character that is not a digit or decimal point
    """,
    re.VERBOSE,
)

KBB_HREF_PATTERN = re.compile(
    r"""
    "href"                     # json key href
    \s*:\s*                    # colon separator with optional whitespace
    "(upa\.syndication\.kbb\.com/usedcar/[^"]+)"  # upa syndication url target
    """,
    re.VERBOSE,
)

KBB_FALLBACK_PATTERN = re.compile(
    r"""
    upa\.syndication\.kbb\.com/usedcar/[^"\s]+  # upa syndication url target without quotes
    """,
    re.VERBOSE,
)

KBB_ADVISOR_SVG_PATTERN = re.compile(
    r"""
    Private\s+Party\s+Value</text>  # section header in svg
    \s*<text[^>]*>\s*             # opening text tag
    (\$[0-9,]+)                   # dollar amount string
    """,
    re.VERBOSE | re.IGNORECASE,
)

ZESTIMATE_PATTERN = re.compile(
    r"""
    "zestimate"  # json property key
    \s*:\s*      # separator
    ([0-9]+)     # numeric valuation
    """,
    re.VERBOSE,
)

DOLLAR_THOUSANDS_PATTERN = re.compile(
    r"""
    \$                          # literal dollar sign
    ([0-9]{1,3}(?:,[0-9]{3})+)  # one to three digits followed by comma-separated triplets
    """,
    re.VERBOSE,
)

JSON_LD_SCRIPT_PATTERN = re.compile(
    r"""
    <script[^>]*type=['"]application/ld\+json['"][^>]*>  # ld+json script tag opening
    (.*?)                                                # json payload content
    </script>                                            # script tag closing
    """,
    re.VERBOSE | re.DOTALL | re.IGNORECASE,
)

REDFIN_PATTERNS = [
    re.compile(
        r"""
        data-rf-test-id=['"]abp-price['"][^>]*>
        .*?class=['"][^'"]*price[^'"]*['"][^>]*>
        .*?\$([0-9,]+)
        """,
        re.VERBOSE | re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r"""
        RedfinEstimateValueHeader.*?smallerFont['"][^>]*>\$([0-9,]+)
        """,
        re.VERBOSE | re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r"""
        estimate\sthe\shome(?:\x27|\\u0027|\x27)s\svalue\sis\s\$([0-9,]+)
        """,
        re.VERBOSE | re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r"""
        class=['"]statsValue\sprice['"][^>]*>.*?\$([0-9,]+)
        """,
        re.VERBOSE | re.DOTALL | re.IGNORECASE,
    ),
]

META_PATTERNS = [
    re.compile(
        r"""<meta[^>]*property=['"]og:description['"][^>]*content=['"]([^'"]+)['"]""",
        re.VERBOSE | re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]*name=['"]description['"][^>]*content=['"]([^'"]+)['"]""",
        re.VERBOSE | re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]*name=['"]twitter:description['"][^>]*content=['"]([^'"]+)['"]""",
        re.VERBOSE | re.IGNORECASE,
    ),
]


def parse_currency(value_str: str | None) -> float:
    "Parse a currency string into a float"

    if not value_str:
        return 0.0

    cleaned = CURRENCY_STRIP_PATTERN.sub("", value_str)
    return float(cleaned)


def extract_kbb_price_advisor_svg_url(raw_html: str) -> str | None:
    "Extract the KBB price advisor SVG URL from raw HTML"

    if not raw_html:
        return None

    match = KBB_HREF_PATTERN.search(raw_html)
    if not match:
        match = KBB_FALLBACK_PATTERN.search(raw_html)
        if not match:
            return None

    href = match.group(1) if match.lastindex else match.group(0)
    href = href.replace("\\u0026", "&")

    if href.startswith("http"):
        return href

    return f"https://{href}"


def parse_private_party_value_from_kbb_svg(svg: str) -> float | None:
    "Extract Private Party Value from KBB Price Advisor SVG"

    if not svg:
        return None

    match = KBB_ADVISOR_SVG_PATTERN.search(svg)
    if not match:
        return None

    return parse_currency(match.group(1))


def replace_query_param(url: str, key: str, value: str) -> str:
    "Replace or append a query parameter in a URL"

    if not url or not key:
        return url

    pattern = re.compile(
        rf"""
        ([?&])           # query string start or parameter delimiter
        {re.escape(key)} # escaped parameter key
        =[^&]*           # value up to next delimiter
        """,
        re.VERBOSE,
    )

    if pattern.search(url):
        return pattern.sub(rf"\g<1>{key}={value}", url)

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={value}"


def url_hash(url: str) -> str:
    "Generate a short hash for a URL to use in debug filenames"

    return hashlib.sha1(url.encode()).hexdigest()[:HASH_LENGTH]


def extract_property_price_from_html(raw_html: str, url: str = "") -> float | None:
    "Extract property price from HTML using platform-specific selectors and fallbacks"

    if not raw_html:
        return None

    # 1. zillow zestimate
    if match := ZESTIMATE_PATTERN.search(raw_html):
        return float(match.group(1))

    # 2. redfin hero price / redfin estimate
    for pattern in REDFIN_PATTERNS:
        if match := pattern.search(raw_html):
            return parse_currency(match.group(1))

    # 3. opengraph / twitter description meta tags
    for meta_pattern in META_PATTERNS:
        if match := meta_pattern.search(raw_html):
            text = match.group(1)
            # find dollar amount with thousands separator
            if price_match := DOLLAR_THOUSANDS_PATTERN.search(text):
                return parse_currency(price_match.group(1))

    # 4. json-ld schemas
    for script_match in JSON_LD_SCRIPT_PATTERN.finditer(raw_html):
        try:
            data = json.loads(script_match.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue

                offers = item.get("offers")
                if isinstance(offers, dict) and (price := offers.get("price")):
                    return parse_currency(str(price))

                if price := item.get("price"):
                    return parse_currency(str(price))
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            continue

    return None
