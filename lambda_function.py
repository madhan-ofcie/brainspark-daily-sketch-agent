
import json
import os
import urllib.request
import urllib.parse
import random
import hashlib
import time
from datetime import datetime, timezone, timedelta


# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
CLOUDFLARE_ACCOUNT_ID = os.environ['CLOUDFLARE_ACCOUNT_ID']
CLOUDFLARE_API_TOKEN = os.environ['CLOUDFLARE_API_TOKEN']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']

IST = timezone(timedelta(hours=5, minutes=30))


# ============================================
# MAIN HANDLER (Lambda entry point)
# ============================================
def lambda_handler(event, context):
    """Main handler - triggered daily by EventBridge at 7 AM IST"""
    try:
        today = datetime.now(IST)
        day_name = today.strftime('%A')
        date_str = today.strftime('%B %d, %Y')
        date_key = today.strftime('%Y-%m-%d')

        # Get feedback history from DynamoDB
        feedback_data = get_feedback_history()

        # Generation count
        gen_count = len(feedback_data) + 1

        # Unique seed (timestamp-based = different every second!)
        unique_seed = int(time.time()) + gen_count
        random.seed(unique_seed)

        # Smart theme selection based on feedback
        theme, sub_topic = get_smart_theme(day_name, feedback_data, unique_seed)

        # Generate drawing sketch
        image_url = generate_sketch(theme, sub_topic, unique_seed)

        # Save to DynamoDB
        save_to_dynamodb(today, theme, sub_topic, image_url, gen_count)

        # Send to Telegram
        send_telegram_sketch(image_url, theme, sub_topic, date_str, day_name, feedback_data, gen_count)
        send_telegram_poll(theme)

        # Update S3 Dashboard
        update_s3_dashboard()

        return {
            'statusCode': 200,
            'body': json.dumps(f'BrainSpark Success! Sketch #{gen_count} - {theme}: {sub_topic}')
        }

    except Exception as e:
        send_telegram_text(f"❌ BrainSpark Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }


# ============================================
# FEEDBACK HISTORY (DynamoDB)
# ============================================
def get_feedback_history():
    """Read past feedback from DynamoDB"""
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    table = dynamodb.Table(DYNAMODB_TABLE)
    try:
        response = table.scan()
        items = sorted(response.get('Items', []), key=lambda x: x.get('timestamp', ''), reverse=True)
        return items
    except Exception:
        return []


# ============================================
# SMART THEME ENGINE (Smooth transitions!)
# ============================================
def get_smart_theme(day_name, feedback_data, unique_seed):
    """
    SMART THEME LOGIC with SMOOTH TRANSITIONS:
    - 👍 LIKED → Same theme, different sub-topic
    - ✅ DONE → Move to a CONNECTED/RELATED theme (not random!)
    - No response → Follow connected theme chain
    """

    # Theme families with 15 sub-topics each
    theme_families = {
        'Animals': ['Cute Baby Elephant', 'Lion Cub Playing', 'Panda Eating Bamboo', 'Giraffe Family', 'Playful Puppies', 'Kitten with Yarn Ball', 'Bunny in Flower Garden', 'Wise Owl on Branch', 'Fox in Autumn Forest', 'Deer in Meadow', 'Koala on Tree', 'Monkey Swinging', 'Hippo in Water', 'Zebra Running', 'Bear Catching Fish'],
        'Plants & Flowers': ['Giant Sunflower', 'Rose Garden Path', 'Cactus Family in Desert', 'Cherry Blossom Tree', 'Magical Mushroom Forest', 'Lotus on Calm Pond', 'Tulip Field', 'Vine Growing on Wall', 'Ancient Oak Tree', 'Tropical Jungle Plants', 'Bamboo Forest', 'Lavender Field', 'Bonsai Tree', 'Carnivorous Plant', 'Flower Bouquet'],
        'Vehicles': ['Fire Truck Racing', 'Rocket Ship Launching', 'Pirate Ship on Waves', 'Steam Train on Bridge', 'Hot Air Balloon Festival', 'Yellow Submarine', 'Formula Race Car', 'Rescue Helicopter', 'Bicycle in Park', 'Sailboat at Sunset', 'Monster Truck', 'School Bus', 'Tractor on Farm', 'Spaceship Landing', 'Double Decker Bus'],
        'Sea Creatures': ['Friendly Octopus', 'Dolphin Jumping Waves', 'Sea Turtle Swimming', 'Clownfish in Anemone', 'Blue Whale', 'Seahorse Family', 'Glowing Jellyfish', 'Crab on Sandy Beach', 'Starfish Tide Pool', 'Mermaid with Fish', 'Shark Smiling', 'Lobster', 'Pufferfish', 'Coral Reef Scene', 'Orca Whale'],
        'Birds': ['Colorful Parrot', 'Eagle Soaring High', 'Penguin Family on Ice', 'Peacock Showing Feathers', 'Pink Flamingo', 'Tiny Hummingbird', 'Toucan in Rainforest', 'Robin Building Nest', 'Swan on Lake', 'Woodpecker on Tree', 'Owl at Night', 'Pelican Fishing', 'Kingfisher Diving', 'Ostrich Running', 'Crane Flying'],
        'Insects': ['Monarch Butterfly', 'Ladybug on Green Leaf', 'Bee Collecting Honey', 'Blue Dragonfly', 'Caterpillar on Branch', 'Fireflies at Night', 'Grasshopper Jumping', 'Ant Carrying Food', 'Spider Web with Dew', 'Rhinoceros Beetle', 'Praying Mantis', 'Moth with Moon', 'Centipede', 'Snail in Rain', 'Worm in Apple'],
        'Fantasy': ['Baby Dragon Breathing Fire', 'Unicorn with Rainbow', 'Fairy in Flower', 'Wizard in Tower', 'Mushroom Fairy House', 'Magic Flying Carpet', 'Enchanted Dark Forest', 'Crystal Ice Cave', 'Rainbow Bridge to Castle', 'Cloud Kingdom City', 'Phoenix Rising', 'Gnome Garden', 'Mermaid Palace', 'Pegasus Flying', 'Troll Under Bridge'],
        'Space': ['Astronaut Floating', 'Saturn with Rings', 'Friendly Alien Waving', 'Solar System Planets', 'Shooting Star Trail', 'Space Station', 'Moon Rover Exploring', 'Star Constellation', 'Rocket Launch Pad', 'Earth from Space', 'Mars Colony', 'Black Hole', 'Comet Flying', 'Space Dog', 'Nebula Cloud'],
        'Dinosaurs': ['T-Rex Roaring', 'Triceratops Grazing', 'Long Neck Brontosaurus', 'Pterodactyl Flying', 'Stegosaurus with Plates', 'Baby Dino Hatching from Egg', 'Dino Family Walking', 'Volcano Erupting Scene', 'Dino Footprints Trail', 'Velociraptor Pack', 'Ankylosaurus', 'Spinosaurus Fishing', 'Dino Skeleton Museum', 'Ice Age Mammoth', 'Dino vs Meteor'],
        'Food & Fruits': ['Triple Scoop Ice Cream', 'Pizza with Toppings', 'Fruit Basket Overflowing', 'Three Layer Birthday Cake', 'Decorated Cupcake', 'Watermelon Slice Smiling', 'Spiral Lollipop', 'Cookie Jar Open', 'Fresh Juice Glass', 'Sprinkle Donut', 'Sushi Plate', 'Taco Tuesday', 'Pancake Stack', 'Popcorn Bucket', 'Candy Shop'],
        'Weather': ['Double Rainbow', 'Happy Snowman Family', 'Sun Peeking Through Clouds', 'Lightning Storm', 'Kite Flying in Wind', 'Kid with Umbrella in Rain', 'Autumn Leaves Falling', 'Spring Garden Blooming', 'Beach Summer Day', 'Cozy Winter Cabin', 'Tornado Swirl', 'Fog in Forest', 'Northern Lights', 'Sunrise Mountain', 'Cloud Shapes'],
        'Buildings': ['Treehouse Adventure', 'Lighthouse on Cliff', 'Medieval Castle', 'Dutch Windmill', 'Arctic Igloo', 'Camping Tent by Lake', 'Red Farm Barn', 'Cottage with Garden', 'City Skyscraper', 'Suspension Bridge', 'Pyramid Egypt', 'Japanese Temple', 'Underwater City', 'Space Colony Dome', 'Hobbit Hole House'],
    }

    # Connected themes for smooth transitions
    theme_connections = {
        'Animals':          ['Plants & Flowers', 'Birds', 'Insects', 'Sea Creatures'],
        'Plants & Flowers': ['Insects', 'Birds', 'Weather', 'Animals'],
        'Vehicles':         ['Space', 'Buildings', 'Weather', 'Dinosaurs'],
        'Sea Creatures':    ['Birds', 'Weather', 'Animals', 'Fantasy'],
        'Birds':            ['Animals', 'Insects', 'Plants & Flowers', 'Weather'],
        'Insects':          ['Plants & Flowers', 'Animals', 'Birds', 'Weather'],
        'Fantasy':          ['Space', 'Dinosaurs', 'Buildings', 'Sea Creatures'],
        'Space':            ['Vehicles', 'Fantasy', 'Weather', 'Dinosaurs'],
        'Dinosaurs':        ['Animals', 'Space', 'Fantasy', 'Vehicles'],
        'Food & Fruits':    ['Plants & Flowers', 'Animals', 'Buildings', 'Weather'],
        'Weather':          ['Plants & Flowers', 'Sea Creatures', 'Birds', 'Space'],
        'Buildings':        ['Vehicles', 'Fantasy', 'Food & Fruits', 'Space'],
    }

    # Check last feedback
    if feedback_data and len(feedback_data) > 0:
        last_entry = feedback_data[0]
        last_feedback = last_entry.get('feedback', 'none')
        last_theme = last_entry.get('theme', '')

        # 👍 LIKED → Same theme, different sub-topic
        if last_feedback == 'liked' and last_theme in theme_families:
            theme = last_theme
            used = [i.get('sub_topic', '') for i in feedback_data[:10] if i.get('theme') == theme]
            available = [s for s in theme_families[theme] if s not in used]
            if not available:
                available = theme_families[theme]
            sub_topic = available[unique_seed % len(available)]
            return theme, sub_topic

        # ✅ DONE → Move to CONNECTED theme (smooth shift!)
        elif last_feedback == 'done' and last_theme in theme_connections:
            connected = theme_connections[last_theme]
            used_themes = [i.get('theme', '') for i in feedback_data[:5]]
            available_themes = [t for t in connected if t not in used_themes]
            if not available_themes:
                available_themes = connected
            theme = available_themes[unique_seed % len(available_themes)]
            sub_topics = theme_families[theme]
            sub_topic = sub_topics[unique_seed % len(sub_topics)]
            return theme, sub_topic

        # No feedback → Move to connected theme gently
        elif last_theme in theme_connections:
            connected = theme_connections[last_theme]
            used_themes = [i.get('theme', '') for i in feedback_data[:3]]
            available_themes = [t for t in connected if t not in used_themes]
            if not available_themes:
                available_themes = connected
            theme = available_themes[unique_seed % len(available_themes)]
            sub_topics = theme_families[theme]
            used_subs = [i.get('sub_topic', '') for i in feedback_data[:10]]
            available_subs = [s for s in sub_topics if s not in used_subs]
            if not available_subs:
                available_subs = sub_topics
            sub_topic = available_subs[unique_seed % len(available_subs)]
            return theme, sub_topic

    # First time → Day-based theme
    daily_themes = {
        'Monday': 'Animals',
        'Tuesday': 'Plants & Flowers',
        'Wednesday': 'Vehicles',
        'Thursday': 'Sea Creatures',
        'Friday': 'Birds',
        'Saturday': 'Dinosaurs',
        'Sunday': 'Fantasy'
    }

    theme = daily_themes.get(day_name, 'Animals')
    sub_topics = theme_families.get(theme, ['Fun Drawing'])
    sub_topic = sub_topics[unique_seed % len(sub_topics)]

    return theme, sub_topic


# ============================================
# IMAGE GENERATION
# Primary: Cloudflare Workers AI (10,000 free/day)
# Fallback: Pollinations.ai (unlimited, never fails)
# ============================================
def generate_sketch(theme, sub_topic, unique_seed):
    """Generate image - Cloudflare first, Pollinations fallback"""

    prompt = (
        f"simple kids coloring page of {sub_topic.lower()}, "
        f"black and white line art, thick bold outlines, "
        f"white background, no shading, no color, no gradient, "
        f"clean simple lines, cartoon style, cute and friendly, "
        f"suitable for children to color, printable, minimal detail"
    )

    # Try Cloudflare Workers AI
    try:
        image_url = generate_cloudflare(prompt, unique_seed)
        if image_url:
            return image_url
    except Exception:
        pass

    # Fallback: Pollinations.ai (never fails!)
    return generate_pollinations(prompt, unique_seed)


def generate_cloudflare(prompt, unique_seed):
    """Cloudflare Workers AI - Stable Diffusion XL"""

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"

    seed = unique_seed % 999999999

    payload = {
        "prompt": prompt,
        "negative_prompt": "color, colored, shading, gradient, realistic, photo, blurry, text, watermark, scary, dark, complex background, thin lines, grey",
        "num_steps": 20,
        "guidance": 7.5,
        "seed": seed,
        "width": 1024,
        "height": 1024
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}'
    })

    with urllib.request.urlopen(req, timeout=45) as response:
        image_bytes = response.read()

    if not image_bytes or len(image_bytes) < 1000:
        return None

    # Upload to S3
    return upload_image_to_s3(image_bytes, unique_seed)


def upload_image_to_s3(image_bytes, unique_seed):
    """Upload image to S3 and return public URL"""
    import boto3

    s3_client = boto3.client('s3', region_name='ap-south-1')
    today = datetime.now(IST)
    key = f"sketches/{today.strftime('%Y-%m-%d')}_{unique_seed % 99999}.png"

    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=key,
        Body=image_bytes,
        ContentType='image/png'
    )

    return f"http://{S3_BUCKET_NAME}.s3.ap-south-1.amazonaws.com/{key}"


def generate_pollinations(prompt, unique_seed):
    """Pollinations.ai fallback - URL-based, never fails"""
    seed = unique_seed % 99999
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"


# ============================================
# SAVE TO DYNAMODB
# ============================================
def save_to_dynamodb(today, theme, sub_topic, image_url, gen_count):
    """Save generation data to DynamoDB"""
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    table = dynamodb.Table(DYNAMODB_TABLE)

    table.put_item(Item={
        'date': today.strftime('%Y-%m-%d_%H%M%S'),
        'day': today.strftime('%A'),
        'theme': theme,
        'sub_topic': sub_topic,
        'image_url': image_url,
        'timestamp': today.isoformat(),
        'generated_at': today.strftime('%I:%M %p IST'),
        'generation_number': gen_count,
        'feedback': 'none'
    })


# ============================================
# TELEGRAM - SEND SKETCH
# ============================================
def send_telegram_sketch(image_url, theme, sub_topic, date_str, day_name, feedback_data, gen_count):
    """Send coloring sketch to Telegram"""

    total = len(feedback_data)

    if total == 0:
        stage = "🌱 Day 1"
    elif total < 3:
        stage = "🌿 Learning"
    elif total < 7:
        stage = "🌳 Adapting"
    elif total < 14:
        stage = "🌟 Personalizing"
    else:
        stage = "⭐ Expert"

    # Why this theme
    if feedback_data and feedback_data[0].get('feedback') == 'liked':
        reason = f"📌 You liked {feedback_data[0].get('theme', '')} → Here's more!"
    elif feedback_data and feedback_data[0].get('feedback') == 'done':
        reason = f"🔄 Done with {feedback_data[0].get('theme', '')} → Shifted to related theme!"
    else:
        reason = f"📅 Today's theme: {theme}"

    caption = (
        f"🧠 BrainSpark — Daily Drawing Sketch #{gen_count}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {day_name}, {date_str}\n"
        f"🎨 Theme: {theme}\n"
        f"✏️ Today: {sub_topic}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{reason}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🖍️ Print → Color → Enjoy!\n"
        f"🤖 {stage} | Sketch #{gen_count}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'photo': image_url, 'caption': caption}
    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
        if not result.get('ok'):
            send_telegram_text(f"🎨 Sketch #{gen_count}: {sub_topic}\n🔗 {image_url}")
    except Exception:
        send_telegram_text(f"🎨 Sketch #{gen_count}: {sub_topic}\n🔗 {image_url}")


# ============================================
# TELEGRAM - SEND POLL
# ============================================
def send_telegram_poll(theme):
    """Send feedback poll to Telegram"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'question': f"How was today's {theme} sketch?",
        'options': json.dumps([
            "👍 Liked! More like this!",
            "✅ Done! New theme tomorrow!"
        ]),
        'is_anonymous': False
    }

    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception:
        send_telegram_text(
            f"📊 Rate today's sketch:\n"
            f"Reply: 👍 (More {theme}) or ✅ (New theme)"
        )


# ============================================
# TELEGRAM - SEND TEXT
# ============================================
def send_telegram_text(text):
    """Send plain text message"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': text}).encode('utf-8')
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass


# ============================================
# S3 DASHBOARD
# ============================================
def update_s3_dashboard():
    """Update the S3 hosted dashboard with latest data"""
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    table = dynamodb.Table(DYNAMODB_TABLE)
    s3_client = boto3.client('s3', region_name='ap-south-1')

    response = table.scan()
    all_items = response.get('Items', [])
    items = sorted(all_items, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]

    total = len(all_items)
    liked = sum(1 for i in all_items if i.get('feedback') == 'liked')
    done = sum(1 for i in all_items if i.get('feedback') == 'done')

    if total == 0:
        stage = "Stage 1: Learning"
    elif total < 3:
        stage = "Stage 2: Adapting"
    elif total < 7:
        stage = "Stage 3: Personalizing"
    elif total < 14:
        stage = "Stage 4: Mastering"
    else:
        stage = "Stage 5: Expert"

    progress = min(total * 7, 100)

    # Build sketch cards
    cards_html = ""
    for item in items:
        feedback = item.get('feedback', 'none')
        if feedback == 'liked':
            badge = '<span style="background:#c8e6c9;color:#2e7d32;padding:4px 12px;border-radius:12px;font-size:0.75rem;">👍 Liked → Gave related!</span>'
        elif feedback == 'done':
            badge = '<span style="background:#bbdefb;color:#1565c0;padding:4px 12px;border-radius:12px;font-size:0.75rem;">✅ Done → Switched theme!</span>'
        else:
            badge = '<span style="background:#f5f5f5;color:#999;padding:4px 12px;border-radius:12px;font-size:0.75rem;">⏳ Awaiting</span>'

        cards_html += f"""
        <div style="background:white;border-radius:20px;padding:24px;margin-bottom:20px;box-shadow:0 8px 24px rgba(0,0,0,0.06);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:8px;">
                <div>
                    <div style="color:#764ba2;font-weight:bold;">📅 {item.get('day','')}, {item.get('date','')[:10]}</div>
                    <div style="color:#667eea;margin-top:4px;">🎨 {item.get('theme','')} → ✏️ {item.get('sub_topic','')}</div>
                    <div style="color:#999;font-size:0.75rem;margin-top:2px;">⏰ {item.get('generated_at','')}</div>
                </div>
                <div>{badge}</div>
            </div>
            <div style="text-align:center;padding:15px;background:#fafafa;border-radius:16px;">
                <img src="{item.get('image_url','')}" alt="{item.get('sub_topic','')}"
                     style="max-width:100%;max-height:400px;border-radius:12px;border:2px dashed #764ba2;" loading="lazy"/>
            </div>
        </div>"""

    # Theme flow visualization
    theme_flow = ""
    for i, item in enumerate(reversed(items[:7])):
        t = item.get('theme', '')
        fb = item.get('feedback', '')
        arrow = ' → ' if i < min(len(items), 7) - 1 else ''
        color = '#4caf50' if fb == 'liked' else '#2196f3' if fb == 'done' else '#9e9e9e'
        theme_flow += f'<span style="background:{color}22;color:{color};padding:4px 10px;border-radius:8px;margin:3px;display:inline-block;font-size:0.8rem;border:1px solid {color}44;">{t}</span>{arrow}'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BrainSpark — AI Drawing Sketches for Kids</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:30px 15px}}
.c{{max-width:900px;margin:0 auto}}
</style></head>
<body><div class="c">

<div style="text-align:center;background:white;border-radius:24px;padding:40px 30px;margin-bottom:24px;box-shadow:0 20px 60px rgba(0,0,0,0.12);">
<h1 style="font-size:2.2rem;color:#764ba2;margin-bottom:8px;">🧠✨ BrainSpark</h1>
<p style="color:#555;font-size:1.05rem;">AI-Powered Daily Drawing Sketches for Kids</p>
<p style="color:#999;font-size:0.85rem;margin-top:5px;">Unique Every Time • Learns from Feedback • Smooth Theme Transitions</p>
<div style="display:inline-block;background:#00c853;color:#fff;padding:8px 20px;border-radius:20px;font-size:0.85rem;margin-top:15px;">🟢 ALWAYS-ON — Unique Sketch Every Morning at 7 AM IST</div>
</div>

<div style="background:white;border-radius:20px;padding:24px;margin-bottom:20px;">
<h3 style="color:#764ba2;text-align:center;margin-bottom:12px;">🧬 Agent Evolution: {stage}</h3>
<div style="background:#f0f0f0;border-radius:10px;height:16px;margin:12px 0;overflow:hidden;">
<div style="background:linear-gradient(90deg,#667eea,#764ba2);height:100%;width:{progress}%;border-radius:10px;"></div></div>
<p style="font-size:0.8rem;color:#888;text-align:center;">👍 Like = More of same theme | ✅ Done = Smooth shift to related theme</p>
</div>

<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
<div style="background:white;border-radius:14px;padding:18px 10px;text-align:center;"><h3 style="color:#764ba2;font-size:1.6rem;">{total}</h3><p style="font-size:0.75rem;color:#666;">Sketches</p></div>
<div style="background:white;border-radius:14px;padding:18px 10px;text-align:center;"><h3 style="color:#4caf50;font-size:1.6rem;">{liked}</h3><p style="font-size:0.75rem;color:#666;">👍 Liked</p></div>
<div style="background:white;border-radius:14px;padding:18px 10px;text-align:center;"><h3 style="color:#2196f3;font-size:1.6rem;">{done}</h3><p style="font-size:0.75rem;color:#666;">✅ Done</p></div>
<div style="background:white;border-radius:14px;padding:18px 10px;text-align:center;"><h3 style="color:#ff9800;font-size:1.6rem;">12</h3><p style="font-size:0.75rem;color:#666;">🎨 Themes</p></div>
</div>

<div style="background:white;border-radius:16px;padding:20px;margin-bottom:20px;">
<h4 style="color:#764ba2;margin-bottom:12px;">📈 Theme Progression (Agent Learning Path):</h4>
<div style="line-height:2.2;">{theme_flow if theme_flow else '<span style="color:#999;">Will show after first sketches...</span>'}</div>
<p style="font-size:0.75rem;color:#aaa;margin-top:12px;">🟢 Green = Liked (gave related) | 🔵 Blue = Done (smooth shift) | ⚪ Grey = No feedback</p>
</div>

<div style="background:white;border-radius:16px;padding:20px;margin-bottom:20px;">
<h4 style="color:#764ba2;margin-bottom:10px;">🔄 How the Smart Feedback Loop Works:</h4>
<div style="font-size:0.85rem;color:#555;line-height:1.8;">
<p>1️⃣ Agent generates unique sketch + sends to Telegram with poll</p>
<p>2️⃣ User votes: 👍 <b>Like</b> (want more of same) or ✅ <b>Done</b> (ready for new)</p>
<p>3️⃣ 👍 Like → Same theme, different drawing (goes deeper!)</p>
<p>4️⃣ ✅ Done → Smoothly shifts to a RELATED theme (not random!)</p>
<p style="margin-top:8px;color:#764ba2;font-weight:bold;">Example: Animals → Plants → Insects → Birds (natural flow!) 🌿</p>
</div></div>

{cards_html}

<div style="text-align:center;color:white;margin-top:30px;padding:20px;">
<p style="font-size:0.9rem;font-weight:bold;">⚡ Architecture</p>
<p style="font-size:0.8rem;margin-top:5px;">AWS Lambda + EventBridge + DynamoDB + S3</p>
<p style="font-size:0.8rem;">Images: Cloudflare Workers AI (SDXL) + Pollinations.ai fallback</p>
<p style="font-size:0.8rem;">Delivery: Telegram Bot with Interactive Polls</p>
<div style="display:inline-block;background:rgba(255,153,0,0.3);border:1px solid #ff9900;padding:6px 14px;border-radius:12px;color:#ff9900;font-size:0.8rem;margin-top:12px;">⚡ 100% Free Tier — Zero Cost</div>
<p style="margin-top:12px;font-size:0.7rem;opacity:0.7;">Last updated: {datetime.now(IST).strftime('%B %d, %Y at %I:%M %p IST')}</p>
</div>
</div></body></html>"""

    s3_client.put_object(Bucket=S3_BUCKET_NAME, Key='index.html', Body=html.encode('utf-8'), ContentType='text/html')

