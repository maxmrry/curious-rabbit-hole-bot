import os
import re
from datetime import datetime, timedelta
import pytz
from feedgen.feed import FeedGenerator
from src.pipeline.philosophy import get_daily_principle, get_daily_protocol, generate_daily_narrative

TIMEZONE = pytz.timezone('Europe/London')

def clean_quote(text):
    """Removes quotes, 'wisdom:', and trailing/leading whitespace."""
    text = text.replace('"', '').replace('"', '').replace('"', '')
    text = re.sub(r'(?i)^wisdom:\s*', '', text)
    return text.strip()

def strip_emojis(text):
    """Removes all emoji characters from a string for clean RSS output."""
    if not text:
        return text
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF"
        "\U00002700-\U000027BF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U0000FE00-\U0000FE0F"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()

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

    # --- ENTRY 0: The Max Entry — Personalised Cold Open ---
    max_entry_text = strip_emojis(generate_max_entry(selected_items, now))
    fe_max = fg.add_entry()
    fe_max.title(f"(Today) {max_entry_text[:80].split('.')[0].strip()}")
    fe_max.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#max-{now.strftime('%Y%m%d')}")
    fe_max.description(max_entry_text)
    fe_max.pubDate(now + timedelta(seconds=1))
    fe_max.id(f"max-entry-{now.strftime('%Y%m%d')}")

    # --- ENTRY 1: The Daily Protocol ---
    daily_protocol = strip_emojis(clean_quote(get_daily_protocol()))
    fe_rem = fg.add_entry()
    fe_rem.title(f"(Reminder) {daily_protocol}")
    fe_rem.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#protocol-{now.strftime('%Y%m%d')}")
    fe_rem.pubDate(now)
    fe_rem.id(f"protocol-{now.strftime('%Y%m%d')}")

    # --- ENTRY 2: The Daily Anchor ---
    # Subtract 1 second so the Adage stays neatly grouped under the Reminder
    daily_principle = strip_emojis(clean_quote(get_daily_principle()))
    fe_intro = fg.add_entry()
    fe_intro.title(f"(Adage) {daily_principle}")
    fe_intro.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#anchor-{now.strftime('%Y%m%d')}")
    fe_intro.pubDate(now - timedelta(seconds=1))
    fe_intro.id(f"anchor-{now.strftime('%Y%m%d')}")

    # --- ENTRY 2.5: The Narrative Stitch ---
    narrative = generate_daily_narrative(selected_items)
    fe_narrative = fg.add_entry()
    fe_narrative.title(f"{narrative['headline']}")
    fe_narrative.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#theme-{now.strftime('%Y%m%d')}")
    fe_narrative.description(narrative['explanation'])
    fe_narrative.pubDate(now - timedelta(seconds=2))
    fe_narrative.id(f"theme-{now.strftime('%Y%m%d')}")
    
    # Update the seconds_offset for the rest of the items to start at 3
    seconds_offset = 3

    # --- ENTRY 3+: The Curated Content ---
    # We subtract seconds sequentially so the items order beautifully in your reader
    seconds_offset = 2

    # --- DOOM INOCULATION CIRCUIT BREAKER ---
    # If multiple items triggered a doom inoculation reframe, surface it as a standalone entry
    inoculated_items = [i for i in selected_items if "🛡️" in i.get("description", "")]
    if len(inoculated_items) >= 2:
        fe_inoculation = fg.add_entry()
        fe_inoculation.title("(System) Your feed today contains reframed negative signals — here's why that matters")
        fe_inoculation.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#inoculation-{now.strftime('%Y%m%d')}")
        fe_inoculation.description(
            f"<b>{len(inoculated_items)} items today</b> contained language associated with threat or urgency. "
            "Each has been reframed with a stoic counter-perspective. This is not denial — it is calibration. "
            "The nervous system cannot distinguish between a push notification and a physical threat. "
            "Choosing how you receive information is a cognitive skill, not avoidance. "
            "<br><br><i>— U-Curve Brain, running psychological triage since boot.</i>"
        )
        fe_inoculation.pubDate(now - timedelta(seconds=seconds_offset))
        fe_inoculation.id(f"inoculation-{now.strftime('%Y%m%d')}")
        seconds_offset += 1

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
            
        fe.title(f"{prefix}{strip_emojis(item['title'])}")
        fe.link(href=item['url'])

        # Build description with embedded Thumbnail
        final_desc = f"<b>Source:</b> {strip_emojis(item['source_name'])}<br><br>"
        if item.get('image_url'):
            fe.enclosure(item['image_url'], 0, 'image/jpeg') 
            final_desc += f"<img src='{item['image_url']}' alt='thumbnail' style='max-width:100%; border-radius:8px;'/><br><br>"
            
        final_desc += strip_emojis(item['description'])
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
