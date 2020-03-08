from urllib.parse import urlparse, urlunparse


def build_repo_url(url: str, username, password):
    """add credentials to url if url is http"""
    if url.startswith("http") and username and password:
        u = urlparse(url)
        netloc = str(u.netloc)
        parts = netloc.split('@')
        if len(parts) == 1:
            netloc = '{}:{}@{}'.format(username, password, parts[0])
        else:
            netloc = '{}:{}@{}'.format(username, password, parts[1])
        return str(urlunparse((u.scheme, netloc, u.path, u.params, u.query, u.fragment)))
    else:
        return url
