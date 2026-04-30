import os
import re
from datetime import datetime, timedelta
import pytz
from feedgen.feed import FeedGenerator
from src.pipeline.philosophy import get_daily_principle, get_daily_protocol

TIMEZONE = pytz.timezone('Europe/London')

def clean_quote(text):
    """Removes quotes, 'wisdom:', and trailing/leading whitespace."""
    text = text.replace('"', '').replace('“', '').replace('”', '')
    text = re.sub(r'(?i)^wisdom:\s*', '', text)
    return text.strip()

def build_feed(selected_items):
    """Generates the final XML feed with clean, stoic framing."""
    now = datetime.now(TIMEZONE)
    
    fg = FeedGenerator()
    fg.title('The U-Curve Brain')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/', rel='alternate')
    fg.description('A macro-autonomous cognitive filter. Optimizing for agency, perspective, and resilience.')
    
    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='U-Curve Brain', link='https://maxmrry.github.io/curious-rabbit-hole-bot/feed.xml')

    # --- ENTRY 1: The Daily Protocol ---
    daily_protocol = clean_quote(get_daily_protocol())
    fe_rem = fg.add_entry()
    fe_rem.title(f"(Reminder) {daily_protocol}")
    fe_rem.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#protocol-{now.strftime('%Y%m%d')}")
    fe_rem.description("Daily cognitive baseline.")
    fe_rem.pubDate(now)
    fe_rem.id(f"protocol-{now.strftime('%Y%m%d')}")

    # --- ENTRY 2: The Daily Anchor ---
    # Subtract 1 second so the Adage stays neatly grouped under the Reminder
    daily_principle = clean_quote(get_daily_principle())
    fe_intro = fg.add_entry()
    fe_intro.title(f"(Adage) {daily_principle}")
    fe_intro.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#anchor-{now.strftime('%Y%m%d')}")
    fe_intro.description("A timeless principle for cognitive resilience.")
    fe_intro.pubDate(now - timedelta(seconds=1))
    fe_intro.id(f"anchor-{now.strftime('%Y%m%d')}")

    # --- ENTRY 3+: The Curated Content ---
    # We subtract seconds sequentially so the items order beautifully in your reader
    seconds_offset = 2

    for item in selected_items:
        fe = fg.add_entry()
        
        if item["source_type"] == "podcast":
            prefix = "(Audio) "
        elif item["source_type"] == "rss":
            prefix = "(Research) "
        elif item["source_type"] == "news":
            prefix = "(News) "
        elif item["source_type"] == "youtube":
            prefix = "(Video) "
        else:
            prefix = ""
            
        fe.title(f"{prefix}{item['title']}")
        fe.link(href=item['url'])
        
        # Build description with embedded Thumbnail
        final_desc = f"<b>Source:</b> {item['source_name']}<br><br>"
        if item.get('image_url'):
            fe.enclosure(item['image_url'], 0, 'image/jpeg') 
            final_desc += f"<img src='{item['image_url']}' alt='thumbnail' style='max-width:100%; border-radius:8px;'/><br><br>"
            
        final_desc += item['description']
        fe.description(final_desc)
        
        if item.get('audio_url'):
            fe.enclosure(item['audio_url'], 0, 'audio/mpeg')

        # FIX: Stamp every item with TODAY'S date so they appear at the top of your feed
        item_date = now - timedelta(seconds=seconds_offset)
        fe.pubDate(item_date)
        fe.id(f"brain:{item['native_id']}")
        
        seconds_offset += 1

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')
    print("✅ RSS Feed successfully built and saved to docs/feed.xml")
