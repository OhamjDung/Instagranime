import scrapy
import csv
import os

class AnimeCrawl(scrapy.Spider):
    name = "animecrawl"
    allowed_domains = ["myanimelist.net"]
    REVIEW_PAGE_LIMIT = 5

    def start_requests(self):
        filename = 'D:/MAL/anime.csv'
        try:
            with open(filename, mode='r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    anime_id = row['ID']
                    anime_title = row['TITLE']
                    anime_url = f'https://myanimelist.net/anime/{anime_id}'
                    yield scrapy.Request(
                        url=anime_url,
                        callback=self.parse_main_page,
                        meta={'anime_id': anime_id, 'anime_title': anime_title}
                    )
        except FileNotFoundError:
            self.log(f"Error: The file '{filename}' was not found.")

    def parse_main_page(self, response):
        anime_id = response.meta['anime_id']
        anime_title = response.meta['anime_title']
        self.log(f"Scraping main page for: {anime_title} (ID: {anime_id})")

        # --- THE FIX: Define all possible fields, leaving review fields blank ---
        yield {
            'type': 'anime_details',
            'anime_id': anime_id,
            'anime_title': anime_title,
            'studio': response.xpath("//span[normalize-space()='Studios:']/following-sibling::a/text()").get(),
            'promo_video_url': response.xpath("//div[@class='video-promotion']/a/@href").get(),
            # Add placeholders for review fields
            'username': None,
            'date': None,
            'rating_score': None,
            'review_text': None,
        }

        reviews_url = response.xpath("//a[contains(text(), 'All reviews')]/@href").get()
        if reviews_url:
            meta_data = response.meta.copy()
            meta_data['review_page_count'] = 1
            yield response.follow(
                reviews_url,
                callback=self.parse_reviews_page,
                meta=meta_data
            )

    def parse_reviews_page(self, response):
        anime_id = response.meta['anime_id']
        anime_title = response.meta['anime_title']
        page_count = response.meta['review_page_count']
        self.log(f"Scraping reviews for: {anime_title} (Review Page: {page_count})")

        review_selectors = response.css('div.review-element')
        for review in review_selectors:
            review_text_parts = review.css('div.text::text').getall()
            full_review_text = "".join(review_text_parts).strip()

            # --- THE FIX: Define all possible fields, leaving detail fields blank ---
            yield {
                'type': 'review',
                'anime_id': anime_id,
                'anime_title': anime_title,
                # Add placeholders for detail fields
                'studio': None,
                'promo_video_url': None,
                # Add the actual review fields
                'username': review.css('.username a::text').get(),
                'date': review.css('.update_at::text').get(),
                'rating_score': review.css('.rating span::text').get(),
                'review_text': full_review_text,
            }

        if page_count < self.REVIEW_PAGE_LIMIT:
            next_page = response.css('div.pagination a.next::attr(href)').get()
            if next_page:
                meta_data = response.meta.copy()
                meta_data['review_page_count'] += 1
                yield response.follow(
                    next_page,
                    callback=self.parse_reviews_page,
                    meta=meta_data
                )