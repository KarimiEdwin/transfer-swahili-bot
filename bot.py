import os
import logging
import json
import re
import feedparser
import threading
from groq import Groq
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==============================================================================
# 1. CONFIGURATION & SECRETS
# ==============================================================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)

# RSS Sources (Easy to add more sources here in the future)
RSS_SOURCES = [
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.skysports.com/rss/12040", 
    "https://www.sportskeeda.com/football/rss.xml", 
    "https://www.givemesport.com/rss"              
]

# File Paths
HISTORY_FILE = "posted_history.json"
LEARNING_FILE = "editor_learning.json"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=800&q=80"

# ==============================================================================
# 2. MODULAR HELPER FUNCTIONS
# ==============================================================================
def normalize_text(text: str) -> str:
    """Removes punctuation and lowercases text for accurate duplicate checking."""
    return re.sub(r'[^\w\s]', '', text).lower().strip()

def load_json_file(filepath: str, default_val):
    """Safely loads a JSON file, returning default_val if file is missing or corrupted."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️ Warning: {filepath} was corrupted. Starting fresh.")
    return default_val

def save_json_file(filepath: str, data):
    """Safely saves data to a JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_duplicate(title: str, link: str) -> bool:
    """Checks if an article is a duplicate using Link (primary) or Normalized Title (fallback)."""
    history = load_json_file(HISTORY_FILE, [])
    norm_title = normalize_text(title)
    
    for item in history:
        if link and item.get("link") == link:
            return True
        if normalize_text(item.get("title", "")) == norm_title:
            return True
    return False

def save_to_history(title: str, link: str):
    """Saves article to history, keeping only the last 200 to prevent file bloat."""
    history = load_json_file(HISTORY_FILE, [])
    if not is_duplicate(title, link):
        history.append({"title": title, "link": link})
        if len(history) > 200:
            history = history[-200:]
        save_json_file(HISTORY_FILE, history)
        print(f"✅ History Updated: {title[:50]}...")

def load_learning_history():
    return load_json_file(LEARNING_FILE, [])

def save_learning_example(original_text: str, ai_draft: str, editor_final: str):
    """Saves editor corrections to teach the AI the preferred style."""
    if normalize_text(ai_draft) == normalize_text(editor_final):
        return 
    
    learning_data = load_learning_history()
    learning_data.append({
        "original": original_text,
        "ai_draft": ai_draft,
        "editor_final": editor_final
    })
    
    if len(learning_data) > 5:
        learning_data = learning_data[-5:]
        
    save_json_file(LEARNING_FILE, learning_data)
    print("🧠 Bot learned from your edit!")

# ==============================================================================
# 3. TELEGRAM BOT HANDLERS
# ==============================================================================
custom_keyboard = [[KeyboardButton("🚀 Anza / Start")]]
reply_markup_custom = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_keyboard = [
        [InlineKeyboardButton("📰 Habari za Leo (News)", callback_data='news')],
        [InlineKeyboardButton("🗣️ Uvumi (Rumors)", callback_data='rumors')],
        [InlineKeyboardButton("ℹ️ Kuhusu (About)", callback_data='about')]
    ]
    inline_markup = InlineKeyboardMarkup(inline_keyboard)
    
    await update.message.reply_text("Karibu Transfer Swahili AI! ⚽️\nChagua chaguo lako hapa chini:", reply_markup=inline_markup)
    await update.message.reply_text("👇 Bonyeza hapa kuanza tena:", reply_markup=reply_markup_custom)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data in ['news', 'rumors']:
        try:
            english_title = "No new news available right now."
            english_summary = ""
            article_link = ""
            image_url = DEFAULT_IMAGE
            source_name = "Unknown"
            
            for rss_url in RSS_SOURCES:
                feed = feedparser.parse(rss_url)
                source_name = feed.feed.get('title', 'Football News')
                
                for article in feed.entries[:5]:
                    title = article.title
                    link = article.get('link', '')
                    
                    if not is_duplicate(title, link):
                        english_title = title
                        article_link = link
                        english_summary = article.get('summary', article.get('description', ''))
                        
                        if hasattr(article, 'media_content') and len(article.media_content) > 0:
                            image_url = article.media_content[0]['url']
                        elif hasattr(article, 'media_thumbnail') and len(article.media_thumbnail) > 0:
                            image_url = article.media_thumbnail[0]['url']
                        elif hasattr(article, 'enclosures') and len(article.enclosures) > 0:
                            image_url = article.enclosures[0]['href']
                        break 
                
                if english_title != "No new news available right now.":
                    break 
            
        except Exception as e:
            english_title = "Error fetching news"
            print(f"❌ RSS Fetch Error: {e}")
        
        if english_title in ["No new news available right now.", "Error fetching news"]:
            await query.edit_message_text(text="📰 *Hakuna habari mpya za sasa!* Bot itarudi tena baada ya habari mpya kutoka. ✅", parse_mode='Markdown')
            return

        save_to_history(english_title, article_link)

        learning_examples = load_learning_history()
        examples_text = ""
        if learning_examples:
            examples_text = "\n\n🧠 MFANO ZA MTINDO WA MHARIRI (Editor Style Examples - Mimic this exact style):\n"
            for i, ex in enumerate(learning_examples[-3:], 1):
                examples_text += f"Example {i}:\n- AI Draft: {ex['ai_draft']}\n- Editor Final: {ex['editor_final']}\n"

        if query.data == 'news':
            full_context = f"HEADLINE: {english_title}\nSUMMARY: {english_summary}"
            system_prompt = (
                "Wewe ni mwandishi wa soka maarufu kwenye X (Twitter) ambaye anaelimisha na kusisimua mashabiki wa Afrika Mashariki. "
                "Kazi yako ni kuandika 'Tweet' fupi, yenye nguvu, na inayovutia (Viral Tweet) kutokana na habari hii.\n\n"
                "SHERIA KUU ZA X (TWITTER):\n"
                "1. UREFU: Lazima uze herufi 280. Weka sentensi fupi, 1-2 tu.\n"
                "2. HOOK: Anza na neno la kushtusha na emoji (mfano: '🚨 BOMBA!', '⚽️ HABARI KUBWA!').\n"
                "3. HASHTAGS: Weka hashtags 2-3 zinazofaa mwishoni (mfano: #Soka, #EPL, #Uvumi, #FabrizioRomano).\n"
                "4. JOURNALISTS: Ikiwa habari inataja Fabrizio Romano au David Ornstein, hakikisha unawataja na kuweka hashtag yao.\n"
                "5. LUGHA: Tumia Kiswahili chenye shangwe, mchanganyiko kidogo wa slang ya mtaani ('mabomu', 'kocha', 'dimbani').\n"
                f"{examples_text}\n\nHABARI: \n{full_context}\n\n"
                "SASA ANDIKA TWEET HII (Toa Kiswahili pekee, hakuna maelezo ya ziada kama 'Hii ni tweet'):"
            )
        else: 
            full_context = f"HEADLINE: {english_title}\nSUMMARY: {english_summary}"
            system_prompt = (
                "Wewe ni mfalme wa uvumi wa soka kwenye X (Twitter). Unajulikana kwa 'breaking news' zako za kwanza na mtindo wa kuvutia. "
                "Kazi yako ni kuandika 'Tweet' ya uvumi inayochangamsha mashabiki wa Afrika Mashariki.\n\n"
                "SHERIA KUU ZA X (TWITTER):\n"
                "1. UREFU: Lazima uze herufi 280. Weka sentensi fupi, 1-2 tu.\n"
                "2. HOOK: Anza na emoji na neno la kuvutia (mfano: '🗣️ EXCLUSIVE!', '💣 KIVUMBI!').\n"
                "3. HASHTAGS: Weka hashtags 2-3 (mfano: #Uvumi, #TransferDeadline, #Chelsea).\n"
                "4. JOURNALISTS: Ikiwa habari inataja Fabrizio Romano au David Ornstein, hakikisha unawataja na kuweka hashtag yao.\n"
                "5. LUGHA: Tumia Kiswahili cha mtaani na soka ('mkwaju', 'inadaiwa', 'kocha anatafuta').\n"
                f"{examples_text}\n\nHABARI: \n{full_context}\n\n"
                "SASA ANDIKA TWEET HII (Toa Kiswahili pekee, hakuna maelezo ya ziada):"
            )

        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Andika tweet hii sasa:"}
                ],
                model="llama-3.3-70b-versatile",
            )
            swahili_text = chat_completion.choices[0].message.content
        except Exception as e:
            swahili_text = f"❌ AI Error: {str(e)}"
            print(f"❌ Groq API Error: {e}")

        context.user_data['latest_english'] = english_title
        context.user_data['original_ai_swahili'] = swahili_text
        context.user_data['latest_swahili'] = swahili_text
        context.user_data['latest_image_url'] = image_url
        context.user_data['latest_category'] = query.data
        context.user_data['latest_source'] = source_name
        
        approve_keyboard = [[InlineKeyboardButton("✅ Approve & Post", callback_data='approve')]]
        approve_markup = InlineKeyboardMarkup(approve_keyboard)
        
        caption = (
            f"🇬🇧 *Original:* {english_title}\n\n"
            f"🇹🇿 *Swahili Draft:* \n{swahili_text}\n\n"
            f"💡 *Tip: Reply to this message to edit the Swahili text, or click 'Approve & Post' below!*"
        )
        
        await query.message.delete()
        new_msg = await query.message.reply_photo(
            photo=image_url,
            caption=caption,
            reply_markup=approve_markup,
            parse_mode='Markdown'
        )
        context.user_data['draft_message_id'] = new_msg.message_id

    elif query.data == 'approve':
        english_title = context.user_data.get('latest_english', 'No text found')
        original_ai_swahili = context.user_data.get('original_ai_swahili', '')
        final_swahili = context.user_data.get('latest_swahili', 'No text found')
        image_url = context.user_data.get('latest_image_url', DEFAULT_IMAGE)
        category = context.user_data.get('latest_category', 'news')
        source_name = context.user_data.get('latest_source', 'Football News')
        
        save_learning_example(english_title, original_ai_swahili, final_swahili)
        
        header = f"📰 *HABARI KUTOKA {source_name.upper()}*" if category == 'news' else "🗣️ *UVUMI WA USAJILI*"
        
        await context.bot.send_photo(
            chat_id=CHANNEL_ID, 
            photo=image_url,
            caption=f"{header}\n\n{final_swahili}", 
            parse_mode='Markdown'
        )
        
        await query.message.edit_caption(
            caption=f"✅ *Imechapishwa! Tayari kwa Copy-Paste kwenye X!* 📸🐦\n(Bot imekumbuka habari hii na imejifunza mtindo wako!)",
            parse_mode='Markdown'
        )
        
    elif query.data == 'about':
        await query.edit_message_text(text="ℹ️ Bot hii inaundwa na wewe! Hii ni AI ya habari za usajili inayotafsiri na kuandaa tweets za Kiswahili kwa mashabiki wa soka.")

async def handle_edit_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        expected_draft_id = context.user_data.get('draft_message_id')
        
        if replied_msg_id == expected_draft_id:
            new_swahili_text = update.message.text
            context.user_data['latest_swahili'] = new_swahili_text
            english_title = context.user_data.get('latest_english', '')
            
            new_caption = (
                f"🇬🇧 *Original:* {english_title}\n\n"
                f"🇹🇿 *Swahili Draft (EDITED BY YOU):* \n{new_swahili_text}\n\n"
                f"💡 *Tip: Reply again to edit further, or click 'Approve & Post' below!*"
            )
            
            await update.message.reply_to_message.edit_caption(
                caption=new_caption,
                reply_markup=update.message.reply_to_message.reply_markup,
                parse_mode='Markdown'
            )
            await update.message.reply_text("✅ *Swahili text updated successfully!* Click 'Approve & Post' when ready.", parse_mode='Markdown')

async def handle_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚀 Anza / Start":
        await start(update, context)

# ==============================================================================
# 4. APPLICATION STARTUP & RENDER KEEP-ALIVE TRICK
# ==============================================================================
keep_alive_app = Flask(__name__)

@keep_alive_app.route('/')
def home():
    return "Transfer Swahili AI Bot is alive and running! 🚀"

def run_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    keep_alive_app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # 1. Start the dummy website in a background thread to keep Render happy
    threading.Thread(target=run_keep_alive, daemon=True).start()
    
    # 2. Start the Telegram Bot
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.Text("🚀 Anza / Start"), handle_custom_start))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_edit_reply))
    
    print("🚀 FINAL PRODUCTION BOT IS RUNNING! (Keep-alive active)")
    app.run_polling()