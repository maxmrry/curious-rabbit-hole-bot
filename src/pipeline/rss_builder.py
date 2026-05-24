import os
import re
import json
from datetime import datetime, timedelta
import pytz
from feedgen.feed import FeedGenerator
from src.pipeline.philosophy import (
    get_daily_principle, get_daily_protocol,
    generate_daily_narrative, generate_max_entry, _get_register
)

TIMEZONE = pytz.timezone('Europe/London')


def clean_quote(text):
    """Removes quotes, 'wisdom:', and trailing/leading whitespace."""
    text = text.replace('\u201c', '').replace('\u201d', '').replace('"', '')
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


def _build_micro_feedback(redirect_base, redirect_secret, item):
    """
    Builds item-specific psychological feedback buttons.
    Injects the TITLE into the context so the AI knows exactly what the topic was.
    """
    import urllib.parse
    token = urllib.parse.quote(redirect_secret)

    item_id = urllib.parse.quote(item.get("native_id", "unknown"))
    source = urllib.parse.quote(item.get("source_name", "unknown"))
    source_type = urllib.parse.quote(item.get("source_type", "unknown"))
    
    # Grab a short, clean version of the title to send to the AI
    short_title = item.get("title", "Unknown Title")[:80]

    def make_url(signal, emotion_label):
        # We package the emotion AND the title together so the AI can read it later!
        combined_context = f"{emotion_label} | Topic: {short_title}"
        return (
            f"{redirect_base}/signal"
            f"?item={item_id}"
            f"&signal={signal}"
            f"&source={source}"
            f"&type={source_type}"
            f"&context={urllib.parse.quote(combined_context)}"
            f"&dest={urllib.parse.quote('https://maxmrry.github.io/curious-rabbit-hole-bot/')}"
            f"&token={token}"
        )

    return (
        f"<br><br><hr>"
        f"<small><b>How did this land?</b><br>"
        f"<a href='{make_url(3, 'amazingly_hopeful')}' style='text-decoration:none;'>🥇✅ Wow, I Feel Positive, Inspired, Impressed</a><br>"
        f"<a href='{make_url(2, 'pretty_positive')}' style='text-decoration:none;'>💪 Pretty Positive. Kinda Cool.</a><br>"
        f"<a href='{make_url(1, 'neutral_okay')}' style='text-decoration:none;'>🤔 Hmm. Okay, but forgettable.</a><br>"
        f"<a href='{make_url(0, 'not_interested')}' style='text-decoration:none;'>🥱 Don't Care... Not Interested</a><br>"
        f"<a href='{make_url(-1, 'too_gloomy')}' style='text-decoration:none;'>⛔ Too Gloomy / Negative</a>"
        f"</small>"
    )


def _sequence_items(items):
    """
    Psychologically sequences items for maximum impact.
    Deep dive opens, news closes, middle alternates registers.
    """
    deep = [i for i in items if i.get("category") == "deep_dive"]
    news = [i for i in items if i.get("source_type") == "news"]
    middle = [i for i in items if i not in deep and i not in news]

    sequenced_middle = []
    last_register = None
    remaining = list(middle)

    while remaining:
        next_item = next(
            (i for i in remaining if _get_register(i) != last_register),
            remaining[0]
        )
        sequenced_middle.append(next_item)
        last_register = _get_register(next_item)
        remaining.remove(next_item)

    return deep + sequenced_middle + news


def build_feed(selected_items):
    """Generates the final XML feed with clean, stoic framing."""
    now = datetime.now(TIMEZONE)

    # Apply psychological sequencing before building
    selected_items = _sequence_items(selected_items)

    fg = FeedGenerator()
    fg.title('The U-Curve Brain')
    fg.link(href='https://maxmrry.github.io/curious-rabbit-hole-bot/', rel='alternate')
    fg.description('A macro-autonomous cognitive filter. Optimizing for agency, perspective, and resilience.')

    image_url = 'https://raw.githubusercontent.com/maxmrry/curious-rabbit-hole-bot/main/bot-logo.png'
    fg.logo(image_url)
    fg.image(url=image_url, title='U-Curve Brain', link='https://maxmrry.github.io/curious-rabbit-hole-bot/feed.xml')

    # --- ENTRY 1: THE ADAGE & MASTER RESET BUTTON ---
    daily_principle = strip_emojis(clean_quote(get_daily_principle()))
    
    fe_intro = fg.add_entry()
    fe_intro.title(f"(Adage) {daily_principle}")
    fe_intro.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#anchor-{now.strftime('%Y%m%d')}")
    fe_intro.pubDate(now)
    fe_intro.id(f"anchor-{now.strftime('%Y%m%d')}")

    # Build the Master "Nuke the Feed" Button
    import urllib.parse
    redirect_base = os.getenv("REDIRECT_BASE_URL", "")
    redirect_secret = os.getenv("REDIRECT_SECRET", "")
    if redirect_base and redirect_secret:
        token = urllib.parse.quote(redirect_secret)
        nuke_url = (
            f"{redirect_base}/signal"
            f"?item=daily_feed_{now.strftime('%Y%m%d')}"
            f"&signal=0"
            f"&source=daily_experience"
            f"&type=feed"
            f"&context=whole_feed_boring"
            f"&dest={urllib.parse.quote('https://maxmrry.github.io/curious-rabbit-hole-bot/')}"
            f"&token={token}"
        )
        fe_intro.description(
            f"<small><i>If today's overall curation completely missed the mark, tap below to trigger an algorithmic shake-up for tomorrow.</i></small><br><br>"
            f"<a href='{nuke_url}' style='text-decoration:none;'>🔄 The whole feed is boring today</a>"
        )

    # Update the seconds_offset for the rest of the curated items to start at 1
    seconds_offset = 1

    # --- CURATED CONTENT ---
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

        final_desc = f"<b>Source:</b> {strip_emojis(item['source_name'])}<br><br>"
        if item.get('image_url'):
            fe.enclosure(item['image_url'], 0, 'image/jpeg')
            final_desc += f"<img src='{item['image_url']}' alt='thumbnail' style='max-width:100%; border-radius:8px;'/><br><br>"

        final_desc += strip_emojis(item['description'])

        # Inject Micro-Feedback RLHF Buttons
        redirect_base = os.getenv("REDIRECT_BASE_URL", "")
        redirect_secret = os.getenv("REDIRECT_SECRET", "")
        if redirect_base and redirect_secret:
            final_desc += _build_micro_feedback(redirect_base, redirect_secret, item)

        fe.description(final_desc)

        if item.get('audio_url'):
            fe.enclosure(item['audio_url'], 0, 'audio/mpeg')

        item_date = now - timedelta(seconds=seconds_offset)
        fe.pubDate(item_date)
        fe.id(f"brain:{item['native_id']}")
        seconds_offset += 1

    os.makedirs('docs', exist_ok=True)
    fg.rss_file('docs/feed.xml')
    print("RSS Feed successfully built and saved to docs/feed.xml")
