import scrapy
import csv
import json

class MalSpider(scrapy.Spider):
    """
    This spider scrapes anime list data for a given list of usernames from MyAnimeList.net.
    It reads usernames from 'user.csv' and scrapes their 'completed' anime list
    by parsing a JSON object embedded in the page's HTML.
    """
    name = 'malspider'
    allowed_domains = ['myanimelist.net']

    # Add a User-Agent to avoid being blocked.
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    async def start(self):
        """
        Reads usernames from a CSV file and generates initial requests.
        """
        try:
            with open('D:/MAL/user.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    username = row.get('USERNAME')
                    if username:
                        url = f"https://myanimelist.net/animelist/{username.strip()}?status=2"
                        yield scrapy.Request(
                            url=url,
                            callback=self.parse,
                            meta={'username': username}
                        )
                    else:
                        self.logger.warning("Found a row with no USERNAME.")
        except FileNotFoundError:
            self.logger.error("'user.csv' not found at 'D:/MAL/user.csv'. Please check the path.")

    def parse(self, response):
        """
        Parses the anime list page for each user.
        Extracts anime title and score from a JSON blob embedded in the HTML.
        """
        username = response.meta['username']
        self.logger.info(f"Scraping animelist for user: {username}")

        # FINAL FIX v3: The data is in a 'data-items' attribute on the main table itself.
        # This selector correctly targets that attribute.
        json_data_string = response.css('table.list-table::attr(data-items)').get()

        if not json_data_string:
            self.logger.warning(f"No data found for user: {username}. Their list might be private, empty, or the page structure has changed.")
            return
        
        try:
            # Parse the JSON string into a Python list of dictionaries
            anime_list = json.loads(json_data_string)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON for user: {username}")
            return

        if not anime_list:
            self.logger.warning(f"Anime list for user {username} is empty after parsing JSON.")
            return

        # Iterate through each anime in the parsed list
        for anime in anime_list:
            # The score is 0 if not rated by the user
            score = anime.get('score')
            
            yield {
                'username': username,
                'anime_name': anime.get('anime_title'),
                'score': score if score != 0 else None
            }

