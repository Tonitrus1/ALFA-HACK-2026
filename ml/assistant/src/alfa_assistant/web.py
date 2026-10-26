import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx
import trafilatura

from .errors import ServiceError


class URLPolicy:
    def __init__(self, domains):
        self.domains = [d.lower().rstrip(".") for d in domains]

    def check(self, url):
        try:
            p = urlsplit(url)
            host = (p.hostname or "").lower().rstrip(".").encode("idna").decode()
            if p.scheme not in {"http", "https"} or p.username or p.password or not host:
                raise ValueError()
            if p.port not in {None, 80 if p.scheme == "http" else 443}:
                raise ValueError()
            if not any(host == d or host.endswith("." + d) for d in self.domains):
                raise ValueError()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError()
            return p, host
        except (ValueError, UnicodeError):
            raise ServiceError("UNSAFE_URL", 422) from None

    async def resolve(self, host, port):
        loop = asyncio.get_running_loop()
        rows = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = sorted({row[4][0] for row in rows})
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ServiceError("UNSAFE_DNS_ADDRESS", 422)
        return addresses[0]


class SafePageReader:
    """Pin connection to validated IP; preserve Host, TLS SNI and certificate verification.

    No environment proxies and no second DNS lookup, preventing DNS rebinding. Each redirect
    goes through the same domain/DNS checks. Only bounded decompressed content is retained.
    """

    def __init__(self, policy, run_sync):
        self.policy, self.run_sync = policy, run_sync

    async def read(self, url):
        async with asyncio.timeout(10):
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                for redirect in range(4):
                    p, host = self.policy.check(url)
                    address = await self.policy.resolve(
                        host, p.port or (443 if p.scheme == "https" else 80)
                    )
                    ip_host = f"[{address}]" if ":" in address else address
                    pinned_url = urlunsplit((p.scheme, ip_host, p.path or "/", p.query, ""))
                    # HTTPCore uses this extension for start_tls(server_hostname=...).
                    async with client.stream(
                        "GET",
                        pinned_url,
                        headers={
                            "Host": host,
                            "User-Agent": "AlfaHackAssistant/0.1",
                            "Accept": "text/html,text/plain",
                            "Accept-Encoding": "identity",
                        },
                        extensions={"sni_hostname": host.encode("ascii")},
                    ) as response:
                        if response.is_redirect:
                            if redirect == 3 or "location" not in response.headers:
                                raise ServiceError("TOO_MANY_REDIRECTS", 422)
                            url = urljoin(url, response.headers["location"])
                            continue
                        response.raise_for_status()
                        if (
                            response.headers.get("content-encoding", "identity").lower()
                            != "identity"
                        ):
                            raise ServiceError("WEB_CONTENT_ENCODING_UNSUPPORTED", 415)
                        mime = response.headers.get("content-type", "").split(";")[0].lower()
                        if mime not in {"text/html", "text/plain", "application/xhtml+xml"}:
                            raise ServiceError("WEB_CONTENT_TYPE_UNSUPPORTED", 415)
                        if int(response.headers.get("content-length", "0")) > 5 * 1024 * 1024:
                            raise ServiceError("WEB_PAGE_TOO_LARGE", 413)
                        body = bytearray()
                        async for part in response.aiter_bytes(16384):
                            body.extend(part)
                            if len(body) > 5 * 1024 * 1024:
                                raise ServiceError("WEB_PAGE_TOO_LARGE", 413)
                        text = body.decode(response.encoding or "utf-8", errors="replace")
                        if mime != "text/plain":
                            text = await self.run_sync(
                                lambda text=text: trafilatura.extract(
                                    text, include_comments=False, include_tables=True
                                )
                                or ""
                            )
                        if not text.strip():
                            raise ServiceError("WEB_EMPTY_TEXT", 422)
                        return {"url": url, "text": text}
        raise ServiceError("WEB_FETCH_FAILED", 502)


class SearxngSearch:
    def __init__(self, base_url, policy):
        self.base_url, self.policy = base_url.rstrip("/"), policy

    async def search(self, query):
        sites = " OR ".join("site:" + d for d in self.policy.domains)
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(
                self.base_url + "/search",
                params={
                    "q": f"{query} ({sites})",
                    "format": "json",
                    "language": "ru",
                    "engines": "duckduckgo,bing",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("results") and payload.get("unresponsive_engines"):
                raise ServiceError("WEB_ENGINES_UNAVAILABLE", 503)
            results = []
            seen = set()
            for item in payload.get("results", []):
                url = item.get("url", "")
                try:
                    self.policy.check(url)
                except ServiceError:
                    continue
                if url in seen:
                    continue
                seen.add(url)
                results.append(
                    {
                        "result_id": str(uuid4()),
                        "title": item.get("title", "")[:300],
                        "url": url,
                        "snippet": item.get("content", "")[:1000],
                        "is_read": False,
                    }
                )
                if len(results) == 5:
                    break
            return results
