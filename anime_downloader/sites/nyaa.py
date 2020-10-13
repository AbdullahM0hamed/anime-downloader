import re
import logging

from anime_downloader.sites.anime import Anime, AnimeEpisode, SearchResult
from anime_downloader.sites import helpers
from anime_downloader.config import Config

logger = logging.getLogger(__name__)


class Nyaa(Anime, sitename='nyaa'):
    """
    Site: https://nyaa.si

    Config
    ~~~~~~
    filter: Choose filter method in search. One of ['No filter', 'No remakes', 'Trusted Only'] - ignored if episodic is set to 'True'
    category: Choose categories to search. One of ['Anime Music Video', 'English-translated', 'Non-English-translated'] - ignored if episodic is set to 'True'
    episodic: one of ['True', 'False'] - used to determine whether nyaa should be scraped as-is, or whether attempts should be made to find single-ep links, order them by ep, snd download them as you would from other providers
    """

    sitename = 'nyaa'
    url = f'https://{sitename}.si'

    # Something like: [Erai-raws] Boruto Next Generations 38 [720p][Multiple Subs].mkv
    # Becomes something like ('[Erai-raws] Boruto Next Generations 38 [720p][Multiple Subs].mkv', '[Erai-raws] Boruto Next Generations', '78')
    title_regex = "((\[.*?\]\s+?.*)\s-\s+?(\d+).*\[.*)"
    matches = []

    @classmethod
    def search_episodic(cls, query, scrape_eps=False):
        # Specifying an episode drastically reduces results
        # and boosts the speed of this search method tremendously
        # but for _scrape_episodes_episodic it won't catch all the episodes if we do that
        # And thw query will already be precise and thus much faster
        # than a user search
        query = f"{query} 01" if not scrape_eps else query
        parameters = {"f": 2, "c": "1_0", "q": query}
        soup = helpers.soupify(helpers.get("https://nyaa.si", params=parameters))
        links_and_titles = [(x.get("title"), x.get("href")) for x in soup.select("td[colspan] > a[href][title]:not(.comments)")]

        while soup.select(".next > a"):
            if not soup.select(".next > a")[0].get("href"):
                break

            link = cls.url + soup.select(".next > a")[0].get("href")
            soup = helpers.soupify(helpers.get(link))
            links_and_titles.extend([(x.get("title"), x.get("href")) for x in soup.select("td[colspan] > a[href][title]:not(.comments)")])

        # Used by _scrape_episodes_episodic
        if scrape_eps:
            return links_and_titles

        # '[Erai-raws] Boruto - Naruto Next Generations - 167 [1080p][Multiple Subtitle].mkv' -> ('[Erai-raws] Boruto - Naruto Next Generations - 167 [1080p][Multiple Subtitle].mkv', '[Erai-raws] Boruto - Naruto Next Generations', '167')
        regexed_titles_and_eps = [re.search(cls.title_regex, x[0]).group(1,2,3) for x in links_and_titles if re.search(cls.title_regex, x[0]) is not None]

        final_list = []

        for title_item in regexed_titles_and_eps:
            full_title = title_item[0]
            link = [x for x in links_and_titles if full_title in x][0][1]
            short_title = title_item[1]

            final_list.append((short_title, link, title_item[2]))

        # Convert to dict for de-duplication
        final_dict = dict([(x[0], x[1]) for x in final_list])

        search_results = [
            SearchResult(
                title=x[0],
                url=cls.url + x[1]
            )
            for x in final_dict.items()
        ]

        return search_results

    @classmethod
    def search(cls, query):
        if Config._CONFIG["siteconfig"]["nyaa"]["episodic"]:
            return cls.search_episodic(query)

        filters = {"No filter": 0, "No remakes": 1, "Trusted only": 2}
        categories = {"Anime Music Video": "1_1", "English-translated": "1_2", "Non-English-translated": "1_3"}


        parameters = {
            "f": filters[Config._CONFIG["siteconfig"]["nyaa"]["filter"]], 
            "c": categories[Config._CONFIG["siteconfig"]["nyaa"]["category"]], 
            "q": query, 
            "s": "size", 
            "o": "desc"
        }
        
        search_results = helpers.soupify(helpers.get(f"https://nyaa.si/", params=parameters))

        # Used to match magnet links
        rex = r'(magnet:)+[^"]*'

        search_results = [
            SearchResult(
                title=i.select("a:not(.comments)")[1].get("title"),
                url=i.find_all('a', {'href': re.compile(rex)})[0].get('href'),
                meta={'peers': i.find_all('td', class_='text-center')[3].text + ' peers', 'size':i.find_all('td', class_='text-center')[1].text})

            for i in search_results.select("tr.default, tr.success")
        ]

        return search_results

    def _scrape_episodes_episodic(self):
        soup = helpers.soupify(helpers.get(self.url))
        title = soup.select("h3.panel-title")[0].text.strip()
        regexed_title = re.search(self.title_regex, title).group(2)

        # List of tuples of titles and links
        anime = self.search_episodic(regexed_title, scrape_eps=True)

        cleaned_list = []

        for potential_ep in anime:
            regexed_ep = re.search(self.title_regex, potential_ep[0])

            # Check that the regex isn't empty
            if regexed_ep:
                if regexed_ep.group(2) == regexed_title:
                    cleaned_list.append(potential_ep)

        # This works!
        cleaned_list.sort()

        final_list = []

        for ep in cleaned_list:
            if self.quality in ep[0]:
                final_list.append(ep)

        if not final_list:
            logger.warn(f"No eps of quality: {self.quality} found")

            # Attempt to get all eps with the same quality as the first ep
            first_ep = cleaned_list[0]

            # Finds: [1080p], [720p] etc, and then captures everything in the brackets
            regexed_quality = re.search("\[(\d{3}\d?p)\]", first_ep[0])

            if not regexed_quality:
                logger.warn("Could not discern quality, downloading all links...")
                return cleaned_list

            final_list = [x for x in cleaned_list if regexed_quality.group(1) in x[0]]

        return final_list

    def _scrape_episodes(self):
        if self.config["episodic"]:
            return self._scrape_episodes_episodic()

        # the magnet has all episodes making this redundant
        return [self.url]


class NyaaEpisode(AnimeEpisode, sitename='nyaa'):
    def _get_sources(self):
        if not self.config["episodic"]:
            return [('no_extractor', self.url)]

        url = Nyaa.url + self.url
        soup = helpers.soupify(helpers.get(url))
        magnet_link = soup.select("a:has(i.fa.fa-magnet)")[0].get("href")
        
        return [("no_extractor", magnet_link)]
