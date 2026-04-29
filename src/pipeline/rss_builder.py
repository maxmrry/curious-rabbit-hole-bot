import os
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
from src.pipeline.philosophy import get_daily_principle, get_daily_protocol

TIMEZONE = pytz.timezone('Europe/London')

def build_feed(selected_items):
    """Generates the final XML feed with the U-Curve cognitive framing."""
    now = datetime.now(TIMEZONE)
    
    fg = FeedGenerator()
    fg.title('The U-Curve Brain: Daily Shield')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/', rel='alternate')
    fg.description('A macro-autonomous cognitive filter. Optimizing for agency, perspective, and resilience.')
    
    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='U-Curve Brain', link='https://maxmrry.github.io/curious-rabbit-hole-bot/feed.xml')

    # --- ENTRY 1: The Daily Protocol (Power of Bad) ---
    daily_protocol = get_daily_protocol()
    fe_rem = fg.add_entry()
    fe_rem.title(f"🧠 Daily Protocol: {now.strftime('%d %b')}")
    fe_rem.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#protocol-{now.strftime('%Y%m%d')}")
    fe_rem.description(f"<b>Active Rewire:</b> {daily_protocol}")
    fe_rem.pubDate(now)
    fe_rem.id(f"protocol-{now.strftime('%Y%m%d')}")

    # --- ENTRY 2: The Daily Anchor (Adage) ---
    daily_principle = get_daily_principle()
    fe_intro = fg.add_entry()
    fe_intro.title(f"🛡️ Daily Anchor: {now.strftime('%d %b')}")
    fe_intro.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#anchor-{now.strftime('%Y%m%d')}")
    fe_intro.description(f"<em>\"{daily_principle}\"</em><br><br>The U-Curve Brain has balanced the scales today, selecting {len(selected_items)} high-signal items.")
    fe_intro.pubDate(now)
    fe_intro.id(f"anchor-{now.strftime('%Y%m%d')}")

    # --- ENTRY 3+: The Curated Content ---
    for item in selected_items:
        fe = fg.add_entry()
        
        # Clean text prefixes instead of emojis
        if item["source_type"] == "podcast":
            prefix = "(Audio) "
        elif item["source_type"] == "rss":
            prefix = "(Research) "
        elif item["source_type"] == "news":
            prefix = "(News) "
        else:
            prefix = "" # YouTube gets no prefix, easily recognizable by thumbnail
            
        fe.title(f"{prefix}{item['title']}")
        fe.link(href=item['url'])
        
        # Build description with embedded Thumbnail
        final_desc = f"<b>Source:</b> {item['source_name']}<br><br>"
        if item.get('image_url'):
            # Enclosure for RSS readers that parse hero images
            fe.enclosure(item['image_url'], 0, 'image/jpeg') 
            # HTML img tag for readers that display it in the text body
            final_desc += f"<img src='{item['image_url']}' alt='thumbnail' style='max-width:100%; border-radius:8px;'/><br><br>"
            
        final_desc += item['description']
        fe.description(final_desc)
        
        # Direct Audio Link for Podcasts
        if item.get('audio_url'):
            fe.enclosure(item['audio_url'], 0, 'audio/mpeg')

        item_date = datetime.fromtimestamp(item['published_date_ms'] / 1000.0, tz=TIMEZONE)
        fe.pubDate(item_date)
        fe.id(f"brain:{item['native_id']}")

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')
    print("✅ RSS Feed successfully built and saved to docs/feed.xml")
