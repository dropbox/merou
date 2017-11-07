from bs4 import BeautifulSoup


class Page(object):
    def __init__(self, body):
        self.soup = BeautifulSoup(body, "html.parser")

    def has_element(self, name=None, text=None):
        def matcher(tag):
            if name and tag.name != name:
                return False

            if text and text not in tag.text:
                return False

            return True

        return self.soup.find(matcher)

    def has_text(self, text):
        return self.has_element(text=text)

    def has_link(self, text, href):
        def matcher(tag):
            return all([
                tag.name == "a",
                tag.get("href") == href,
                text in tag.text
            ])

        return self.soup.find(matcher)
