import os
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator

TIMEZONE = pytz.timezone('Europe/London')

def build_feed(selected_items, daily_principle):
    """Generates the final XML feed with the U-Curve framing."""
    now = datetime.now(TIMEZONE)
    
    fg = FeedGenerator()
    fg.title('The U-Curve Brain: Daily Shield')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/', rel='alternate')
    fg.description('A macro-autonomous cognitive filter. 4 parts progress, 1 part deep-dive.')
    
    # Base feed logo setup
    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='U-Curve Brain', link='https://maxmrry.github.io/curious-rabbit-hole-bot/feed.xml')

    # Entry 1: The Daily Anchor (Philosophy Engine)
    fe_intro = fg.add_entry()
    fe_intro.title(f"🛡️ Daily Anchor: {now.strftime('%d %b %Y')}")
    fe_intro.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#anchor-{now.strftime('%Y%m%d')}")
    fe_intro.description(f"<b>System Message:</b><br><em>\"{daily_principle}\"</em><br><br>The U-Curve Brain has actively balanced the scales today, selecting {len(selected_items)} high-signal items to protect your attention.")
    fe_intro.pubDate(now)
    fe_intro.id(f"anchor-{now.strftime('%Y%m%d')}")

    # Entry 2+: The Curated Content
    for item in selected_items:
        fe = fg.add_entry()
        category_emoji = "🔵" if item.get("category") == "positivity" else "🕳️"
        
        fe.title(f"{category_emoji} {item['title']}")
        fe.link(href=item['url'])
        
        # Format the description cleanly
        desc_html = f"<b>Source:</b> {item['source_name']}<br><br>{item['description']}"
        fe.description(desc_html)
        
        # Use the item's original published date, fallback to now
        item_date = datetime.fromtimestamp(item['published_date_ms'] / 1000.0, tz=TIMEZONE)
        fe.pubDate(item_date)
        fe.id(f"brain:{item['native_id']}")

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')
    print("✅ RSS Feed successfully built and saved to docs/feed.xml")
