"""Instagram educational skincare recipe pool — one recipe per Reel."""

from __future__ import annotations

from typing import Any

INSTAGRAM_CONTENT_BRIEF = """INSTAGRAM CONTENT RULES:
Each 45-second video teaches ONE specific beauty recipe.
The presenter demonstrates on camera with exact quantities.

CONTENT CATEGORIES (rotate between these):

1. FACE MASKS (most popular):
   - Clay masks for oily/acne skin
   - Honey masks for dry skin
   - Turmeric masks for brightening
   - Oat masks for sensitive skin
   - Egg white masks for pores
   - Coffee masks for dark circles
   - Yogurt masks for glow
   - Avocado masks for hydration

2. HAIR TREATMENTS:
   - Egg + olive oil mask for hair growth
   - Coconut oil + honey for damaged hair
   - Onion juice for hair loss
   - Castor oil for thicker hair
   - Rice water for shine
   - Aloe vera for scalp health

3. ACNE SOLUTIONS:
   - Tea tree + aloe spot treatment
   - Apple cider vinegar toner
   - Green tea ice cubes for redness
   - Salicylic honey treatment

4. SKIN BRIGHTENING:
   - Vitamin C serum (homemade)
   - Lemon + honey overnight mask
   - Turmeric + milk brightening paste
   - Rose water toner

5. ANTI-AGING:
   - Retinol alternative: rosehip oil
   - Collagen boost: bone broth mask
   - Eye cream: cucumber + aloe
   - Neck firming: egg white mask

6. BODY CARE:
   - Coffee body scrub
   - Sugar lip scrub
   - Coconut milk bath soak
   - Himalayan salt scrub

VIDEO STRUCTURE (45 seconds):
Clip 1 (15s):
   'Today I am making [RECIPE NAME]'
   'You need: [EXACT QUANTITIES]'
   Show all ingredients clearly
   Mix them together on camera

Clip 2 (15s):
   Apply to face/hair on camera
   'Leave for [TIME] then rinse'
   Show result/before-after hint

Clip 3 (15s):
   'This works because [SCIENCE REASON]'
   'Best for: [SKIN/HAIR TYPE]'
   'Use [FREQUENCY]: daily/weekly/monthly'
   End: 'Follow for daily beauty recipes!'

TITLE FORMAT (curiosity + benefit):
- 'This 2-Ingredient Mask Removes Dark Spots in 7 Days'
- 'Why Your Hair Grows Faster With This Kitchen Ingredient'
- 'Dermatologists Hate This $2 Acne Treatment'
- 'The Overnight Mask That Erases Wrinkles'
- 'Stop Buying Serums — Make This Instead'

QUANTITIES must be EXACT:
- '2 tablespoons raw honey'
- '1 teaspoon turmeric powder'
- '3 drops of lemon juice'
- '1/2 ripe avocado'

NEVER repeat a recipe — track in story memory.
ALWAYS end with: Follow for daily beauty recipes!"""

INSTAGRAM_RECIPE_SETTINGS: tuple[str, ...] = (
    "bright aesthetic kitchen with white marble counter and natural window light",
    "clean modern bathroom with large mirror, plants, and soft daylight",
    "minimalist vanity with glass jars, wooden tray, and fresh herbs",
    "sunlit kitchen island with ceramic bowls and linen cloth",
    "spa-style bathroom with white tiles, eucalyptus, and warm lighting",
)

INSTAGRAM_RECIPE_CTA = "Follow for daily beauty recipes!"

INSTAGRAM_RECIPE_POOL: tuple[dict[str, Any], ...] = (
    {
        "recipe_name": "Honey & Turmeric Glow Mask",
        "ingredients": ["2 tbsp honey", "1 tsp turmeric", "3 drops lemon juice"],
        "skin_benefit": "brightening, anti-inflammatory",
        "season": "all year",
        "occasion": "daily",
        "category": "face masks",
    },
    {
        "recipe_name": "Oat & Yogurt Calm Mask",
        "ingredients": ["3 tbsp plain yogurt", "2 tbsp ground oat", "1 tsp honey"],
        "skin_benefit": "soothing, barrier support",
        "season": "all year",
        "occasion": "daily",
        "category": "face masks",
    },
    {
        "recipe_name": "Green Clay Pore Refine Mask",
        "ingredients": ["2 tbsp green clay", "1 tbsp rose water", "1 tsp aloe vera gel"],
        "skin_benefit": "oil control, pore refining",
        "season": "summer",
        "occasion": "weekly",
        "category": "face masks",
    },
    {
        "recipe_name": "Egg White Lift Mask",
        "ingredients": ["1 egg white", "1 tsp lemon juice", "1/2 tsp honey"],
        "skin_benefit": "temporary firming, mattifying",
        "season": "all year",
        "occasion": "pre-party glow",
        "category": "face masks",
    },
    {
        "recipe_name": "Avocado Honey Repair Mask",
        "ingredients": ["1/2 ripe avocado", "1 tbsp honey", "1 tsp olive oil"],
        "skin_benefit": "deep hydration, nourishment",
        "season": "winter",
        "occasion": "weekly",
        "category": "face masks",
    },
    {
        "recipe_name": "Coffee Cocoa Firming Mask",
        "ingredients": ["2 tbsp coffee grounds", "1 tbsp cocoa powder", "2 tbsp yogurt"],
        "skin_benefit": "circulation, antioxidant boost",
        "season": "all year",
        "occasion": "weekly",
        "category": "face masks",
    },
    {
        "recipe_name": "Aloe Cucumber Cool Mask",
        "ingredients": ["3 tbsp aloe vera gel", "2 tbsp grated cucumber", "1 tsp witch hazel"],
        "skin_benefit": "cooling, redness relief",
        "season": "summer",
        "occasion": "daily",
        "category": "face masks",
    },
    {
        "recipe_name": "Banana Oat Soft Skin Mask",
        "ingredients": ["1/2 mashed banana", "2 tbsp oat flour", "1 tsp honey"],
        "skin_benefit": "gentle exfoliation, softness",
        "season": "all year",
        "occasion": "daily",
        "category": "face masks",
    },
    {
        "recipe_name": "Rice Water Brightening Mask",
        "ingredients": ["3 tbsp rice water", "1 tbsp honey", "1 tsp turmeric pinch"],
        "skin_benefit": "brightening, even tone",
        "season": "all year",
        "occasion": "weekly",
        "category": "brightening",
    },
    {
        "recipe_name": "Strawberry Yogurt Polish Mask",
        "ingredients": ["3 mashed strawberries", "2 tbsp yogurt", "1 tsp honey"],
        "skin_benefit": "gentle acid exfoliation, glow",
        "season": "spring",
        "occasion": "weekly",
        "category": "brightening",
    },
    {
        "recipe_name": "Papaya Enzyme Glow Mask",
        "ingredients": ["2 tbsp mashed papaya", "1 tbsp honey", "1 tsp lime juice"],
        "skin_benefit": "enzyme exfoliation, radiance",
        "season": "summer",
        "occasion": "weekly",
        "category": "brightening",
    },
    {
        "recipe_name": "Tomato Lemon Spot Mask",
        "ingredients": ["2 tbsp tomato pulp", "1 tsp lemon juice", "1 tbsp yogurt"],
        "skin_benefit": "brightening, dark spot support",
        "season": "all year",
        "occasion": "weekly",
        "category": "brightening",
    },
    {
        "recipe_name": "Tea Tree Clay Blemish Mask",
        "ingredients": ["2 tbsp bentonite clay", "1 tbsp apple cider vinegar", "2 drops tea tree oil"],
        "skin_benefit": "blemish control, oil balance",
        "season": "all year",
        "occasion": "weekly",
        "category": "acne solutions",
    },
    {
        "recipe_name": "Honey Cinnamon Spot Mask",
        "ingredients": ["2 tbsp honey", "1/4 tsp cinnamon", "1 tsp aloe vera gel"],
        "skin_benefit": "antibacterial, spot calming",
        "season": "all year",
        "occasion": "daily",
        "category": "acne solutions",
    },
    {
        "recipe_name": "Neem Yogurt Clarify Mask",
        "ingredients": ["1 tbsp neem powder", "3 tbsp yogurt", "1 tsp honey"],
        "skin_benefit": "clarifying, breakout support",
        "season": "summer",
        "occasion": "weekly",
        "category": "acne solutions",
    },
    {
        "recipe_name": "Oat Honey Blemish Calm Mask",
        "ingredients": ["2 tbsp colloidal oat", "1 tbsp honey", "2 tbsp cooled green tea"],
        "skin_benefit": "redness relief, gentle cleanse",
        "season": "all year",
        "occasion": "daily",
        "category": "acne solutions",
    },
    {
        "recipe_name": "Rosehip Night Repair Serum",
        "ingredients": ["1 tbsp rosehip oil", "1 tsp vitamin E oil", "2 drops lavender oil"],
        "skin_benefit": "repair, fine line support",
        "season": "all year",
        "occasion": "night",
        "category": "night treatments",
    },
    {
        "recipe_name": "Shea Butter Night Cream",
        "ingredients": ["2 tbsp shea butter", "1 tsp honey", "3 drops rose oil"],
        "skin_benefit": "deep overnight moisture",
        "season": "winter",
        "occasion": "night",
        "category": "night treatments",
    },
    {
        "recipe_name": "Retinol-Style Green Tea Night Mask",
        "ingredients": ["2 tbsp aloe vera gel", "1 tbsp green tea", "1 tsp honey"],
        "skin_benefit": "antioxidant overnight recovery",
        "season": "all year",
        "occasion": "night",
        "category": "night treatments",
    },
    {
        "recipe_name": "Chamomile Sleep Recovery Mask",
        "ingredients": ["3 tbsp chamomile tea", "2 tbsp honey", "1 tbsp oat flour"],
        "skin_benefit": "calming, overnight soothe",
        "season": "all year",
        "occasion": "night",
        "category": "night treatments",
    },
    {
        "recipe_name": "Overnight Honey Oat Mask",
        "ingredients": ["2 tbsp honey", "2 tbsp oat milk", "1 tsp almond oil"],
        "skin_benefit": "barrier repair, hydration",
        "season": "winter",
        "occasion": "night",
        "category": "night treatments",
    },
    {
        "recipe_name": "5-Minute Morning Glow Splash",
        "ingredients": ["1 cup cooled green tea", "1 tbsp apple cider vinegar", "1 tbsp rose water"],
        "skin_benefit": "refresh, pore balance",
        "season": "all year",
        "occasion": "morning",
        "category": "morning routines",
    },
    {
        "recipe_name": "Citrus Morning Bright Toner",
        "ingredients": ["3 tbsp orange peel water", "1 tbsp witch hazel", "1 tsp honey"],
        "skin_benefit": "awakening glow, tone balance",
        "season": "spring",
        "occasion": "morning",
        "category": "morning routines",
    },
    {
        "recipe_name": "Coffee Eye Depuff Morning Mask",
        "ingredients": ["1 tbsp coffee grounds", "1 tbsp coconut oil", "1 tsp honey"],
        "skin_benefit": "depuffing, circulation",
        "season": "all year",
        "occasion": "morning",
        "category": "morning routines",
    },
    {
        "recipe_name": "Aloe Mint Morning Cool Gel",
        "ingredients": ["3 tbsp aloe vera gel", "5 mint leaves crushed", "1 tsp cucumber juice"],
        "skin_benefit": "cooling, morning refresh",
        "season": "summer",
        "occasion": "morning",
        "category": "morning routines",
    },
    {
        "recipe_name": "Honey Lemon Morning Cleansing Mask",
        "ingredients": ["2 tbsp honey", "1 tsp lemon juice", "1 tbsp yogurt"],
        "skin_benefit": "gentle cleanse, morning glow",
        "season": "all year",
        "occasion": "morning",
        "category": "morning routines",
    },
    {
        "recipe_name": "Summer Cucumber Ice Facial",
        "ingredients": ["1/2 cucumber blended", "2 tbsp aloe vera gel", "4 ice cubes crushed"],
        "skin_benefit": "cooling, sun-soothe",
        "season": "summer",
        "occasion": "daily",
        "category": "seasonal",
    },
    {
        "recipe_name": "Winter Honey Olive Hydrating Mask",
        "ingredients": ["2 tbsp honey", "1 tbsp olive oil", "1 tbsp mashed avocado"],
        "skin_benefit": "intense hydration, winter repair",
        "season": "winter",
        "occasion": "daily",
        "category": "seasonal",
    },
    {
        "recipe_name": "Spring Floral Rose Mist Mask",
        "ingredients": ["3 tbsp rose water", "1 tbsp honey", "1 tsp glycerin"],
        "skin_benefit": "hydration, seasonal refresh",
        "season": "spring",
        "occasion": "daily",
        "category": "seasonal",
    },
    {
        "recipe_name": "Autumn Pumpkin Enzyme Mask",
        "ingredients": ["2 tbsp pumpkin puree", "1 tbsp honey", "1 tsp cinnamon pinch"],
        "skin_benefit": "gentle exfoliation, seasonal glow",
        "season": "fall",
        "occasion": "weekly",
        "category": "seasonal",
    },
    {
        "recipe_name": "Collagen-Style Berry Anti-Age Mask",
        "ingredients": ["3 tbsp mashed blueberries", "1 tbsp honey", "1 tsp yogurt"],
        "skin_benefit": "antioxidant, elasticity support",
        "season": "all year",
        "occasion": "weekly",
        "category": "anti-aging",
    },
    {
        "recipe_name": "Pomegranate Firming Mask",
        "ingredients": ["2 tbsp pomegranate juice", "1 tbsp honey", "1 tbsp oat flour"],
        "skin_benefit": "antioxidant, firming feel",
        "season": "all year",
        "occasion": "weekly",
        "category": "anti-aging",
    },
    {
        "recipe_name": "Argan Rose Anti-Age Night Mask",
        "ingredients": ["1 tbsp argan oil", "1 tbsp rose water", "1 tsp honey"],
        "skin_benefit": "nourish, fine line softening",
        "season": "all year",
        "occasion": "night",
        "category": "anti-aging",
    },
    {
        "recipe_name": "Green Tea Wrinkle Support Mask",
        "ingredients": ["2 tbsp brewed green tea", "1 tbsp rice flour", "1 tsp honey"],
        "skin_benefit": "antioxidant, smoothing",
        "season": "all year",
        "occasion": "weekly",
        "category": "anti-aging",
    },
    {
        "recipe_name": "Pre-Party Gold Glow Mask",
        "ingredients": ["2 tbsp honey", "1 tsp turmeric", "1 tbsp yogurt"],
        "skin_benefit": "instant radiance, even tone",
        "season": "all year",
        "occasion": "pre-party glow",
        "category": "pre-party glow",
    },
    {
        "recipe_name": "Ice Roller Pre-Event Depuff",
        "ingredients": ["1 cup green tea frozen", "1 tbsp aloe vera gel", "1 tsp cucumber juice"],
        "skin_benefit": "depuff, photo-ready glow",
        "season": "all year",
        "occasion": "pre-party glow",
        "category": "pre-party glow",
    },
    {
        "recipe_name": "Champagne Glow Pre-Event Mask",
        "ingredients": ["2 tbsp plain yogurt", "1 tbsp honey", "1 tbsp flat sparkling water"],
        "skin_benefit": "brightening, event-ready skin",
        "season": "all year",
        "occasion": "pre-party glow",
        "category": "pre-party glow",
    },
    {
        "recipe_name": "Cucumber Eye De-Puff Pads",
        "ingredients": ["4 cucumber slices", "2 tbsp cold green tea", "1 tsp aloe vera gel"],
        "skin_benefit": "eye depuff, hydration",
        "season": "all year",
        "occasion": "daily",
        "category": "eye care",
    },
    {
        "recipe_name": "Coffee Eye Brightening Mask",
        "ingredients": ["1 tsp coffee grounds", "1 tbsp coconut oil", "1 tsp honey"],
        "skin_benefit": "dark circle support, brighten",
        "season": "all year",
        "occasion": "morning",
        "category": "eye care",
    },
    {
        "recipe_name": "Potato Starch Eye Light Mask",
        "ingredients": ["2 tbsp grated potato", "1 tsp honey", "1 tbsp cooled chamomile tea"],
        "skin_benefit": "under-eye brightening",
        "season": "all year",
        "occasion": "weekly",
        "category": "eye care",
    },
    {
        "recipe_name": "Green Tea Eye Recovery Gel",
        "ingredients": ["2 tbsp aloe vera gel", "1 tbsp green tea", "1 tsp vitamin E oil"],
        "skin_benefit": "soothe tired eyes",
        "season": "all year",
        "occasion": "night",
        "category": "eye care",
    },
    {
        "recipe_name": "Honey Sugar Lip Scrub",
        "ingredients": ["1 tbsp honey", "1 tsp brown sugar", "1/2 tsp olive oil"],
        "skin_benefit": "smooth, soft lips",
        "season": "all year",
        "occasion": "daily",
        "category": "lip care",
    },
    {
        "recipe_name": "Beetroot Lip Tint Balm",
        "ingredients": ["1 tsp beetroot juice", "1 tbsp coconut oil", "1 tsp honey"],
        "skin_benefit": "natural tint, hydration",
        "season": "all year",
        "occasion": "daily",
        "category": "lip care",
    },
    {
        "recipe_name": "Cocoa Butter Lip Repair Mask",
        "ingredients": ["1 tbsp cocoa butter melted", "1 tsp honey", "2 drops vanilla extract"],
        "skin_benefit": "overnight lip repair",
        "season": "winter",
        "occasion": "night",
        "category": "lip care",
    },
    {
        "recipe_name": "Peppermint Lip Plump Balm",
        "ingredients": ["1 tbsp shea butter", "1 tsp honey", "1 drop peppermint oil"],
        "skin_benefit": "hydration, fuller look",
        "season": "all year",
        "occasion": "pre-party glow",
        "category": "lip care",
    },
    {
        "recipe_name": "Coffee Coconut Body Scrub",
        "ingredients": ["3 tbsp coffee grounds", "2 tbsp coconut oil", "1 tbsp brown sugar"],
        "skin_benefit": "smooth skin, circulation",
        "season": "all year",
        "occasion": "weekly",
        "category": "body scrubs",
    },
    {
        "recipe_name": "Sea Salt Lemon Body Scrub",
        "ingredients": ["3 tbsp sea salt", "2 tbsp olive oil", "1 tsp lemon zest"],
        "skin_benefit": "exfoliation, glow",
        "season": "summer",
        "occasion": "weekly",
        "category": "body scrubs",
    },
    {
        "recipe_name": "Oat Honey Gentle Body Scrub",
        "ingredients": ["3 tbsp ground oat", "2 tbsp honey", "1 tbsp almond oil"],
        "skin_benefit": "gentle exfoliation, soothe",
        "season": "all year",
        "occasion": "weekly",
        "category": "body scrubs",
    },
    {
        "recipe_name": "Sugar Rose Body Polish",
        "ingredients": ["3 tbsp sugar", "2 tbsp rose oil", "1 tbsp yogurt"],
        "skin_benefit": "soft skin, floral glow",
        "season": "spring",
        "occasion": "weekly",
        "category": "body scrubs",
    },
    {
        "recipe_name": "Charcoal Detox Body Mask",
        "ingredients": ["2 tbsp activated charcoal", "2 tbsp aloe vera gel", "1 tbsp honey"],
        "skin_benefit": "detox feel, smooth texture",
        "season": "all year",
        "occasion": "weekly",
        "category": "body scrubs",
    },
    {
        "recipe_name": "Matcha Honey Antioxidant Mask",
        "ingredients": ["1 tsp matcha powder", "2 tbsp honey", "1 tbsp yogurt"],
        "skin_benefit": "antioxidant, calm glow",
        "season": "all year",
        "occasion": "daily",
        "category": "face masks",
    },
    {
        "recipe_name": "Milk Turmeric Softening Mask",
        "ingredients": ["3 tbsp whole milk", "1 tsp turmeric", "1 tbsp gram flour"],
        "skin_benefit": "softening, even tone",
        "season": "all year",
        "occasion": "weekly",
        "category": "brightening",
    },
    {
        "recipe_name": "Watermelon Summer Hydration Mask",
        "ingredients": ["3 tbsp watermelon juice", "1 tbsp honey", "1 tbsp aloe vera gel"],
        "skin_benefit": "hydration, summer refresh",
        "season": "summer",
        "occasion": "daily",
        "category": "seasonal",
    },
    {
        "recipe_name": "Coconut Milk Winter Comfort Mask",
        "ingredients": ["2 tbsp coconut milk", "1 tbsp honey", "1 tsp almond oil"],
        "skin_benefit": "deep comfort moisture",
        "season": "winter",
        "occasion": "daily",
        "category": "seasonal",
    },
    {
        "recipe_name": "Baking Soda Honey Clarify Mask",
        "ingredients": ["1 tsp baking soda", "2 tbsp honey", "1 tbsp water"],
        "skin_benefit": "gentle clarify, smooth finish",
        "season": "all year",
        "occasion": "weekly",
        "category": "acne solutions",
    },
    {
        "recipe_name": "Flaxseed Gel Hydration Mask",
        "ingredients": ["2 tbsp flaxseed gel", "1 tbsp honey", "1 tsp rose water"],
        "skin_benefit": "hydration, natural hold",
        "season": "all year",
        "occasion": "daily",
        "category": "morning routines",
    },
    # --- 30 new recipes: hair, acne, brightening, anti-aging, body, face_mask ---
    {
        "recipe_name": "Egg Olive Oil Hair Growth Mask",
        "ingredients": ["1 whole egg", "2 tablespoons olive oil", "1 teaspoon honey"],
        "skin_benefit": "strengthens hair follicles and reduces breakage",
        "application_time": "30 minutes",
        "frequency": "once weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "hair",
    },
    {
        "recipe_name": "Coconut Honey Hair Repair Mask",
        "ingredients": ["2 tablespoons coconut oil", "1 tablespoon raw honey", "1 teaspoon apple cider vinegar"],
        "skin_benefit": "repairs damaged strands and adds shine",
        "application_time": "45 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "hair",
    },
    {
        "recipe_name": "Onion Juice Hair Loss Treatment",
        "ingredients": ["3 tablespoons fresh onion juice", "1 tablespoon castor oil", "5 drops rosemary oil"],
        "skin_benefit": "supports scalp circulation and thinning hair",
        "application_time": "20 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "hair",
    },
    {
        "recipe_name": "Castor Oil Thicker Hair Treatment",
        "ingredients": ["2 tablespoons castor oil", "1 tablespoon coconut oil", "1 teaspoon vitamin E oil"],
        "skin_benefit": "nourishes roots for thicker-looking hair",
        "application_time": "1 hour",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "hair",
    },
    {
        "recipe_name": "Fermented Rice Water Hair Shine Rinse",
        "ingredients": ["1 cup fermented rice water", "1 tablespoon aloe vera gel", "1 teaspoon honey"],
        "skin_benefit": "smooths cuticle and boosts natural shine",
        "application_time": "15 minutes",
        "frequency": "once weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "hair",
    },
    {
        "recipe_name": "Aloe Vera Scalp Health Treatment",
        "ingredients": ["3 tablespoons fresh aloe vera gel", "1 tablespoon jojoba oil", "5 drops tea tree oil"],
        "skin_benefit": "calms itchy scalp and reduces flaking",
        "application_time": "25 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "hair",
    },
    {
        "recipe_name": "Tea Tree Aloe Spot Treatment",
        "ingredients": ["2 tablespoons aloe vera gel", "3 drops tea tree oil", "1 teaspoon witch hazel"],
        "skin_benefit": "targets blemishes with antibacterial support",
        "application_time": "10 minutes",
        "frequency": "daily",
        "season": "all year",
        "occasion": "daily",
        "category": "acne",
    },
    {
        "recipe_name": "Apple Cider Vinegar Acne Toner",
        "ingredients": ["2 tablespoons apple cider vinegar", "4 tablespoons distilled water", "1 teaspoon honey"],
        "skin_benefit": "balances pH and clears congested pores",
        "application_time": "5 minutes",
        "frequency": "daily",
        "season": "all year",
        "occasion": "daily",
        "category": "acne",
    },
    {
        "recipe_name": "Green Tea Ice Cube Redness Treatment",
        "ingredients": ["1 cup brewed green tea", "1 tablespoon aloe vera gel", "6 ice cubes"],
        "skin_benefit": "reduces redness and calms inflamed skin",
        "application_time": "5 minutes",
        "frequency": "daily",
        "season": "summer",
        "occasion": "daily",
        "category": "acne",
    },
    {
        "recipe_name": "Salicylic Honey Blemish Treatment",
        "ingredients": ["2 tablespoons raw honey", "1/4 teaspoon salicylic acid powder", "1 teaspoon aloe vera gel"],
        "skin_benefit": "unclogs pores and fades active breakouts",
        "application_time": "15 minutes",
        "frequency": "three times weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "acne",
    },
    {
        "recipe_name": "Homemade Vitamin C Brightening Serum",
        "ingredients": ["1 teaspoon L-ascorbic acid powder", "2 tablespoons rose water", "1 teaspoon glycerin"],
        "skin_benefit": "fades dark spots and boosts radiance",
        "application_time": "overnight",
        "frequency": "three times weekly",
        "season": "all year",
        "occasion": "night",
        "category": "brightening",
    },
    {
        "recipe_name": "Lemon Honey Overnight Brightening Mask",
        "ingredients": ["2 tablespoons raw honey", "1 teaspoon fresh lemon juice", "1 tablespoon yogurt"],
        "skin_benefit": "gentle acid exfoliation for brighter skin",
        "application_time": "overnight",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "night",
        "category": "brightening",
    },
    {
        "recipe_name": "Turmeric Milk Brightening Paste",
        "ingredients": ["2 tablespoons whole milk", "1 teaspoon turmeric powder", "1 teaspoon raw honey"],
        "skin_benefit": "evens skin tone and softens texture",
        "application_time": "20 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "brightening",
    },
    {
        "recipe_name": "Rose Water Brightening Toner",
        "ingredients": ["3 tablespoons rose water", "1 tablespoon witch hazel", "1 teaspoon vegetable glycerin"],
        "skin_benefit": "hydrates and refreshes dull complexion",
        "application_time": "5 minutes",
        "frequency": "daily",
        "season": "all year",
        "occasion": "daily",
        "category": "brightening",
    },
    {
        "recipe_name": "Rosehip Oil Retinol Alternative Serum",
        "ingredients": ["1 tablespoon rosehip oil", "1 teaspoon vitamin E oil", "2 drops frankincense oil"],
        "skin_benefit": "supports cell renewal and fine line reduction",
        "application_time": "overnight",
        "frequency": "daily",
        "season": "all year",
        "occasion": "night",
        "category": "anti_aging",
    },
    {
        "recipe_name": "Bone Broth Collagen Boost Mask",
        "ingredients": ["2 tablespoons bone broth gel", "1 tablespoon honey", "1 teaspoon rice flour"],
        "skin_benefit": "plumps skin with collagen-supporting nutrients",
        "application_time": "20 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "anti_aging",
    },
    {
        "recipe_name": "Cucumber Aloe Eye Cream Treatment",
        "ingredients": ["2 tablespoons grated cucumber", "1 tablespoon aloe vera gel", "1 teaspoon coconut oil"],
        "skin_benefit": "depuffs eyes and softens fine lines",
        "application_time": "15 minutes",
        "frequency": "daily",
        "season": "all year",
        "occasion": "daily",
        "category": "anti_aging",
    },
    {
        "recipe_name": "Egg White Neck Firming Mask",
        "ingredients": ["1 egg white", "1 teaspoon lemon juice", "1 tablespoon plain yogurt"],
        "skin_benefit": "temporarily tightens neck skin and smooths crepey texture",
        "application_time": "15 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "anti_aging",
    },
    {
        "recipe_name": "Coffee Body Firming Scrub",
        "ingredients": ["4 tablespoons coffee grounds", "2 tablespoons coconut oil", "1 tablespoon brown sugar"],
        "skin_benefit": "exfoliates dead skin and improves circulation",
        "application_time": "10 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "body",
    },
    {
        "recipe_name": "Sugar Honey Lip Scrub Treatment",
        "ingredients": ["1 tablespoon brown sugar", "1 teaspoon raw honey", "1/2 teaspoon olive oil"],
        "skin_benefit": "removes flaky lips and restores softness",
        "application_time": "3 minutes",
        "frequency": "three times weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "body",
    },
    {
        "recipe_name": "Coconut Milk Relaxing Bath Soak",
        "ingredients": ["1 cup coconut milk", "2 tablespoons Epsom salt", "1 tablespoon honey"],
        "skin_benefit": "softens full-body skin and soothes dryness",
        "application_time": "20 minutes",
        "frequency": "once weekly",
        "season": "winter",
        "occasion": "weekly",
        "category": "body",
    },
    {
        "recipe_name": "Himalayan Salt Body Polish",
        "ingredients": ["3 tablespoons Himalayan pink salt", "2 tablespoons almond oil", "1 teaspoon lemon zest"],
        "skin_benefit": "deep exfoliation and mineral-rich glow",
        "application_time": "10 minutes",
        "frequency": "once weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "body",
    },
    {
        "recipe_name": "Bentonite Clay Oily Skin Mask",
        "ingredients": ["2 tablespoons bentonite clay", "1 tablespoon apple cider vinegar", "1 teaspoon honey"],
        "skin_benefit": "absorbs excess oil and clears congested pores",
        "application_time": "15 minutes",
        "frequency": "twice weekly",
        "season": "summer",
        "occasion": "weekly",
        "category": "face_mask",
    },
    {
        "recipe_name": "Raw Honey Dry Skin Hydrating Mask",
        "ingredients": ["2 tablespoons raw honey", "1 tablespoon avocado oil", "1 teaspoon oatmeal flour"],
        "skin_benefit": "deep moisture for dry and dehydrated skin",
        "application_time": "20 minutes",
        "frequency": "three times weekly",
        "season": "winter",
        "occasion": "daily",
        "category": "face_mask",
    },
    {
        "recipe_name": "Turmeric Brightening Face Mask",
        "ingredients": ["1 teaspoon turmeric powder", "2 tablespoons plain yogurt", "1 teaspoon raw honey"],
        "skin_benefit": "brightens dull skin and calms inflammation",
        "application_time": "15 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "face_mask",
    },
    {
        "recipe_name": "Colloidal Oat Sensitive Skin Mask",
        "ingredients": ["3 tablespoons colloidal oatmeal", "2 tablespoons warm water", "1 teaspoon honey"],
        "skin_benefit": "soothes redness and strengthens sensitive skin barrier",
        "application_time": "15 minutes",
        "frequency": "three times weekly",
        "season": "all year",
        "occasion": "daily",
        "category": "face_mask",
    },
    {
        "recipe_name": "Egg White Pore Tightening Mask",
        "ingredients": ["1 egg white", "1/2 teaspoon lemon juice", "1 teaspoon cornstarch"],
        "skin_benefit": "minimizes pore appearance and mattifies skin",
        "application_time": "15 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "face_mask",
    },
    {
        "recipe_name": "Coffee Under-Eye Dark Circle Mask",
        "ingredients": ["1 tablespoon coffee grounds", "1 tablespoon coconut oil", "1 teaspoon honey"],
        "skin_benefit": "reduces puffiness and brightens under-eye area",
        "application_time": "10 minutes",
        "frequency": "daily",
        "season": "all year",
        "occasion": "morning",
        "category": "face_mask",
    },
    {
        "recipe_name": "Greek Yogurt Glow Face Mask",
        "ingredients": ["3 tablespoons Greek yogurt", "1 tablespoon honey", "1 teaspoon lemon juice"],
        "skin_benefit": "lactic acid exfoliation for instant glow",
        "application_time": "15 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "face_mask",
    },
    {
        "recipe_name": "Avocado Hydration Face Mask",
        "ingredients": ["1/2 ripe avocado", "1 tablespoon olive oil", "1 teaspoon honey"],
        "skin_benefit": "restores lipids and deep hydration to thirsty skin",
        "application_time": "20 minutes",
        "frequency": "twice weekly",
        "season": "all year",
        "occasion": "weekly",
        "category": "face_mask",
    },
)


def format_ingredients_list(ingredients: list[str]) -> str:
    return " + ".join(str(item) for item in ingredients)


def recipe_memory_key(recipe_name: str) -> str:
    return f"recipe:{recipe_name.strip().lower()}"


__all__ = [
    "INSTAGRAM_CONTENT_BRIEF",
    "INSTAGRAM_RECIPE_CTA",
    "INSTAGRAM_RECIPE_POOL",
    "INSTAGRAM_RECIPE_SETTINGS",
    "format_ingredients_list",
    "recipe_memory_key",
]
