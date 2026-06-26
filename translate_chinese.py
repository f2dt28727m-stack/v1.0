#!/usr/bin/env python3
"""Translate all remaining Chinese content in quiz JSON files to English.

Strategy:
- For files with mixed Chinese/English (one or two Chinese words/phrases),
  use exact-string replacement on the parsed structure.
- For files that are entirely in Chinese (quiz_110, quiz_177, quiz_182),
  rebuild the file's questions block using a translation map.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
QUIZ_DIR = os.path.join(ROOT, "quizzes")

CN = re.compile(r"[\u4e00-\u9fff]")

# ---------- Translation maps (file -> list of (old, new) pairs) ----------
# Single-line / small translations
SMALL_MAP = {
    "quiz_28.json": [
        ("浪漫", "Romance"),
        ("爱情", "Love"),
        ("情感", "Emotion"),
    ],
    "quiz_91.json": [
        ("You discover a broken combo with a冷门英雄. What's your first move?",
         "You discover a broken combo with an off-meta hero. What's your first move?"),
    ],
    "quiz_147.json": [
        ("When planning a new开拓 mission, you prioritize...",
         "When planning a new pioneering mission, you prioritize..."),
    ],
    "quiz_168.json": [
        ("Set a deadline and stick to it, avoiding拖延",
         "Set a deadline and stick to it, avoiding procrastination"),
    ],
    "quiz_169.json": [
        ("Imagine how the场景 conveys the song's emotional core",
         "Imagine how the scene conveys the song's emotional core"),
        ("Prefer a familiar studio to stay focused on细节",
         "Prefer a familiar studio to stay focused on details"),
        ("Blend styles and see what develops during创作",
         "Blend styles and see what develops during the creative process"),
        ("Ignore them and focus on your work to prove实力",
         "Ignore them and focus on your work to prove your strength"),
        ("You express yourself through beauty and emotion, noticing life's细腻 details. Like BLACKPINK's visually stunning stages, you create moments that touch hearts. Gentle and creative, you add depth and warmth to the team. You're an ISFP—artistic, sensitive, and the group's muse.",
         "You express yourself through beauty and emotion, noticing life's subtle details. Like BLACKPINK's visually stunning stages, you create moments that touch hearts. Gentle and creative, you add depth and warmth to the team. You're an ISFP—artistic, sensitive, and the group's muse."),
        ("You excel at managing chaos, turning plans into高效行动. Like BLACKPINK's seamless performances, you ensure the team runs like a well-oiled machine. Decisive and responsible, you lead with clarity and purpose. You're an ESTJ—organized, confident, and the group's director.",
         "You excel at managing chaos, turning plans into efficient action. Like BLACKPINK's seamless performances, you ensure the team runs like a well-oiled machine. Decisive and responsible, you lead with clarity and purpose. You're an ESTJ—organized, confident, and the group's director."),
    ],
    "quiz_170.json": [
        ("You\u2019re充满激情和乐观，就像BLACKPINK传递的正能量。你对新想法充满好奇，总是看到可能性，并用热情感染周围的人。你热爱探索和分享，让平凡的日子变得充满意义。你是ENFP——富有想象力、热情洋溢，是梦想的追求者。",
         "You\u2019re full of passion and optimism, just like the positive energy BLACKPINK radiates. You\u2019re always curious about new ideas, see possibilities everywhere, and inspire everyone around you with your enthusiasm. You love exploring and sharing, turning ordinary days into something meaningful. You\u2019re an ENFP\u2014imaginative, enthusiastic, and a true dreamer who chases the impossible."),
    ],
    "quiz_175.json": [
        ("Practice new魁地奇 moves, imagining game-winning strategies",
         "Practice new Quidditch moves, imagining game-winning strategies"),
        ("Your friend is falsely accused of stealing a金杯\u2014you...",
         "Your friend is falsely accused of stealing a golden cup\u2014you..."),
    ],
    "quiz_176.json": [
        ("During Quidditch practice, the captain asks for new战术 ideas. You suggest...",
         "During Quidditch practice, the captain asks for new tactical ideas. You suggest..."),
        ("You\u2019re the thoughtful, analytical mind with a gentle heart. Like Lupin, you\u2019re博学且内敛, sharing wisdom only when it matters most. You see the world through a lens of curiosity, whether studying werewolf lore or teaching Defense Against the Dark Arts. You\u2019re humble about your strengths, but your ability to think critically and empathize makes you a trusted guide to those lucky enough to know you.",
         "You\u2019re the thoughtful, analytical mind with a gentle heart. Like Lupin, you\u2019re learned and reserved, sharing wisdom only when it matters most. You see the world through a lens of curiosity, whether studying werewolf lore or teaching Defense Against the Dark Arts. You\u2019re humble about your strengths, but your ability to think critically and empathize makes you a trusted guide to those lucky enough to know you."),
    ],
    "quiz_179.json": [
        ("You maximize every minute\u2014early morning hikes, back-to-back museums, and strategic naps to keep energy high. You hate wasting time, so you research the \u2018best of\u2019 lists and optimize routes like a pro. You return home with a相册 full of photos and a brain full of facts. You\u2019re an ESTJ\u2014driven, practical, and determined to get the most out of every adventure.",
         "You maximize every minute\u2014early morning hikes, back-to-back museums, and strategic naps to keep energy high. You hate wasting time, so you research the \u2018best of\u2019 lists and optimize routes like a pro. You return home with a photo album full of snapshots and a brain full of facts. You\u2019re an ESTJ\u2014driven, practical, and determined to get the most out of every adventure."),
        ("You\u2019re the perfect mix of planner and dreamer\u2014you book accommodations in advance but leave afternoons open for spontaneous detours. You enjoy both热闹的 markets and quiet hikes, knowing balance is key to a great trip. You\u2019re adaptable, easygoing, and always up for whatever the journey brings. You\u2019re an ENFJ\u2014charismatic, organized, and the ultimate travel companion.",
         "You\u2019re the perfect mix of planner and dreamer\u2014you book accommodations in advance but leave afternoons open for spontaneous detours. You enjoy both lively markets and quiet hikes, knowing balance is key to a great trip. You\u2019re adaptable, easygoing, and always up for whatever the journey brings. You\u2019re an ENFJ\u2014charismatic, organized, and the ultimate travel companion."),
    ],
    "quiz_183.json": [
        ("Simba is your soulmate! Playful, energetic, and full of life, they live in the moment and spread positivity wherever they go. They\u2019re brave and loyal, with a heart that loves fiercely. Together, you\u2019ll embrace adventure and find joy in the simplest things. They\u2019re an ESFP\u2014spontaneous,热情, and the life of the party.",
         "Simba is your soulmate! Playful, energetic, and full of life, they live in the moment and spread positivity wherever they go. They\u2019re brave and loyal, with a heart that loves fiercely. Together, you\u2019ll embrace adventure and find joy in the simplest things. They\u2019re an ESFP\u2014spontaneous, warm-hearted, and the life of the party."),
        ("Ariel is your soulmate! Curious, passionate, and eager to explore the world, she\u2019s drawn to new experiences and isn\u2019t afraid to dream big. With a fiery spirit and a heart full of courage, she\u2019ll inspire you to chase your goals. Together, you\u2019ll dive into new adventures. She\u2019s an ESFP\u2014spontaneous,热情, and always ready for the next big thing.",
         "Ariel is your soulmate! Curious, passionate, and eager to explore the world, she\u2019s drawn to new experiences and isn\u2019t afraid to dream big. With a fiery spirit and a heart full of courage, she\u2019ll inspire you to chase your goals. Together, you\u2019ll dive into new adventures. She\u2019s an ESFP\u2014spontaneous, warm-hearted, and always ready for the next big thing."),
    ],
    "quiz_186.json": [
        ("Randomly想起不同电影的片段，没有固定顺序",
         "Randomly recall scenes from different movies, with no fixed order"),
        ("Relax and enjoy the氛围 without taking on leadership roles",
         "Relax and enjoy the atmosphere without taking on leadership roles"),
    ],
    "quiz_187.json": [
        ("Moana, with its concrete航海 adventures and island exploration",
         "Moana, with its concrete seafaring adventures and island exploration"),
    ],
    "quiz_192.json": [
        ("Actively ask and陪伴 them through the problem",
         "Actively ask and accompany them through the problem"),
        ("Rigid plans bore you; you thrive in the unexpected. Like Tony Stark, your hidden trait is adaptive creativity\u2014you turn setbacks into experiments, using即兴 ideas to solve problems no rulebook could predict. Your mind works best when unshackled by convention.",
         "Rigid plans bore you; you thrive in the unexpected. Like Tony Stark, your hidden trait is adaptive creativity\u2014you turn setbacks into experiments, using improvisational ideas to solve problems no rulebook could predict. Your mind works best when unshackled by convention."),
    ],
    "quiz_196.json": [
        ("You approach challenges with冷静 logic, dissecting problems to find optimal solutions. Your ability to see patterns and anticipate outcomes makes you a go-to for critical decisions. You balance data-driven thinking with strategic vision, ensuring every choice aligns with long-term goals.",
         "You approach challenges with calm logic, dissecting problems to find optimal solutions. Your ability to see patterns and anticipate outcomes makes you a go-to for critical decisions. You balance data-driven thinking with strategic vision, ensuring every choice aligns with long-term goals."),
    ],
    "quiz_198.json": [
        ("Your future career as a Marketing Specialist lets you blend creativity with people skills to tell brand stories. You excel at understanding audiences, brainstorming innovative campaigns, and adapting to changing trends. Your热情 and ability to inspire others make you a driving force in connecting brands with their communities.",
         "Your future career as a Marketing Specialist lets you blend creativity with people skills to tell brand stories. You excel at understanding audiences, brainstorming innovative campaigns, and adapting to changing trends. Your passion and ability to inspire others make you a driving force in connecting brands with their communities."),
    ],
    "quiz_199.json": [
        ("Try网红 fusion dishes you saw online",
         "Try trendy influencer-famous fusion dishes you saw online"),
        ("A pre-made便当 you packed this morning",
         "A pre-made bento box you packed this morning"),
        ("Warm and包容, you have a way of making everyone feel accepted. Like cheese, you\u2019re rich, complex, and get better with time, revealing new layers to those who take the time to know you. You\u2019re idealistic, empathetic, and believe in the goodness of people. You\u2019re an INFP\u2014compassionate, creative, and a dreamer at heart.",
         "Warm and inclusive, you have a way of making everyone feel accepted. Like cheese, you\u2019re rich, complex, and get better with time, revealing new layers to those who take the time to know you. You\u2019re idealistic, empathetic, and believe in the goodness of people. You\u2019re an INFP\u2014compassionate, creative, and a dreamer at heart."),
    ],
    "quiz_201.json": [
        ("You go with the flow when it comes to food. You\u2019re just as happy eating a food truck taco as a five-star meal, and you never plan where to eat\u2014you let your mood (or a friend\u2019s suggestion) guide you. You love trying whatever\u2019s in season and即兴 cooking with whatever\u2019s in the fridge. Your food personality is flexible, easygoing, and always up for a surprise. You're an ESFP\u2014spontaneous, fun-loving, and the life of any impromptu meal.",
         "You go with the flow when it comes to food. You\u2019re just as happy eating a food truck taco as a five-star meal, and you never plan where to eat\u2014you let your mood (or a friend\u2019s suggestion) guide you. You love trying whatever\u2019s in season and improvising with whatever\u2019s in the fridge. Your food personality is flexible, easygoing, and always up for a surprise. You're an ESFP\u2014spontaneous, fun-loving, and the life of any impromptu meal."),
    ],
    "quiz_204.json": [
        ("Your hidden love language is future-focused inspiration\u2014you bond by imagining shared possibilities, from travel plans to life goals. You激励 others to dream bigger, and your care shines in how you remember their aspirations. You\u2019re an ENFP, turning ordinary moments into adventures of the heart.",
         "Your hidden love language is future-focused inspiration\u2014you bond by imagining shared possibilities, from travel plans to life goals. You inspire others to dream bigger, and your care shines in how you remember their aspirations. You\u2019re an ENFP, turning ordinary moments into adventures of the heart."),
    ],
}


# ---------- Big-block translations (entire question blocks) ----------

# quiz_110.json — Roblox adventure quiz, 12 questions, 4 options each
QUIZ_110_BLOCKS = [
    # Q0
    ("You spawn in a new Roblox server with no instructions. You first...",
     [
         ("Immediately gather tools and materials from the ground to secure survival needs", "S"),
         ("Rush toward other players nearby, waving to team up and explore unknown areas together", "E"),
         ("Start guessing the world\u2019s hidden storyline, looking for possible secret entrances", "N"),
         ("Find a hidden corner first, observing the environment layout and other players\u2019 actions", "I"),
     ]),
    # Q1
    ("A player asks you to help build a complex structure but you don\u2019t know the tools. You...",
     [
         ("Empathize with their struggle, learn as you help, and encourage them to try together", "F"),
         ("Try mixing different tools, creating unexpected designs", "P"),
         ("Quickly look up tutorials or find logical patterns, finishing the build efficiently", "T"),
         ("Strictly follow the player\u2019s step-by-step instructions, no extra changes", "J"),
     ]),
    # Q2
    ("You find a locked chest in a dark cave. You decide to...",
     [
         ("Silently try different password combinations on your own, not wanting to be disturbed", "I"),
         ("Use the pickaxe you\u2019re carrying to smash the chest open and grab the items inside", "S"),
         ("Call all nearby players over to figure out how to open it together and share the treasure", "E"),
         ("First study the patterns on the chest and the surrounding symbols, deducing the puzzle", "N"),
     ]),
    # Q3
    ("A server event lets you choose between rescuing a trapped player or winning a rare item. You...",
     [
         ("Analyze the value of both, grab the item first, then come back to rescue the player", "T"),
         ("Prioritize rushing over to rescue the player, deal with the item later", "F"),
         ("Change your route on the fly, improvising and choosing what you want to do in the moment", "P"),
         ("Stick to your pre-planned route, finish the task first, then handle the emergency", "J"),
     ]),
    # Q4
    ("You\u2019re hosting a Roblox party for friends. You focus on...",
     [
         ("Design a fictional party storyline where everyone plays different roles", "N"),
         ("Sit quietly on the side, watching your friends play on their own", "I"),
         ("Organize cooperative mini-games for everyone, focused on real interaction", "S"),
         ("Proactively chat with every friend, energizing the whole atmosphere", "E"),
     ]),
    # Q5
    ("Your Roblox character gets stuck in a glitch. You respond by...",
     [
         ("First try every operation you can think of, slowly finding a solution", "J"),
         ("Immediately call other players over to help, complaining about the glitch together", "E"),
         ("Use the glitch to explore hidden areas of the map, discovering new ways to play", "P"),
         ("Record the glitch details and report them to the game developers", "T"),
     ]),
    # Q6
    ("You\u2019re tasked with designing a new Roblox game level. You start by...",
     [
         ("First draw a detailed level layout, marking the position of every item", "S"),
         ("Imagine the emotional experience players will have, designing an immersive storyline", "F"),
         ("Drag and drop components directly in the editor, adjusting creatively as you go", "N"),
         ("Research popular level designs first, borrowing from successful patterns", "T"),
     ]),
    # Q7
    ("A stranger in the server keeps stealing your resources. You...",
     [
         ("Send a friendly message, proposing to share resources and develop together", "F"),
         ("Immediately set up traps and hide your resources to prevent further theft", "J"),
         ("Randomly switch to another server, not wanting to waste time arguing", "P"),
         ("Analyze their behavior patterns, then devise a strategy to get your resources back", "T"),
     ]),
    # Q8
    ("You unlock a secret ending in a Roblox story game. You...",
     [
         ("Screenshot and share on social media, telling all your friends about your discovery", "E"),
         ("Replay it repeatedly, exploring every possible branch of the storyline", "S"),
         ("Quietly savor the deeper meaning of the ending on your own, telling no one", "I"),
         ("Write a wild-theory analysis about the ending, guessing the game\u2019s future plot", "N"),
     ]),
    # Q9
    ("You\u2019re playing a Roblox survival game during a storm. You...",
     [
         ("Immediately build a sturdy shelter to ensure your own safety", "J"),
         ("Risk going out to collect rare materials during the storm, betting on luck", "P"),
         ("Worry about other players\u2019 safety, actively inviting them into your shelter", "F"),
         ("Observe the storm\u2019s movement pattern, planning your next course of action", "T"),
     ]),
    # Q10
    ("Your friend asks for help choosing a Roblox avatar. You...",
     [
         ("Recommend practical outfits that match their style, easy for in-game movement", "S"),
         ("Help them design a personalized look with a unique backstory", "N"),
         ("Let them choose themselves, saying as long as they like it that\u2019s what matters", "I"),
         ("Show them several popular looks, letting them pick the most eye-catching one", "E"),
     ]),
    # Q11
    ("You finish a Roblox game achievement. You next...",
     [
         ("Immediately start the next challenge, working through every achievement on schedule", "J"),
         ("Casually open a new game, see if there\u2019s anything fun inside", "P"),
         ("Review the playthrough with friends, sharing tips", "F"),
         ("Analyze the playthrough data, summarizing the most efficient clearing method", "T"),
     ]),
]

# quiz_177.json — Travel Personality, 12 questions, 4 options each
QUIZ_177_BLOCKS = [
    ("Before setting off on a trip, you usually...",
     [
         ("Only set a general direction, then plan flexibly when you arrive", "P"),
         ("Make a detailed itinerary and backup plans", "J"),
         ("Research travel tips alone, quietly preparing", "I"),
         ("Gather friends to plan together, sharing the excitement", "E"),
     ]),
    ("In an unfamiliar city, you prefer to...",
     [
         ("Wander aimlessly, discovering unexpected surprises", "N"),
         ("Browse the local market, chatting with the vendors", "E"),
         ("Check off must-visit spots from the map", "S"),
         ("Find a quiet corner to watch the people pass by", "I"),
     ]),
    ("When facing a language barrier during travel, you...",
     [
         ("Open a translation app for accurate communication", "T"),
         ("Go with the flow, trusting that it will work out", "P"),
         ("Use body language and smiles to communicate", "F"),
         ("Download an offline dictionary in advance to prepare", "J"),
     ]),
    ("When choosing travel souvenirs, you tend to...",
     [
         ("Pick symbolic handicrafts", "N"),
         ("Only buy items of personal value to you", "T"),
         ("Go for practical local specialties", "S"),
         ("Bring gifts for friends and family to share the joy", "F"),
     ]),
    ("For travel accommodation, you choose...",
     [
         ("A uniquely designed specialty stay", "N"),
         ("An independent guesthouse, enjoying private space", "I"),
         ("A lively hostel, easy to meet travel companions", "E"),
         ("A well-equipped chain hotel", "S"),
     ]),
    ("When facing sudden weather changes (like rain), you...",
     [
         ("Stick to the original plan and head out in the rain", "J"),
         ("Feel that a walk in the rain has its own charm", "F"),
         ("Switch to an indoor attraction on the fly", "P"),
         ("Worry about how it affects the trip\u2019s efficiency", "T"),
     ]),
    ("While traveling, how do you usually plan your day?",
     [
         ("Fill the schedule, efficiently checking off spots", "J"),
         ("Sleep until you wake up naturally, plan based on mood", "P"),
         ("Pay close attention to every detailed experience", "S"),
         ("Imagine the stories of the next destination", "N"),
     ]),
    ("During the trip, what do you enjoy more?",
     [
         ("Immersing yourself in the scenery alone", "I"),
         ("Analyzing the local historical and cultural background", "T"),
         ("Sharing feelings with your travel companions", "E"),
         ("Feeling the atmosphere of local life", "F"),
     ]),
    ("When choosing a travel destination, you prioritize...",
     [
         ("Off-the-beaten-path places you\u2019ve discovered yourself", "I"),
         ("Well-established routes with clear travel guides", "J"),
         ("Popular spots recommended by friends", "E"),
         ("Exploratory journeys full of the unknown", "P"),
     ]),
    ("After the trip ends, you...",
     [
         ("Write a private journal to record your feelings", "I"),
         ("Organize practical travel tips for others to reference", "S"),
         ("Post on social media to share photos and stories", "E"),
         ("Create travel reflections or a scrapbook", "N"),
     ]),
    ("When making decisions during travel, you tend to...",
     [
         ("Set rules in advance to avoid disagreements", "J"),
         ("Listen to everyone\u2019s opinion before deciding", "F"),
         ("Decide flexibly on the fly based on the situation", "P"),
         ("Weigh the pros and cons, then make a rational choice", "T"),
     ]),
    ("What satisfies you most during a trip?",
     [
         ("A whole new imagination and understanding of the world", "N"),
         ("Solving complex problems during the journey", "T"),
         ("Feeling the warm connection between people", "F"),
         ("Experiencing the authentic details of local life", "S"),
     ]),
]

# quiz_182.json — Travel Style, 12 questions, 4 options each
QUIZ_182_BLOCKS = [
    ("When choosing accommodation, you prefer...",
     [
         ("A lively youth hostel, easy to meet new friends", "E"),
         ("A quiet independent guesthouse, enjoying private space", "I"),
         ("A well-equipped chain hotel, focused on comfort", "S"),
         ("A themed boutique guesthouse, full of unique design", "N"),
     ]),
    ("Planning a trip, you usually...",
     [
         ("Only set a general destination, then explore daily based on mood", "P"),
         ("Make a detailed itinerary in advance, including a daily schedule", "J"),
         ("Compare multiple platforms, choosing the most cost-effective option", "T"),
         ("Prioritize your companions\u2019 interests, making sure everyone has fun", "F"),
     ]),
    ("Your favorite travel activity is...",
     [
         ("Reading in a quiet caf\u00e9, watching local life", "I"),
         ("Joining local markets or festivals, blending into the crowd", "E"),
         ("Visiting history museums or ancient sites, learning the specific history", "S"),
         ("Hiking up a mountain to see the sunrise, feeling the grandeur of nature", "N"),
     ]),
    ("When selecting a destination, you value...",
     [
         ("Whether there are unknown surprises, enjoying improvising and discovering new places", "P"),
         ("How friendly the local residents are, hoping for warm interactions", "F"),
         ("Transportation convenience and safety index, let the data speak", "T"),
         ("Attraction opening hours and best visiting seasons, planning in advance", "J"),
     ]),
    ("If your flight is delayed, you...",
     [
         ("Pull out a backup plan, act on the alternative", "J"),
         ("Go with the flow, treating it as part of the travel experience", "P"),
         ("Calmly analyze the reason, quickly find a substitute", "T"),
         ("Comfort your travel companions\u2019 emotions, figure out a solution together", "F"),
     ]),
    ("You prefer to travel with...",
     [
         ("Alone, free to arrange your schedule, undisturbed", "I"),
         ("A group of friends, lively and fun, sharing experiences", "E"),
         ("Family, feeling more at ease with familiar people", "S"),
         ("Like-minded travel companions, able to exchange deep thoughts", "N"),
     ]),
    ("How do you record travel memories?",
     [
         ("Post on social media, sharing in real-time with friends", "E"),
         ("Quietly keep it in mind, occasionally looking through photos to reminisce", "I"),
         ("Use a camera to take detailed photos, recording specific details", "S"),
         ("Write a travel journal, recording feelings and thoughts", "N"),
     ]),
    ("Choosing transportation, you tend to...",
     [
         ("Consider whether companions are comfortable, choosing what everyone likes", "F"),
         ("Compare speed and price, choosing the optimal combination", "T"),
         ("Book direct flights in advance to save time", "J"),
         ("Randomly choose a train or bus, enjoying the scenery along the way", "P"),
     ]),
    ("Your attitude towards travel food is...",
     [
         ("Experience fusion cuisine, feeling innovation and cultural collision", "N"),
         ("Try local specialty snacks, focusing on flavor and texture", "S"),
         ("Dine with local residents, listening to their food stories", "E"),
         ("Find a quiet little shop, taste it alone without being disturbed", "I"),
     ]),
    ("How much preparation do you do before a trip?",
     [
         ("Bring only a small amount of luggage, buy whatever you need locally", "P"),
         ("Make a detailed list, pack all the essentials", "J"),
         ("Research local weather and customs, make practical preparations", "T"),
         ("Chat with friends who\u2019ve been there, getting personal advice", "F"),
     ]),
    ("You prefer which travel weather?",
     [
         ("Quiet autumn days, suitable for walking alone and thinking", "I"),
         ("Lively summer days, perfect for outdoor parties", "E"),
         ("Changing weather, like rainbows after rain or misty landscapes", "N"),
         ("Clear and stable weather, good for outdoor activities", "S"),
     ]),
    ("After the trip, you...",
     [
         ("Leave them aside, pulling them out when you want to reminisce", "P"),
         ("Organize photos and souvenirs, archiving them into a travel handbook", "J"),
         ("Summarize the pros and cons of this trip, for next time\u2019s reference", "T"),
         ("Share heartwarming stories from the trip with friends and family", "F"),
     ]),
]


def apply_replacements(data, pairs):
    """Walk a JSON structure and replace exact string occurrences."""
    def walk(obj):
        if isinstance(obj, str):
            for old, new in pairs:
                if old in obj:
                    obj = obj.replace(old, new)
            return obj
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        return obj
    return walk(data)


def replace_block(data, blocks):
    """Replace data['questions'] with a fully translated list of question dicts.
    Keeps original order. Each block is (question_text, [(opt_text, score), ...]).
    """
    new_qs = []
    for i, (q_text, opts) in enumerate(blocks):
        opts_out = [{"text": t, "score": s} for t, s in opts]
        new_qs.append({"text": q_text, "options": opts_out})
    if "questions" in data:
        data["questions"] = new_qs
    return data


def process_file(filename, pairs=None, blocks=None, block_target="questions"):
    path = os.path.join(QUIZ_DIR, filename)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if pairs:
        data = apply_replacements(data, pairs)
    if blocks:
        data = replace_block(data, blocks)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def main():
    # Small one-off translations
    for fname, pairs in SMALL_MAP.items():
        process_file(fname, pairs=pairs)

    # Big blocks
    process_file("quiz_110.json", blocks=QUIZ_110_BLOCKS)
    process_file("quiz_177.json", blocks=QUIZ_177_BLOCKS)
    process_file("quiz_182.json", blocks=QUIZ_182_BLOCKS)

    # Sanity: count remaining Chinese characters in production files
    cn_count = 0
    cn_files = []
    for name in sorted(os.listdir(QUIZ_DIR)):
        if not (name.startswith("quiz_") and name.endswith(".json")):
            continue
        full = os.path.join(QUIZ_DIR, name)
        if not os.path.isfile(full):
            continue
        with open(full, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except Exception:
                continue
        for path, val in walk_strings(data):
            if isinstance(val, str) and CN.search(val):
                cn_count += 1
                cn_files.append((name, path, val))
    print(f"\nRemaining Chinese: {cn_count}")
    for f, p, v in cn_files:
        print(f"  {f}  {p}  -> {v[:100]}")


def walk_strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from walk_strings(item, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}" if path else k
            yield from walk_strings(v, child)


if __name__ == "__main__":
    main()
