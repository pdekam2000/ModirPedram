"""YouTube Shorts channel brief: Science That Feels Impossible."""

from __future__ import annotations

CHANNEL_NAME = "Science That Feels Impossible"
CHANNEL_SLUG = "science_that_feels_impossible"
BRIEF_VERSION = "youtube_science_impossible_v1"

DEFAULT_DURATION_SECONDS = 45
YOUTUBE_DEFAULT_DURATION_SECONDS = 45
INSTAGRAM_DEFAULT_DURATION_SECONDS = 45
TIKTOK_DEFAULT_DURATION_SECONDS = 30

def default_duration_for_platform(platform: str) -> int:
    normalized = str(platform or "").strip().lower()
    if normalized in {"youtube_shorts", "youtube"}:
        return YOUTUBE_DEFAULT_DURATION_SECONDS
    if normalized in {"instagram_reels", "instagram"}:
        return INSTAGRAM_DEFAULT_DURATION_SECONDS
    if normalized == "tiktok":
        return TIKTOK_DEFAULT_DURATION_SECONDS
    return DEFAULT_DURATION_SECONDS

PRESENTER_DIRECTIVE = (
    "Recurring female science presenter: beautiful, confident, intelligent-looking, charismatic, "
    "elegant, modern, slightly glamorous, professionally styled, expressive but not exaggerated. "
    "Stylish modern science presenter / futuristic journalist / premium documentary host wardrobe. "
    "Visual attraction from beauty, confidence, styling, cinematic lighting, camera presence, and "
    "elegant fashion — never explicit or overly revealing. Maintain the same face, hair, styling, "
    "and wardrobe continuity across videos whenever character consistency is supported."
)

CONTENT_PILLARS: tuple[str, ...] = (
    "Human body mysteries",
    "Brain and perception",
    "Space and astrophysics",
    "Extreme physics",
    "Strange biology",
    "Evolution",
    "Deep ocean mysteries",
    "Dangerous natural phenomena",
    "Time and relativity",
    "Quantum phenomena explained simply",
    "Death and biological processes",
    "Survival science",
    "Strange animals",
    "Hidden processes inside the human body",
    "Scientific facts that sound fake but are real",
    "Cosmic disasters",
    "Future science and technology",
    "Psychology and perception experiments",
    "Microscopic worlds",
    "Earth science and planetary phenomena",
)

TOPIC_SUMMARY = f"""Science That Feels Impossible — premium cinematic science Shorts (40–45 seconds, English).

One surprising, strange, mysterious, or visually powerful scientific fact per video. Intelligent, cinematic, mysterious, modern, visually addictive.

{PRESENTER_DIRECTIVE}

STRUCTURE:
0–2s: Powerful hook — surprising statement, question, contradiction, or unbelievable fact. NEVER "Did you know?", "Hello everyone", or long intros.
2–8s: Setup — presenter introduces the phenomenon in one or two short spoken sentences.
8–22s: Visual explanation — holographic displays, animated diagrams, macro/micro footage, space simulations, body visualizations, molecular animation, futuristic lab environments. Presenter integrated dynamically, not static split-screen.
22–29s: Twist/payoff — strangest, most surprising detail; reward viewers who watch to the end.
Final 2–3s: Natural varied CTA when appropriate (e.g. "Follow for science that sounds impossible.").

VISUAL STYLE: Premium cinematic science documentary — futuristic studio, dramatic lighting, depth, realistic scientific visualization, high contrast, strong motion.

SCIENTIFIC ACCURACY: Never invent statistics, experiments, or discoveries. Use "Scientists think…", "One leading theory suggests…", "Researchers have observed…" when uncertain.

SCRIPT: Natural spoken English, short sentences, one central idea, suspense, visual language.

FORBIDDEN: Academic textbook tone, weak hooks, politically controversial topics without scientific necessity, multiple unrelated facts, explicit content."""

PREFERRED_TOPICS = list(CONTENT_PILLARS)

FORBIDDEN_TOPICS = (
    "Overly academic or technical explanations",
    "Topics impossible to visualize",
    "Politically controversial without scientific necessity",
    "Weak first-2-second hooks",
    "Multiple unrelated facts in one Short",
    "Invented statistics or fake research",
    "Dark fantasy fictional stories",
    "Animal comedy or pet fail content",
    "Skincare or beauty routine content",
    "Generic AI explainer tone",
    "Did you know openings",
)

SCIENCE_SETTING_POOL: tuple[dict[str, str], ...] = (
    {"setting": "futuristic holographic science studio with deep blue rim light", "visual": "holographic body scan", "pillar": "Human body mysteries"},
    {"setting": "premium documentary virtual studio overlooking Earth from orbit", "visual": "space-time curvature simulation", "pillar": "Space and astrophysics"},
    {"setting": "dark cinematic lab with floating molecular models", "visual": "atomic-scale electron cloud animation", "pillar": "Extreme physics"},
    {"setting": "immersive neural visualization chamber", "visual": "brain perception filter diagram", "pillar": "Brain and perception"},
    {"setting": "deep-ocean pressure simulation environment", "visual": "bioluminescent abyss creatures", "pillar": "Deep ocean mysteries"},
    {"setting": "microscopic world scale-shift stage", "visual": "tardigrade extreme survival macro", "pillar": "Microscopic worlds"},
    {"setting": "cosmic disaster visualization dome", "visual": "solar flare hitting Earth's magnetosphere", "pillar": "Cosmic disasters"},
    {"setting": "evolutionary timeline holographic gallery", "visual": "ancient organism transformation", "pillar": "Evolution"},
    {"setting": "quantum probability field studio", "visual": "particle superposition visualization", "pillar": "Quantum phenomena explained simply"},
    {"setting": "clinical yet cinematic human biology theater", "visual": "cellular regeneration time-lapse", "pillar": "Hidden processes inside the human body"},
)

SCIENCE_FACT_POOL: tuple[dict[str, str], ...] = (
    {
        "hook": "You are glowing right now.",
        "title": "Your Body Emits Invisible Light",
        "setup": "Every second, chemical reactions inside your cells release tiny flashes of light.",
        "mechanism": "It's called bioluminescence at levels far too weak for your eyes — but real cameras can capture it.",
        "twist": "In total darkness, researchers have photographed humans shining like faint ghosts.",
        "pillar": "Human body mysteries",
    },
    {
        "hook": "You have never actually touched anything.",
        "title": "Why Atoms Never Truly Touch",
        "setup": "Your finger and the table feel solid — but at the atomic level, nothing collides.",
        "mechanism": "Electrons repel each other through electromagnetic force, creating the illusion of contact.",
        "twist": "You are always hovering on an invisible force field — contact is a lie your brain sells you.",
        "pillar": "Extreme physics",
    },
    {
        "hook": "Your brain is hiding part of reality from you.",
        "title": "The Blind Spot Your Brain Fills In",
        "setup": "There is a hole in your vision where your optic nerve connects — you should see a void.",
        "mechanism": "Your brain silently paints in missing detail using context and memory.",
        "twist": "You never notice because the lie is seamless — your mind edits reality in real time.",
        "pillar": "Brain and perception",
    },
    {
        "hook": "Time is moving differently around your body right now.",
        "title": "Gravity Slows Time Near You",
        "setup": "Einstein showed that stronger gravity literally stretches time.",
        "mechanism": "Clocks tick slower closer to massive objects — even your feet age differently from your head.",
        "twist": "GPS satellites must correct for this or your maps would drift kilometers every day.",
        "pillar": "Time and relativity",
    },
    {
        "hook": "This animal can theoretically escape aging.",
        "title": "The Jellyfish That Reverses Its Life Cycle",
        "setup": "Turritopsis dohrnii can revert to an earlier life stage under stress.",
        "mechanism": "Researchers have observed it returning to a polyp form instead of dying.",
        "twist": "Scientists call it biologically immortal — but it can still be eaten or killed.",
        "pillar": "Strange biology",
    },
    {
        "hook": "If Earth stopped for one second, almost everything would die.",
        "title": "What Happens If Earth Stops Spinning",
        "setup": "Earth spins at roughly 1,670 km/h at the equator — that motion is constant.",
        "mechanism": "Stop it instantly and everything not bolted down keeps moving at that speed.",
        "twist": "Oceans would surge in megatsunamis, winds would scour the surface — recovery would take millennia.",
        "pillar": "Earth science and planetary phenomena",
    },
    {
        "hook": "Empty space is not truly empty.",
        "title": "Quantum Foam Fills the Void",
        "setup": "Vacuum sounds like nothing — but quantum mechanics disagrees.",
        "mechanism": "Virtual particles flicker in and out of existence everywhere in space.",
        "twist": "The Casimir effect proves the vacuum has measurable energy — nothing is ever truly empty.",
        "pillar": "Quantum phenomena explained simply",
    },
    {
        "hook": "Your own face looks strange when you stare too long.",
        "title": "The Strange-Face-in-the-Mirror Effect",
        "setup": "Stare at your reflection in dim light without moving for a minute.",
        "mechanism": "Your brain, starved of new input, starts distorting familiar features.",
        "twist": "People report seeing monsters, strangers, or dead faces — all generated by their own perception.",
        "pillar": "Psychology and perception experiments",
    },
    {
        "hook": "A human falling into Jupiter would never hit ground.",
        "title": "There Is No Solid Surface on Jupiter",
        "setup": "Jupiter is mostly hydrogen and helium under crushing pressure.",
        "mechanism": "You would fall through layers of gas that grow denser until you float — crushed and cooked.",
        "twist": "Scientists think you would compress into a streak of carbon — a diamond rain might form around you.",
        "pillar": "Space and astrophysics",
    },
    {
        "hook": "Astronauts age slightly differently in orbit.",
        "title": "Time Moves Faster in Space",
        "setup": "Six months on the International Space Station changes your clock.",
        "mechanism": "Lower gravity and high speed both alter time — effects compete.",
        "twist": "Twin Scott Kelly aged microseconds less than his brother on Earth after a year in space.",
        "pillar": "Time and relativity",
    },
    {
        "hook": "Most of the universe is invisible to you.",
        "title": "Dark Matter Outweighs Everything You See",
        "setup": "Stars, planets, and galaxies — all ordinary matter — are the minority.",
        "mechanism": "Galaxies spin too fast unless invisible mass holds them together.",
        "twist": "Roughly 85% of the universe's matter may be dark — and we still cannot see it directly.",
        "pillar": "Space and astrophysics",
    },
    {
        "hook": "Your memories can be edited without you knowing.",
        "title": "False Memories Are Surprisingly Easy to Plant",
        "setup": "Psychologists have repeatedly implanted vivid memories of events that never happened.",
        "mechanism": "Suggestion, leading questions, and imagination blur the line between real and invented.",
        "twist": "Subjects confidently recall details — your most trusted memory might be a reconstruction.",
        "pillar": "Psychology and perception experiments",
    },
    {
        "hook": "The deepest place humans have explored is still mostly unknown.",
        "title": "The Mariana Trench Holds Living Secrets",
        "setup": "Challenger Deep plunges nearly 11 kilometers below the surface.",
        "mechanism": "Crushing pressure and eternal darkness — yet life thrives there.",
        "twist": "Creatures at the bottom survive pressures that would instantly crush a submarine.",
        "pillar": "Deep ocean mysteries",
    },
    {
        "hook": "Without Earth's magnetic field, life would struggle to exist.",
        "title": "The Invisible Shield Above You",
        "setup": "Earth's core generates a magnetic field stretching far into space.",
        "mechanism": "It deflects charged particles from the Sun that would strip the atmosphere.",
        "twist": "The field weakens and flips unpredictably — during reversals, more radiation reaches the surface.",
        "pillar": "Earth science and planetary phenomena",
    },
    {
        "hook": "You cannot see most of the light around you.",
        "title": "Your Eyes Catch a Tiny Slice of Reality",
        "setup": "The electromagnetic spectrum spans from radio waves to gamma rays.",
        "mechanism": "Human vision covers less than 0.003% of it — visible light is a narrow band.",
        "twist": "Snakes see infrared, bees see ultraviolet — your rainbow is a partial map of reality.",
        "pillar": "Brain and perception",
    },
    {
        "hook": "Near light speed, time nearly stops for you.",
        "title": "Relativity at Near-Light Speed",
        "setup": "Travel close to the speed of light and clocks around you race ahead.",
        "mechanism": "Special relativity slows your personal time relative to everyone else.",
        "twist": "Return to Earth and everyone you knew could be decades older — a round trip to the stars is a one-way goodbye.",
        "pillar": "Time and relativity",
    },
    {
        "hook": "Some organisms survive conditions that kill almost everything else.",
        "title": "Tardigrades Endure the Impossible",
        "setup": "These microscopic animals survive vacuum, radiation, and boiling.",
        "mechanism": "They enter cryptobiosis — replacing water in cells with protective glass-like proteins.",
        "twist": "Researchers have revived tardigrades frozen for thirty years — death is optional for them.",
        "pillar": "Microscopic worlds",
    },
    {
        "hook": "Black holes may not destroy information forever.",
        "title": "The Black Hole Information Paradox",
        "setup": "Fall into a black hole and classical physics says you are gone.",
        "mechanism": "Hawking radiation suggests black holes slowly evaporate — but where does your information go?",
        "twist": "Leading physicists still debate whether the universe preserves every bit of you — or rewrites the rules of reality.",
        "pillar": "Space and astrophysics",
    },
    {
        "hook": "Your body replaces most of itself over time.",
        "title": "You Are Not the Same Matter You Were Years Ago",
        "setup": "Cells die and regenerate constantly — skin, blood, gut lining.",
        "mechanism": "Atoms swap out through eating, breathing, and repair.",
        "twist": "Most of your body is rebuilt within years — yet you feel like the same continuous self.",
        "pillar": "Hidden processes inside the human body",
    },
    {
        "hook": "Extreme cold can stop your heart and still let you survive.",
        "title": "Hypothermia's Impossible Rescues",
        "setup": "When the body cools dramatically, metabolism slows to a near halt.",
        "mechanism": "Doctors have restarted hearts after hours underwater in freezing conditions.",
        "twist": "Under certain conditions, cold buys time — death is delayed, not cancelled.",
        "pillar": "Survival science",
    },
    {
        "hook": "Your stomach acid is strong enough to dissolve metal.",
        "title": "The Acid Bath Inside You",
        "setup": "Gastric acid runs at roughly pH 1.5 — comparable to battery acid.",
        "mechanism": "It breaks down food and kills pathogens — the stomach lining constantly renews to survive it.",
        "twist": "You carry a corrosive lake inside you — and your body rebuilds its own container every few days.",
        "pillar": "Human body mysteries",
    },
    {
        "hook": "Trees communicate through underground networks.",
        "title": "The Wood Wide Web",
        "setup": "Fungi connect root systems across entire forests.",
        "mechanism": "Trees share nutrients and chemical warning signals through mycorrhizal networks.",
        "twist": "Mother trees preferentially feed their offspring — forests behave like slow, hidden societies.",
        "pillar": "Strange biology",
    },
    {
        "hook": "A solar storm could cripple civilization tomorrow.",
        "title": "When the Sun Sends a Kill Shot",
        "setup": "Coronal mass ejections hurl billions of tons of plasma toward Earth.",
        "mechanism": "The 1859 Carrington Event set telegraph lines on fire — today we'd lose satellites and grids.",
        "twist": "Scientists warn a modern Carrington-level event could knock out power for months — we are overdue.",
        "pillar": "Cosmic disasters",
    },
    {
        "hook": "Your brain uses more energy than you think while resting.",
        "title": "The Hungry Idle Brain",
        "setup": "Even at rest, your brain burns roughly 20% of your body's energy.",
        "mechanism": "Constant signaling, memory maintenance, and prediction keep it running hot.",
        "twist": "Doing nothing is exhausting — your mind is always working, even in sleep.",
        "pillar": "Brain and perception",
    },
    {
        "hook": "Death is not a single moment inside your cells.",
        "title": "Cells Keep Living After You Die",
        "setup": "Clinical death is one threshold — biology keeps going afterward.",
        "mechanism": "Some cells remain active for hours, even days, after the heart stops.",
        "twist": "Researchers have observed gene expression shifting post-mortem — the body unwinds in stages, not all at once.",
        "pillar": "Death and biological processes",
    },
)

SCIENCE_VISUAL_HOOK_POOL: tuple[str, ...] = (
    "holographic scientific display materializes beside the presenter as she delivers the hook",
    "macro camera dives into a microscopic world while the presenter gestures toward the visualization",
    "cinematic push-in on the presenter's face as a space simulation blooms behind her",
    "molecular animation spirals around the presenter in a futuristic virtual studio",
    "dramatic rim light catches the presenter as a body-scan visualization pulses with data",
)

SCIENCE_ENDING_POOL: tuple[str, ...] = (
    "presenter holds eye contact as the final impossible detail lands — subtle CTA: follow for science that sounds impossible",
    "camera pulls back revealing the full holographic explanation as she says reality is stranger than fiction",
    "presenter turns toward the visualization for the payoff beat then back to camera with a knowing close-up",
    "freeze on the presenter's expression as the strangest fact echoes — science gets stranger from here",
)

SCIENCE_CTA_POOL: tuple[str, ...] = (
    "Follow for science that sounds impossible.",
    "Reality is stranger than fiction.",
    "Follow for another impossible fact.",
    "Science gets stranger from here.",
)


def get_youtube_channel_topic_text() -> str:
    return TOPIC_SUMMARY


def is_science_youtube_platform(target_platform: str, channel_topic: str = "") -> bool:
    platform_key = str(target_platform or "").strip().lower()
    if platform_key in {"youtube_shorts", "youtube"}:
        return True
    lowered = str(channel_topic or "").lower()
    return any(
        marker in lowered
        for marker in (
            "science that feels impossible",
            "impossible science",
            "science facts",
            "premium cinematic science",
        )
    )


def is_science_topic_text(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "science that feels impossible",
            "impossible science",
            "premium cinematic science",
            "science shorts",
        )
    )


__all__ = [
    "BRIEF_VERSION",
    "CHANNEL_NAME",
    "CHANNEL_SLUG",
    "CONTENT_PILLARS",
    "DEFAULT_DURATION_SECONDS",
    "INSTAGRAM_DEFAULT_DURATION_SECONDS",
    "TIKTOK_DEFAULT_DURATION_SECONDS",
    "YOUTUBE_DEFAULT_DURATION_SECONDS",
    "default_duration_for_platform",
    "FORBIDDEN_TOPICS",
    "PREFERRED_TOPICS",
    "PRESENTER_DIRECTIVE",
    "SCIENCE_CTA_POOL",
    "SCIENCE_ENDING_POOL",
    "SCIENCE_FACT_POOL",
    "SCIENCE_SETTING_POOL",
    "SCIENCE_VISUAL_HOOK_POOL",
    "TOPIC_SUMMARY",
    "get_youtube_channel_topic_text",
    "is_science_topic_text",
    "is_science_youtube_platform",
]
