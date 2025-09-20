import scrapy
import csv

class TitleSpider(scrapy.Spider):
    # The name of the spider, used to run it from the command line.
    name = 'englishtitleman'
    
    def start_requests(self):
        """
        Reads the input CSV, skips to a specific ID, generates URLs,
        and yields Scrapy Requests.
        """
        # The absolute path to your input CSV file.
        input_csv_path = 'D:/MAL/csv_exports/animes.csv'
        
        # The ID you want to start AFTER.
        start_after_id = '34213'
        
        # A flag to track when we should start scraping.
        found_start_point = False

        try:
            with open(input_csv_path, mode='r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader) # Skip the header row (ID,TITLE,...)
                
                for row in reader:
                    anime_id = row[0]
                    
                    # If the flag is True, it means we have passed our starting ID
                    # and should now process this row and all future rows.
                    if found_start_point:
                        anime_url = f'https://myanimelist.net/anime/{anime_id}'
                        
                        # Yield a request for the anime.
                        yield scrapy.Request(
                            url=anime_url,
                            callback=self.parse,
                            meta={'anime_id': anime_id}
                        )

                    # Check if the current row's ID is our target.
                    # If it is, we set the flag to True so the *next* iteration starts scraping.
                    if anime_id == start_after_id:
                        found_start_point = True

        except FileNotFoundError:
            self.logger.error(f"Input file not found: {input_csv_path}. Please ensure the path is correct.")

    def parse(self, response):
        """
        This method is called for each anime page downloaded.
        It finds the English title and synopsis, and yields the data.
        """
        # Retrieve the anime_id we passed from start_requests
        anime_id = response.meta['anime_id']

        # Use a CSS selector to find the English title element.
        english_title = response.css('p.title-english.title-inherit::text').get()
        
        # --- NEW: Scrape the synopsis ---
        # Select the <p> tag with the itemprop="description" attribute.
        # ::text extracts all text nodes, which are then joined together.
        synopsis_fragments = response.css('p[itemprop="description"]::text').getall()
        synopsis = ''.join(synopsis_fragments).strip() if synopsis_fragments else ''
        
        # Prepare the data to be yielded
        output_data = {
            'animeid': anime_id,
            'englishtitle': '',
            'haveenglishtitle': 'No',
            'synopsis': synopsis
        }

        if english_title:
            # If an English title was found, update the data
            output_data['englishtitle'] = english_title.strip()
            output_data['haveenglishtitle'] = 'Yes'
        
        yield output_data

