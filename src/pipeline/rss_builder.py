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


def _get_feedback_stage():
    """
    Determines what the algorithm most needs to learn right now.
    Returns a stage name based on how much feedback data exists.
    """
    try:
        with open("state/feedback.json", "r") as f:
            feedback = json.load(f)
        total_signals = len(feedback.get("recent_signals", []))
        if total_signals < 10:
            return "source_calibration"
        elif total_signals < 30:
            return "domain_calibration"
        elif total_signals < 60:
            return "experience_calibration"
        else:
            return "drift_check"
    except FileNotFoundError:
        return "source_calibration"


def _build_feedback_buttons(redirect_base, redirect_secret, date_str):
    """
    Builds contextually appropriate feedback buttons based on calibration stage.
    Questions evolve as the system learns more about Max's preferences.
    """
    import urllib.parse
    token = urllib.parse.quote(redirect_secret)
    stage = _get_feedback_stage()

    def make_url(signal, context=""):
        return (
            f"{redirect_base}/signal"
            f"?item=daily-{date_str}"
            f"&signal={signal}"
            f"&source=daily_experience"
            f"&type=experience"
            f"&context={urllib.parse.quote(context)}"
            f"&dest={urllib.parse.quote('https://maxmrry.github.io/curious-rabbit-hole-bot/')}"
            f"&token={token}"
        )

    if stage == "source_calibration":
        question = "How did today's sources land?"
        buttons = (
            f'<a href="{make_url(2, "sources_excellent")}">Excellent sources</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(1, "sources_mixed")}">Mixed</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(0, "sources_weak")}">Weak sources today</a>'
        )
    elif stage == "domain_calibration":
        question = "What was today's feed missing?"
        buttons = (
            f'<a href="{make_url(2, "want_more_science")}">More science</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(1, "want_more_psychology")}">More psychology</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(0, "want_more_history")}">More history</a>'
        )
    elif stage == "experience_calibration":
        question = "Did today's feed shift your perspective?"
        buttons = (
            f'<a href="{make_url(2, "perspective_shifted")}">Genuinely shifted something</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(1, "felt_informed")}">Informed but familiar</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(0, "too_abstract")}">Too abstract today</a>'
        )
    else:
        question = "Is the feed staying grounded?"
        buttons = (
            f'<a href="{make_url(2, "well_balanced")}">Well balanced</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(1, "slightly_too_positive")}">Slightly too rosy</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="{make_url(0, "lost_credibility")}">Lost its edge</a>'
        )

    return (
        f'<br><br><hr>'
        f'<small><i>{question}</i><br>'
        f'{buttons}</small>'
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

    # --- PREPARE BRIEFING COMPONENTS ---
    max_entry_text = strip_emojis(generate_max_entry(selected_items, now))
    daily_protocol = strip_emojis(clean_quote(get_daily_protocol()))
    daily_principle = strip_emojis(clean_quote(get_daily_principle()))
    narrative = generate_daily_narrative(selected_items)
    
    inoculated_items = [i for i in selected_items if i.get("has_inoculation")]
    doom_count = len(inoculated_items)

    # Build Feedback Buttons
    redirect_base = os.getenv("REDIRECT_BASE_URL", "")
    redirect_secret = os.getenv("REDIRECT_SECRET", "")
    feedback_html = ""
    if redirect_base and redirect_secret:
        feedback_html = _build_feedback_buttons(
            redirect_base=redirect_base,
            redirect_secret=redirect_secret,
            date_str=now.strftime('%Y%m%d')
        )

    # --- ENTRY 1: THE MORNING BRIEFING (Merged) ---
    fe_briefing = fg.add_entry()
    # Uses the Narrative Headline as the punchy title for the whole briefing
    fe_briefing.title(f"{strip_emojis(narrative['headline'])}")
    fe_briefing.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#briefing-{now.strftime('%Y%m%d')}")
    
    # Build the combined HTML description
    briefing_html = f"<b>(Today)</b> {max_entry_text}<br><br>"
    briefing_html += f"<b>(Pattern)</b> {strip_emojis(narrative['explanation'])}<br><br>"
    briefing_html += f"<b>(Reminder)</b> {daily_protocol}<br><br>"
    
    if doom_count >= 2:
        briefing_html += f"<b>(System)</b> {doom_count} items today contained threat language. They have been reframed. The nervous system cannot distinguish between a push notification and a physical threat. Choosing how you receive information is a cognitive skill.<br><br>"
        
    briefing_html += feedback_html
    
    fe_briefing.description(briefing_html)
    fe_briefing.pubDate(now)
    fe_briefing.id(f"briefing-{now.strftime('%Y%m%d')}")

    # --- ENTRY 2: THE ADAGE ---
    fe_intro = fg.add_entry()
    fe_intro.title(f"(Adage) {daily_principle}")
    fe_intro.link(href=f"https://maxmrry.github.io/curious-rabbit-hole-bot/#anchor-{now.strftime('%Y%m%d')}")
    fe_intro.pubDate(now - timedelta(seconds=1))
    fe_intro.id(f"anchor-{now.strftime('%Y%m%d')}")

    # Update the seconds_offset for the rest of the items to start at 2
    seconds_offset = 2

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
