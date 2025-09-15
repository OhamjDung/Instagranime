import scrapy

class NewspiderSpider(scrapy.Spider):
    name = "newspider"
    allowed_domains = ["myanimelist.net"]
    
    # 1. Initialize a set to store the usernames we have already scraped.
    seen_usernames = set()

    def start_requests(self):
        base_url = "https://myanimelist.net/forum/?board=15"
        yield scrapy.Request(url=base_url, callback=self.parse)
        for i in range(1, 297):
            next_page_url = base_url + "&show=" + str(i * 50)
            yield scrapy.Request(url=next_page_url, callback=self.parse)

    def parse(self, response):
        for user in range(1, 51):
            xpathlink = '//*[@id="topicRow' + str(user) + '"]/td[4]/a[1]/text()'
            username = response.xpath(xpathlink).get()
            
            # 2. Check if we have a username AND if it's not already in our set.
            if username and username not in self.seen_usernames:
                
                # 3. If it's new, add it to the set for future checks.
                self.seen_usernames.add(username)
                
                # 4. Yield the unique item.
                yield {
                    'username' : username
                }