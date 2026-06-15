import feedparser

# This is the live RSS feed for BBC Sport Football
rss_url = "http://feeds.bbci.co.uk/sport/football/rss.xml"

print("📡 Connecting to BBC Sport...")
# Fetch and parse the live feed
feed = feedparser.parse(rss_url)

print(f"✅ Success! Found {len(feed.entries)} live articles.\n")
print("--- FIRST 3 LIVE HEADLINES ---")

# Loop through the first 3 articles and print them
for i in range(3):
    article = feed.entries[i]
    print(f"{i+1}. {article.title}")
    print(f"   Link: {article.link}\n")