# encoding: utf8
import re
import scrapy
from scrapy.crawler import CrawlerProcess
import scraperwiki

INDEX_URL = 'http://dialogsocial.gov.ro/categorie/proiecte-de-acte-normative/'

DOC_EXTENSIONS = [
    ".docs", ".doc", ".txt", ".crt", ".xls",
    ".xml", ".pdf", ".docx", ".xlsx",
]

TYPE_RULES = [
    ("lege", "LEGE"),
    ("hotarare de guvern", "HG"),
    ("hotarare a guvernului", "HG"),
    ("ordonanta de guvern", "OG"),
    ("ordonanta de urgenta", "OUG"),
    ("ordin de ministru", "OM"),
    ("ordinul", "OM"),
]

DIACRITICS_RULES = [
    (ur'[șş]', 's'),
    (ur'[ȘŞ]', 'S'),
    (ur'[țţ]', 't'),
    (ur'[ȚŢ]', 'T'),
    (ur'[ăâ]', 'a'),
    (ur'[ĂÂ]', 'A'),
    (ur'[î]', 'i'),
    (ur'[Î]', 'I'),
]


class Publication(scrapy.Item):
    institution = scrapy.Field()
    identifier = scrapy.Field()
    type = scrapy.Field()
    date = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()
    documents = scrapy.Field()
    contact = scrapy.Field()
    feedback_days = scrapy.Field()
    max_feedback_date = scrapy.Field()


def strip_diacritics(text):
    """
    Replace all diacritics in the given text with their regular counterparts.
    :param text: the text to look into
    :return: the text without diacritics
    """
    result = text
    for search_pattern, replacement in DIACRITICS_RULES:
        result = re.sub(search_pattern, replacement, result, re.UNICODE)
    return result


def guess_initiative_type(text, rules):
    """
    Try to identify the type of a law initiative from its description.

    Use a best guess approach. The rules are provided by the caller as a list
    of tuples. Each tuple is composed of a search string and the initiative
    type it matches to.
    :param text: the description of the initiative
    :param rules: the rules of identification expressed as a list of tuples
    :return: the type of initiative if a rule matches; "OTHER" if no rule
    matches
    """
    text = strip_diacritics(text)

    for search_string, initiative_type in rules:
        if search_string in text:
            return initiative_type
    else:
        return "OTHER"


def text_from(sel):
    return sel.xpath('string(.)').extract_first().strip()


class DialogSpider(scrapy.Spider):

    name = 'dialog'
    start_urls = [INDEX_URL]

    def parse(self, response):
        for article in response.css('#content article.post'):
            href = article.css('.entry-title a::attr(href)').extract_first()
            yield scrapy.Request(response.urljoin(href), self.parse_article)

    def parse_article(self, response):
        title = text_from(response.css('h1'))
        publication_type = guess_initiative_type(title, TYPE_RULES)

        article = response.css('#content article.post')[0]

        id_value = article.css('::attr(id)').extract_first()
        identifier = re.match(r'post-(\d+)', id_value).group(1)

        date = (
            article.css('time.entry-date::attr(datetime)')
            .extract_first()[:10]
        )

        # remove <div class="fb-comments"> and everything below
        to_remove = article.css('.fb-comments')[0].root
        while to_remove is not None:
            next_to_remove = to_remove.getnext()
            to_remove.getparent().remove(to_remove)
            to_remove = next_to_remove

        documents = [
            {
                'type': href.split('.')[-1],
                'url': href,
            }
            for href in article.css('a::attr(href)').extract()
            if any(href.endswith(ext) for ext in DOC_EXTENSIONS)
        ]

        publication = Publication(
            identifier=identifier,
            title=title,
            institution='dialog',
            description=text_from(article),
            type=publication_type,
            date=date,
            #documents=documents,
        )
        scraperwiki.sqlite.save(unique_keys=['identifier'], data=dict(publication))


process = CrawlerProcess()
process.crawl(DialogSpider)
process.start()
