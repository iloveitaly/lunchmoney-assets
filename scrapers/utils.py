import hashlib
import json
import re


def parse_currency(value_str: str | None) -> float:
    """Parse a currency string (e.g. '$1,234.56') into a float."""
    if not value_str:
        return 0.0

    return float(re.sub(r"[^0-9.]", "", value_str))


def extract_kbb_price_advisor_svg_url(raw_html: str) -> str | None:
    """Extract the KBB price advisor SVG URL from raw HTML."""
    if not raw_html:
        return None

    match = re.search(
        r'"href"\s*:\s*"(upa\.syndication\.kbb\.com/usedcar/[^"]+)"',
        raw_html,
    )

    if not match:
        match = re.search(r'upa\.syndication\.kbb\.com/usedcar/[^"\s]+', raw_html)

        if not match:
            return None

    href = match.group(1) if match.lastindex else match.group(0)
    href = href.replace("\\u0026", "&").replace("&", "&")

    if href.startswith("http"):
        return href

    return f"https://{href}"


def parse_private_party_value_from_kbb_svg(svg: str) -> float | None:
    """Extract Private Party Value from KBB's Price Advisor SVG."""
    if not svg:
        return None

    match = re.search(
        r"Private Party Value</text>\s*<text[^>]*>\s*(\$[0-9,]+)",
        svg,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return parse_currency(match.group(1))


def replace_query_param(url: str, key: str, value: str) -> str:
    """Replace or append a query parameter in a URL."""
    if not url or not key:
        return url

    pattern = rf"([?&]){re.escape(key)}=[^&]*"

    if re.search(pattern, url):
        return re.sub(pattern, rf"\g<1>{key}={value}", url)

    separator = "&" if "?" in url else "?"

    return f"{url}{separator}{key}={value}"


def url_hash(url: str) -> str:
    """Generate a short hash for a URL to use in debug filenames."""
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def extract_property_price_from_html(raw_html: str, url: str = "") -> float | None:
    """Extract property price from HTML using platform-specific selectors and fallbacks."""
    if not raw_html:
        return None

    # 1. Zillow Zestimate
    if match := re.search(r'"zestimate"\s*:\s*([0-9]+)', raw_html):
        return float(match.group(1))

    # 2. Redfin hero price / Redfin Estimate
    redfin_patterns = [
        r'data-rf-test-id=[\'"]abp-price[\'"][^>]*>.*?class=[\'"][^\'"]*price[^\'"]*[\'"][^>]*>.*?\$([0-9,]+)',
        r'RedfinEstimateValueHeader.*?smallerFont[\'"][^>]*>\$([0-9,]+)',
        r'estimate the home(?:\x27|\\u0027|\x27)s value is \$([0-9,]+)',
        r'class=[\'"]statsValue price[\'"][^>]*>.*?\$([0-9,]+)',
    ]
    for pattern in redfin_patterns:
        if match := re.search(pattern, raw_html, re.DOTALL | re.IGNORECASE):
            return parse_currency(match.group(1))

    # 3. OpenGraph / Twitter description meta tags (e.g. Zillow: "valued at $561,800")
    meta_patterns = [
        r'<meta[^>]*property=[\'"]og:description[\'"][^>]*content=[\'"]([^\'"]+)[\'"]',
        r'<meta[^>]*name=[\'"]description[\'"][^>]*content=[\'"]([^\'"]+)[\'"]',
        r'<meta[^>]*name=[\'"]twitter:description[\'"][^>]*content=[\'"]([^\'"]+)[\'"]',
    ]
    for pattern in meta_patterns:
        if match := re.search(pattern, raw_html, re.IGNORECASE):
            text = match.group(1)
            # Find dollar amount with thousands separator
            if price_match := re.search(r"\$([0-9]{1,3}(?:,[0-9]{3})+)", text):
                return parse_currency(price_match.group(1))

    # 4. JSON-LD schemas
    for script_match in re.finditer(
        r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>',
        raw_html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(script_match.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if "offers" in item and isinstance(item["offers"], dict):
                    if price := item["offers"].get("price"):
                        return parse_currency(str(price))
                if price := item.get("price"):
                    return parse_currency(str(price))
        except Exception:
            continue

    return None


# Backward compatibility aliases with leading underscore
_parse_currency = parse_currency
_extract_kbb_price_advisor_svg_url = extract_kbb_price_advisor_svg_url
_parse_private_party_value_from_kbb_svg = parse_private_party_value_from_kbb_svg
_replace_query_param = replace_query_param
_url_hash = url_hash
_extract_property_price_from_html = extract_property_price_from_html
