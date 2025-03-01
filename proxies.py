import logging
import random
from decouple import config
import requests

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

def get_random_proxy():
  proxies = get_webshare_proxies()

  random_proxy = random.choice(proxies) if proxies else None
  assert random_proxy

  log.info(f"Using proxy: {random_proxy['server']}")
  return random_proxy


def test_proxy(proxy):
  """
  Test if a proxy correctly routes through the US

  Args:
    proxy: Proxy dict with server, username, password

  Raises:
    Exception: If the proxy doesn't route through the US
  """
  try:
    response = requests.get(f"http://ip-api.com/json/{proxy["proxy_address"]}?fields=countryCode,proxy", timeout=10)

    response.raise_for_status()
    data = response.json()

    if data.get("countryCode") != "US":
      log.info(f"Proxy is not routing through US. Country: {data.get('country', 'unknown')}")
      return False

    if data.get("proxy"):
      log.info("Proxy is a known proxy. Skipping.")
      return False

    return True
  except Exception as e:
    log.error(f"Proxy test failed: {str(e)}")
    raise


def get_webshare_proxies():
    token = config("WEBSHARE_TOKEN")
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    proxy_response = requests.get(
        # https://apidocs.webshare.io/proxy-list
        "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct", headers=headers
    )

    proxy_response.raise_for_status()

    proxies = proxy_response.json()["results"]
    us_proxies = [p for p in proxies if p["country_code"] == "US"]

    log.info(f"Found {len(us_proxies)} US proxies")

    # we want proxies that are not known proxies
    discovered_proxies = [
      p
      for p in us_proxies
      if test_proxy(p)
    ]

    log.info(f"Found {len(discovered_proxies)} discovered proxies")


    # TODO authorize the current IP we are on
    # requests.post(
    #     "https://proxy.webshare.io/api/v2/proxy/ipauthorization/",
    #     headers=headers,
    #     json={"ip_address": requests.get("https://ifconfig.me").text.strip()},
    # )

    return [
        {
            "server": f"{p['proxy_address']}:{p['port']}",
            "username": p["username"],
            "password": p["password"],
        }
        for p in discovered_proxies
    ]
