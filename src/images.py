import os
import random
import requests
from typing import Callable


def fetch_unsplash(query: str = "crab") -> bytes | None:
    """Fetch random image from the Unsplash API.

    Needs UNSPLASH_ACCESS_KEY. Returns None without one so the caller's
    fallback chain moves on to another source rather than failing the send.

    Carries weight 0 in config.json while the API key application is
    pending, so its share is routed to loremflickr instead. Give it a
    non-zero weight once the key is in the repo secrets; nothing here
    needs to change.
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return None
    try:
        resp = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": query, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        image_url = resp.json()["urls"]["regular"]
        if image_url:
            return _fetch_image(image_url)
    except (requests.RequestException, KeyError, ValueError):
        pass
    return None


def fetch_loremflickr(query: str = "crab") -> bytes | None:
    """Fetch random keyword-matched image from LoremFlickr."""
    # random= busts the CDN cache; without it a keyword tends to repeat.
    seed = random.randint(1, 10000)
    url = f"https://loremflickr.com/800/600/{query}?random={seed}"
    return _fetch_image(url)


def fetch_picsum() -> bytes | None:
    """Fetch random image from Lorem Picsum."""
    # Add random seed to avoid caching
    seed = random.randint(1, 10000)
    url = f"https://picsum.photos/seed/{seed}/800/600"
    return _fetch_image(url)


def fetch_random_duck() -> bytes | None:
    """Fetch random duck image."""
    try:
        resp = requests.get("https://random-d.uk/api/v2/random", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        image_url = data.get("url")
        if image_url:
            return _fetch_image(image_url)
    except (requests.RequestException, ValueError):
        pass
    return None


def fetch_cataas() -> bytes | None:
    """Fetch random cat image."""
    url = "https://cataas.com/cat"
    return _fetch_image(url)


def fetch_dog_ceo() -> bytes | None:
    """Fetch random dog image."""
    try:
        resp = requests.get(
            "https://dog.ceo/api/breeds/image/random", timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data.get("message")
        if image_url:
            return _fetch_image(image_url)
    except (requests.RequestException, ValueError):
        pass
    return None


def _fetch_image(url: str, max_retries: int = 2) -> bytes | None:
    """Fetch image bytes from URL with retries."""
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type:
                return resp.content
        except requests.RequestException:
            if attempt < max_retries:
                continue
    return None


def get_random_image(
    sources: dict[str, int],
    image_queries: list[str] | None = None,
) -> bytes | None:
    """Get a random image based on weighted source selection.

    Args:
        sources: Dict of source_name -> weight
        image_queries: Keywords for the query-capable sources
            (unsplash, loremflickr)

    Returns:
        Image bytes or None if all sources fail
    """
    if image_queries is None:
        image_queries = ["crab", "abstract", "nature"]

    # Build weighted list
    weighted_sources: list[tuple[str, Callable[[], bytes | None]]] = []
    for source, weight in sources.items():
        if source == "unsplash":
            query = random.choice(image_queries)
            fetcher = lambda q=query: fetch_unsplash(q)
        elif source == "loremflickr":
            query = random.choice(image_queries)
            fetcher = lambda q=query: fetch_loremflickr(q)
        elif source == "picsum":
            fetcher = fetch_picsum
        elif source == "random_duck":
            fetcher = fetch_random_duck
        elif source == "cataas":
            fetcher = fetch_cataas
        elif source == "dog_ceo":
            fetcher = fetch_dog_ceo
        else:
            continue
        for _ in range(weight):
            weighted_sources.append((source, fetcher))

    if not weighted_sources:
        return None

    # Shuffle and try sources until one works
    random.shuffle(weighted_sources)
    tried = set()

    for source_name, fetcher in weighted_sources:
        if source_name in tried:
            continue
        tried.add(source_name)

        print(f"Trying image source: {source_name}")
        image_bytes = fetcher()
        if image_bytes:
            print(f"Got image from {source_name}: {len(image_bytes)} bytes")
            return image_bytes

    print("All image sources failed")
    return None
