import requests


def search_wikipedia(query: str, lang: str = "ru") -> str:
    try:
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "titles": query,
            "redirects": 1,
        }
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            if page.get("extract"):
                return page["extract"][:5000]
        return "По вашему запросу в Википедии ничего не найдено."
    except Exception as exc:
        return f"Ошибка запроса к Википедии: {exc}"
