from deep_translator import GoogleTranslator

# This is our fake English football news
english_news = "Manchester United is close to signing a new striker from Brazil."

# This tells the translator to take English ('en') and turn it into Swahili ('sw')
swahili_news = GoogleTranslator(source='en', target='sw').translate(english_news)

# Print the results to the terminal so we can see it work
print("--- TRANSLATION TEST ---")
print("English:", english_news)
print("Swahili:", swahili_news)