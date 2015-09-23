import urllib
import urlparse


def url(base_url, path, query_dict=None):
    """Given a base url, update with a specified path and query string.

    Args:
        base_url(str): url to work from
        path(str): path urljoin with base_url
        query_dict(dict): query parameter values to replace in base_url. this
                replaces all query parameters wholesale

    Returns the newly updated url.
    """
    url = urlparse.urljoin(base_url, path)
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

    if query_dict:
        query = urllib.urlencode(query_dict)

    return urlparse.urlunsplit((scheme, netloc, path, query, fragment))
