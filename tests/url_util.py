from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit


def url(base_url, path, query_dict=None):
    """Given a base url, update with a specified path and query string.

    Args:
        base_url(str): url to work from
        path(str): path urljoin with base_url
        query_dict(dict): query parameter values to replace in base_url. this
                replaces all query parameters wholesale

    Returns the newly updated url.
    """
    url = urljoin(base_url, path)
    scheme, netloc, path, query, fragment = urlsplit(url)

    if query_dict:
        query = urlencode(query_dict)

    return urlunsplit((scheme, netloc, path, query, fragment))
