import json
import random
import re
from datetime import datetime
from difflib import SequenceMatcher

import requests
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.rule import Rule
from rich.text import Text

MODEL = "qwen2.5:1.5b-instruct"
API_URL = "http://localhost:11434/api/generate"
REQUEST_TIMEOUT = 150
console = Console()

FALLBACK_QUESTS = {
    "indoors": [
        {"title": "A Window to the World", "steps": ["Find a comfortable spot by a window, if one is available.", "Observe the sky, light, clouds, or activity you can see from there.", "Name three details you usually overlook; if no window is available, observe three details in your room."], "success_goal": "Identify three details you had not paid attention to before.", "kind": "observation", "minutes": 10},
        {"title": "Make Something from What You Have", "steps": ["Look at materials or ordinary objects already within reach.", "Choose one safe, simple thing you can make, arrange, or improve.", "Create it, or sketch a plan if you lack the needed materials."], "success_goal": "Make or sketch one useful or creative idea.", "kind": "creative", "minutes": 15},
        {"title": "A Memory Worth Sharing", "steps": ["Recall a positive memory involving someone you know.", "Think of three details that made the moment memorable.", "If comfortable, tell that person about the memory or write it down."], "success_goal": "Recall three details from a meaningful memory.", "kind": "connection", "minutes": 10},
        {"title": "The Everyday Food Explorer", "steps": ["Check which ingredients are already available and safe to use.", "Think of a simple snack or drink that needs no cooking, if possible.", "Prepare it safely, or write down a recipe using available ingredients."], "success_goal": "Make a simple snack or create a realistic recipe from available ingredients.", "kind": "food", "minutes": 15},
        {"title": "The Sound Detective", "steps": ["Sit comfortably and listen without using your phone.", "Notice three different sounds around you.", "Describe how the sounds differ in rhythm, volume, or distance."], "success_goal": "Identify and describe three distinct sounds.", "kind": "observation", "minutes": 10},
        {"title": "Invent a Tiny Game", "steps": ["Invent a simple game that needs no special equipment.", "Write down three clear rules.", "Check whether another person could understand how to play, or test the rules yourself."], "success_goal": "Create a game with three understandable rules.", "kind": "creative", "minutes": 15},
    ],
    "outdoor": [
        {"title": "Watch the Sky Change", "steps": ["From your own outdoor space, choose a comfortable and safe spot.", "Observe the sky, clouds, or changing light without using your phone.", "Notice three details; if the sky is not visible, observe nearby plants or everyday activity instead."], "success_goal": "Identify three details in your surroundings.", "kind": "nature", "minutes": 10},
        {"title": "A Walk with Fresh Eyes", "steps": ["If safe and practical, walk along a familiar route in suitable conditions.", "Notice details you usually pass without attention.", "Remember three things that caught your eye; if you cannot go for a walk, do this from your own outdoor space."], "success_goal": "Notice three details you normally overlook.", "kind": "movement", "minutes": 15},
        {"title": "Your Tiny Nature Study", "steps": ["Observe a plant or another natural feature from a safe, comfortable spot.", "Notice its shape, texture, and any movement around it without disturbing it.", "Come up with one question you would like to investigate."], "success_goal": "Notice three details and form one question.", "kind": "nature", "minutes": 10},
        {"title": "The Sunset Pause", "steps": ["If it is a suitable time and the sky is visible, find a safe place to observe it.", "Notice changes in colour, light, and cloud shapes.", "If sunset is not happening now or the sky is obscured, observe another detail in your surroundings instead."], "success_goal": "Notice three changes or details in the sky or surroundings.", "kind": "nature", "minutes": 10},
        {"title": "A Familiar Place, Newly Seen", "steps": ["Stay in a familiar, safe outdoor area.", "Look for three details you have not previously paid much attention to.", "Choose one and explain what makes it interesting."], "success_goal": "Discover three overlooked details in a familiar place.", "kind": "exploration", "minutes": 15},
        {"title": "Plan a Meal from the Market", "steps": ["Think of a simple dish you can prepare at home and list its ingredients.", "Check what you already have and estimate what else you would need.", "If a familiar market is open, accessible, and within your budget, plan a short shopping trip for another time."], "success_goal": "Create a practical ingredient list and plan.", "kind": "food", "minutes": 15},
    ],
}


def show_banner():
    console.clear()
    title = Text()
    title.append("GEN", style="bold bright_cyan")
    title.append("QUEST", style="bold bright_magenta")
    title.append("\nYour world. Your next adventure.", style="italic white")
    console.print()
    console.print(Panel(Align.center(title), border_style="bright_cyan", padding=(1, 4)))
    console.print(Align.center("[dim]AI gives you a quest. The real world is your playground.[/dim]"))
    console.print()


def numbered_menu(title, options):
    console.print(f"\n[bold]{title}[/bold]")
    for number, label in enumerate(options, start=1):
        console.print(f"  [cyan]{number}[/cyan]  {label}")
    return IntPrompt.ask("Choose an option", choices=[str(i) for i in range(1, len(options) + 1)])


def ask_profile():
    console.print(Rule("[bold cyan]YOUR ADVENTURE[/bold cyan]"))
    location = Prompt.ask("Where do you live?", choices=["village", "town", "city"], default="town")
    age_choice = numbered_menu("Choose your age range:", ["Under 13", "13–17", "18–24", "25–39", "40–59", "60+"])
    age_range = {1: "under 13", 2: "13-17", 3: "18-24", 4: "25-39", 5: "40-59", 6: "60+"}[age_choice]
    role_choice = numbered_menu("What best describes you?", ["Student", "Working", "Other"])
    role = {1: "student", 2: "working", 3: "other"}[role_choice]
    duration = IntPrompt.ask("\nHow many minutes do you have?", default=20)
    while not 5 <= duration <= 120:
        console.print("[yellow]Please choose between 5 and 120 minutes.[/yellow]")
        duration = IntPrompt.ask("Available minutes", default=20)
    mood_choice = numbered_menu("What kind of experience sounds interesting?", ["Explore or discover something", "Create or make something", "Move or experience nature", "Connect with people", "Surprise me"])
    mood = {1: "exploration and discovery", 2: "creativity and making", 3: "movement and nature", 4: "human connection", 5: "a surprising mix of experiences"}[mood_choice]
    place_choice = numbered_menu("Where can you comfortably complete a quest?", ["Indoors only", "My own outdoor space", "Familiar neighbourhood", "Any familiar, safe place"])
    place = {1: "indoors only", 2: "own outdoor space", 3: "familiar neighbourhood", 4: "any familiar, safe place"}[place_choice]
    interests = Prompt.ask("\nWhat are you interested in? (e.g. sky, cooking, nature, learning, people)", default="anything").strip()[:200] or "anything"
    energy_choice = numbered_menu("What is your energy level right now?", ["Low — something calm", "Medium — something engaging", "High — something active"])
    energy = {1: "low; prefer calm activities", 2: "medium; prefer engaging activities", 3: "high; open to active activities"}[energy_choice]
    limitations = Prompt.ask("\nAny access needs or limitations to consider? (optional)", default="none").strip()[:200] or "none"
    return {
        "location": location, "age_range": age_range, "role": role,
        "duration": duration, "mood": mood, "place": place,
        "interests": interests, "energy": energy, "limitations": limitations,
        "local_time": datetime.now().astimezone().strftime("%A, %I:%M %p"),
    }


def fallback_for_profile(profile):
    place = profile["place"]
    if place == "indoors only":
        candidates = list(FALLBACK_QUESTS["indoors"])
    elif place == "own outdoor space":
        candidates = list(FALLBACK_QUESTS["outdoor"])
    elif place == "familiar neighbourhood":
        candidates = list(FALLBACK_QUESTS["outdoor"])
    else:
        candidates = FALLBACK_QUESTS["indoors"] + FALLBACK_QUESTS["outdoor"]

    interest = profile["interests"].lower()
    mood = profile["mood"].lower()

    def score(quest):
        text = (quest["title"] + " " + " ".join(quest["steps"]) + " " + quest["kind"]).lower()
        value = sum(2 for word in re.findall(r"[a-z]+", interest) if len(word) > 3 and word in text)
        if "creativ" in mood and quest["kind"] == "creative": value += 2
        if "nature" in mood and quest["kind"] == "nature": value += 2
        if "connect" in mood and quest["kind"] == "connection": value += 2
        if "explor" in mood and quest["kind"] in {"exploration", "observation"}: value += 2
        if profile["energy"].startswith("low") and quest["kind"] == "movement": value -= 1
        return value

    random.shuffle(candidates)
    candidates.sort(key=score, reverse=True)
    chosen, used_kinds = [], set()
    for quest in candidates:
        if quest["kind"] not in used_kinds:
            chosen.append(dict(quest))
            used_kinds.add(quest["kind"])
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        for quest in candidates:
            if len(chosen) == 3:
                break
            if quest not in chosen:
                chosen.append(dict(quest))
    for quest in chosen:
        quest["estimated_minutes"] = min(profile["duration"], max(5, int(quest.get("minutes", 10))))
    return chosen[:3]


def strip_json_fence(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def validate_quest(quest, profile):
    if not isinstance(quest, dict):
        return False
    title, steps, goal = quest.get("title"), quest.get("steps"), quest.get("success_goal")
    minutes = quest.get("estimated_minutes", profile["duration"])
    if not isinstance(title, str) or not title.strip() or len(title) > 90:
        return False
    if not isinstance(steps, list) or len(steps) != 3:
        return False
    if not all(isinstance(s, str) and 5 <= len(s.strip()) <= 280 for s in steps):
        return False
    if not isinstance(goal, str) or not 8 <= len(goal.strip()) <= 240:
        return False
    if not isinstance(minutes, (int, float)) or not 5 <= int(minutes) <= profile["duration"]:
        return False

    full_text = " ".join([title, *steps, goal]).lower()
    unsafe_patterns = [
        r"\b(climb|climbing|trespass|trespassing|enter abandoned|railway track|train track)\b",
        r"\b(pond|lake|river|well)\b",
        r"\b(approach|follow|talk to) strangers\b",
        r"\b(knife|power tool|chainsaw|open flame|fireworks)\b",
    ]
    if any(re.search(pattern, full_text) for pattern in unsafe_patterns):
        return False

    if profile["place"] == "indoors only":
        outdoor_patterns = [
            r"\b(go outside|go outdoors|walk outside|outdoor walk|visit a market|farmer.?s market)\b",
            r"\b(park|garden|neighbourhood walk|neighborhood walk|go to the shop|go shopping)\b",
        ]
        if any(re.search(pattern, full_text) for pattern in outdoor_patterns):
            return False
    elif profile["place"] == "own outdoor space":
        away_patterns = [r"\b(go to the market|visit a market|go shopping|walk around the neighbourhood|walk around the neighborhood)\b"]
        if any(re.search(pattern, full_text) for pattern in away_patterns):
            return False

    if profile["duration"] <= 15:
        infeasible_patterns = [
            r"\b(buy ingredients and cook|visit .*market.*prepare|shop for ingredients and cook)\b",
            r"\b(travel to .* and return|visit multiple locations)\b",
        ]
        if any(re.search(pattern, full_text) for pattern in infeasible_patterns):
            return False

    quest["title"] = title.strip()
    quest["steps"] = [s.strip() for s in steps]
    quest["success_goal"] = goal.strip()
    quest["estimated_minutes"] = int(minutes)
    return True


def are_distinct(quests):
    for i in range(len(quests)):
        for j in range(i + 1, len(quests)):
            a = (quests[i]["title"] + " " + " ".join(quests[i]["steps"])).lower()
            b = (quests[j]["title"] + " " + " ".join(quests[j]["steps"])).lower()
            if SequenceMatcher(None, a, b).ratio() > 0.78:
                return False
            if quests[i]["title"].lower() == quests[j]["title"].lower():
                return False
    return True


def generate_quests(profile):
    prompt = f'''
You are GenQuest, an imaginative designer of real-world quests.
Help people stop looking at screens and experience real life.

USER PROFILE
- Local time: {profile["local_time"]}
- Environment: {profile["location"]}
- Age range: {profile["age_range"]}
- Occupation: {profile["role"]}
- Available time: {profile["duration"]} minutes
- Interest: {profile["interests"]}
- Preferred experience: {profile["mood"]}
- Setting constraint: {profile["place"]}
- Energy: {profile["energy"]}
- Access needs or limitations: {profile["limitations"]}

Create exactly THREE genuinely different, achievable real-world quests.
Ideas include observing the sky, noticing nature, making something from
available materials, preparing a very simple snack, learning a practical
skill, or connecting with someone the user already knows. Invent fresh ideas;
do not merely reword the same activity three times.

NON-NEGOTIABLE CONSTRAINTS
- If setting is "indoors only", every step must be completable indoors.
  Do not require a window, kitchen, ingredients, or equipment; give an
  alternative if something may not be available.
- If setting is "own outdoor space", do not require leaving that property.
- If setting is "familiar neighbourhood", only suggest familiar, public,
  ordinary places and only if the user chooses to go.
- Never assume a market is open, a sky object is visible, weather is good,
  or equipment or ingredients are available. Do not claim live information.
- Each quest must be achievable within {profile["duration"]} minutes.
- When time is 15 minutes or less, do not propose shopping plus cooking,
  travel, or a long multi-stage activity.
- Respect access needs and energy. Do not stereotype age or occupation.
- Never suggest dangerous roads, climbing, trespassing, isolated places,
  bodies of water, approaching strangers, or hazardous tools.
- No phone use is required while doing the quest.
- Each quest needs a short title, exactly 3 clear practical steps, and one
  measurable success goal. Avoid vague or poetic instructions.
- Return valid JSON only in this shape:
{{"quests":[{{"title":"Title","steps":["Step one","Step two","Step three"],"success_goal":"Measurable goal","estimated_minutes":{profile["duration"]}}}]}}
Return exactly three quest objects.
'''
    try:
        response = requests.post(
            API_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False, "format": "json", "think": False,
                  "options": {"temperature": 0.85, "num_predict": 1100, "num_ctx": 3072}},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = json.loads(strip_json_fence(response.json().get("response", "")))
        quests = data.get("quests")
        if not isinstance(quests, list) or len(quests) != 3:
            raise ValueError("Model did not return exactly three quests.")
        valid = [quest for quest in quests if validate_quest(quest, profile)]
        if len(valid) != 3 or not are_distinct(valid):
            raise ValueError("Generated quests failed validation or were too similar.")
        return valid
    except (requests.RequestException, ValueError, TypeError, KeyError):
        console.print("\n[yellow]The model output wasn't usable. Using local fallback quests instead.[/yellow]")
        return fallback_for_profile(profile)


def display_quests(quests):
    console.print()
    console.print(Rule("[bold bright_magenta]CHOOSE YOUR QUEST[/bold bright_magenta]"))
    for index, quest in enumerate(quests, start=1):
        steps = "\n\n".join(f"[cyan]{n}.[/cyan] {step}" for n, step in enumerate(quest["steps"], start=1))
        body = f"{steps}\n\n[bold green]SUCCESS GOAL[/bold green]\n{quest['success_goal']}"
        console.print(Panel(body, title=f"[bold]{index}. {quest['title']}[/bold]",
                            subtitle=f"{quest['estimated_minutes']} minutes",
                            border_style="bright_cyan" if index == 1 else "magenta", padding=(1, 2)))
    choice = IntPrompt.ask("\nWhich quest will you take?", choices=["1", "2", "3"])
    return quests[choice - 1]


def reflect():
    console.print()
    console.print(Rule("[bold green]WELCOME BACK[/bold green]"))
    reflection = Prompt.ask("\nWhat did you discover, create, or experience?", default="I completed my quest").strip()
    console.print(Panel("[bold green]QUEST COMPLETE[/bold green]\n\n"
                        "You used technology to find a reason to step away from it.\n"
                        "There's always something new to notice in the world around you.",
                        border_style="green", padding=(1, 2)))
    if reflection:
        console.print(f"\n[dim]Your reflection: {reflection}[/dim]")


def main():
    show_banner()
    profile = ask_profile()
    console.print(Panel("[bold cyan]Generating three adventures with your local AI...[/bold cyan]\n"
                        "[dim]No cloud AI API is used.[/dim]", border_style="cyan"))
    quests = generate_quests(profile)
    selected = display_quests(quests)
    console.print(Panel(f"[bold yellow]Your quest: {selected['title']}[/bold yellow]\n\n"
                        "Remember the steps, put your screen away, and experience it.\n"
                        "[dim]Choose what feels safe and comfortable. You can stop at any time.[/dim]",
                        border_style="yellow"))
    Prompt.ask("\n[bold cyan]Press Enter when you return from your quest[/bold cyan]", default="")
    reflect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Adventure paused. You can return anytime.[/yellow]")
