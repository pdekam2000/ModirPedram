"""Instagram educational skincare recipe pool — one recipe per Reel."""

from __future__ import annotations

from typing import Any

INSTAGRAM_CONTENT_BRIEF = """INSTAGRAM CONTENT RULES:
1. Each video teaches ONE specific skincare recipe
2. Show EXACT quantities: "2 tablespoons honey + 1 teaspoon turmeric + 3 drops lemon juice"
3. Presenter makes/applies treatment ON CAMERA
4. Structure:
   - Clip 1 (15s): Show ingredients + mix them
     Presenter says: "Today I'm making [recipe name].
     You need [exact ingredients]"
   - Clip 2 (15s): Apply to face/skin + result
     End with: "Follow for daily skincare recipes"
5. Visual style: bright, clean, aesthetic kitchen or bathroom. Close-ups of ingredients and skin.
6. NEVER repeat a recipe — track used recipes in story memory
7. Recipe categories to rotate:
   - Face masks (honey, clay, oat, egg, yogurt...)
   - Night treatments
   - Morning routines
   - Seasonal (summer cooling, winter hydrating...)
   - Anti-aging
   - Brightening
   - Acne solutions
   - Pre-party glow
   - Eye care
   - Lip care
   - Body scrubs"""

INSTAGRAM_RECIPE_SETTINGS: tuple[str, ...] = (
    "bright aesthetic kitchen with white marble counter and natural window light",
    "clean modern bathroom with large mirror, plants, and soft daylight",
    "minimalist vanity with glass jars, wooden tray, and fresh herbs",
    "sunlit kitchen island with ceramic bowls and linen cloth",
    "spa-style bathroom with white tiles, eucalyptus, and warm lighting",
)

INSTAGRAM_RECIPE_CTA = "Follow for daily skincare recipes"

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
