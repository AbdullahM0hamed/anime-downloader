
from anime_downloader.sites.anime import Anime, AnimeEpisode, SearchResult
from anime_downloader.sites import helpers
from urllib.parse import urlparse

import logging
import re

logger = logging.getLogger(__name__)


class MeusAnime(Anime, sitename='meusanime'):
    sitename='meusanime'

    @classmethod
    def search(cls, query):
        soup=helpers.soupify(helpers.get("https://meusanimes.com", params={"s": query}))

        search_results=[
            SearchResult(
                title=x.get("title"),
                url=x.get("href"),

                # Dublado == dub, legendado == sub
                meta={"type": "legendado" if "dublado" not in x.get("href") else "dublado"}
            )
            for x in soup.select("div.ultAnisContainerItem > a")
        ]

        return search_results

    def _scrape_episodes(self):
        soup=helpers.soupify(helpers.get(self.url))

        first_loop=True
        eps=[x.get("href") for x in soup.select("div.ultEpsContainerItem > a")]

        # Loop through all the pages to get all eps
        while soup.select("a.page-numbers:last-child")[0].get("href") != soup.select("a.page-numbers.current")[0].get("href"):
            soup=helpers.soupify(helpers.get([x for x in soup.select("a.page-numbers") if x.text == "›"][0].get("href")))

            eps.extend([
                x.get("href") for x in soup.select("div.ultEpsContainerItem > a")
            ])

        return eps

    def _scrape_metadata(self):
        soup=helpers.soupify(helpers.get(self.url))
        self.title=soup.select("div.animeFirstContainer > h1")[0].text


class MeusEpisode(AnimeEpisode, sitename='meusanime'):
    def _get_sources(self):
        soup=helpers.soupify(helpers.get(self.url, referer="https://meusanimes.com/"))
        link1=soup.select("div.playerBox > a")[-1].get("href")

        if link1.startswith("//"):
            link1="http:" + link1

        soup=helpers.soupify(helpers.get(link1))

        # Gotta bounce from place to place
        while soup.form:
            post_data=dict([(x.get("name"), x.get("value")) for x in soup.select("form > input")])
            link2=soup.form.get("action")

            if link2.startswith("//"):
                link2="https:" + link2

            method=helpers.post if soup.form.get("method") == "post" else helpers.get
            parsed=urlparse(link1)
            referer="://".join((parsed.scheme, parsed.netloc)) + '/'
            resp=method(link2, data=post_data, referer=referer)
            soup=helpers.soupify(resp)

            # For next iteration
            link1=link2

        while soup.find().name == "script":
            logger.info(soup)
            link=re.search("window.*href.*[\"'](.*?)['\"]", resp.text).group(1)

            if link.startswith("//"):
                link="http:" + link

            parsed=urlparse(link1)
            referer="://".join((parsed.scheme, parsed.netloc)) + '/'
            resp=helpers.get(link, referer=link1)
            soup=helpers.soupify(resp)
            link1=link

        final_link="https:" + soup.iframe.get("src")

        return [("no_extractor", final_link)]
