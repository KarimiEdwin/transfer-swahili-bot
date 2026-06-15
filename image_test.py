import feedparser

# This is the live BBC Sport RSS feed
RSS_URL = "http://feeds.bbci.co.uk/sport/football/rss.xml"
feed = feedparser.parse(RSS_URL)

# Get the very first (latest) article
article = feed.entries[0]
print(f"📰 Headline: {article.title}\n")

print("🔍 Searching for the hidden image link...")

# BBC usually hides the image in one of these three places
if hasattr(article, 'media_content'):
    image_url = article.media_content[0]['url']
    print(f"✅ Found image (media_content): {image_url}")
    
elif hasattr(article, 'media_thumbnail'):
    image_url = article.media_thumbnail[0]['url']
    print(f"✅ Found image (media_thumbnail): {image_url}")
    
elif hasattr(article, 'enclosures'):
    image_url = article.enclosures[0]['href']
    print(f"✅ Found image (enclosures): {image_url}")
    
else:
    print("❌ No standard image found. Here are all the hidden tags in this article:")
    print(article.keys())