from protego import Protego

from assistant.scrape.discover import (
    absolute,
    allowed,
    internal,
    locations,
    sitemap_urls,
)

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
  <url><loc>https://www.nawaloka.com/</loc></url>
  <url><loc>  https://www.nawaloka.com/heart-centre  </loc></url>
  <url><loc></loc></url>
</urlset>
"""


def test_locations_reads_and_trims_every_entry():
    assert locations(SITEMAP) == [
        "https://www.nawaloka.com/",
        "https://www.nawaloka.com/heart-centre",
    ]


def test_sitemap_urls_uses_the_fetcher_it_is_given():
    assert sitemap_urls(lambda _: SITEMAP) == [
        "https://www.nawaloka.com/",
        "https://www.nawaloka.com/heart-centre",
    ]


def test_a_broad_allow_does_not_mask_a_later_disallow():
    """The live robots.txt opens with `Allow: /` and disallows paths below it.

    A first-match parser reads that as permission to fetch everything.
    """
    parser = Protego.parse("User-agent: *\nAllow: /\nDisallow: /ajax/\n")

    assert allowed(parser, "https://www.nawaloka.com/heart-centre")
    assert not allowed(parser, "https://www.nawaloka.com/ajax/search")


def test_wildcard_rules_are_honoured():
    parser = Protego.parse("User-agent: *\nAllow: /\nDisallow: /*?*\n")

    assert not allowed(parser, "https://www.nawaloka.com/search?q=heart")


def test_links_are_resolved_against_their_page_without_fragments():
    page = "https://www.nawaloka.com/aboutus"

    assert absolute("/laboratory", page) == "https://www.nawaloka.com/laboratory"
    assert absolute("/laboratory#tests", page) == "https://www.nawaloka.com/laboratory"
    assert absolute("consultants", page) == "https://www.nawaloka.com/consultants"


def test_only_pages_on_the_hospital_site_are_followed():
    assert internal("https://www.nawaloka.com/dialysis")
    assert not internal("https://www.facebook.com/NawalokaHospitalColombo")
    assert not internal("mailto:nawaloka@slt.lk")
    assert not internal("https://nhref.nawaloka.com/newsletter")
