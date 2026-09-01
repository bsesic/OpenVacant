from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return [
            "pages:home",
            "reports:map",
            "reports:create",
            "pages:about",
            "pages:faq",
            "pages:contact",
            "pages:imprint",
            "pages:privacy",
            "pages:terms",
            "billing:pricing",
        ]

    def location(self, item):
        return reverse(item)
