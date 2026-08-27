"""
Shared reference data for the RedMealGPT-mini pipeline.

This is the single source of truth for:
  - activity levels (used by utils.calculate_tdee)
  - allergy / disease / cuisine / digestive-trigger reference lists (used by
    the Streamlit profile form AND by meal_gpt_core's prompt-building logic,
    so both sides agree on the exact same category names)
  - goal recommendations by weight condition, calorie-adjustment options per
    goal, and the macro-split rules (protein g/kg, carb %, fat %) used by
    utils.calculate_macros and user_profile.build_profile
  - the 5-slot meal proportions used to split daily targets across meals

NOTE: This module didn't exist among the uploaded files (utils.py,
user_profile.py, and app.py all import from it) so its contents were
reconstructed from how each name is used at the call sites. The numeric
ranges below (protein g/kg, carb %, fat %, calorie-adjustment amounts) are
reasonable, commonly-cited sports-nutrition defaults - adjust them freely if
your product has different clinical guidance.
"""

# ---------------------------------------------------------------------------
# Activity levels (keys MUST match utils.calculate_tdee's activity_factors)
# ---------------------------------------------------------------------------

ACTIVITY_LEVELS = {
    "sedentary": {
        "name": "Sedentary",
        "description": "Little or no exercise, a desk job.",
    },
    "lightly_active": {
        "name": "Lightly Active",
        "description": "Light exercise or sports 1-3 days/week.",
    },
    "moderately_active": {
        "name": "Moderately Active",
        "description": "Moderate exercise or sports 3-5 days/week.",
    },
    "very_active": {
        "name": "Very Active",
        "description": "Hard exercise or sports 6-7 days/week.",
    },
    "extra_active": {
        "name": "Extra Active",
        "description": "Very hard exercise, physical job, or training twice a day.",
    },
}


# ---------------------------------------------------------------------------
# Allergies: category -> specific foods restricted by that allergy.
# ---------------------------------------------------------------------------

ALLERGIES = {
    "Tree Nuts": ["Almonds", "Walnuts", "Cashews", "Pistachios", "Hazelnuts", "Pecans", "Brazil Nuts", "Macadamia Nuts"],
    "Peanuts": ["Peanuts", "Peanut Butter"],
    "Shellfish": ["Shrimp", "Prawns", "Crab", "Lobster", "Crayfish"],
    "Fish": ["Salmon", "Tuna", "Cod", "Sardines", "Mackerel", "Anchovies"],
    "Eggs": ["Boiled Eggs", "Fried Eggs", "Omelette", "Scrambled Eggs", "Mayonnaise", "Egg Custard", "Egg Noodles"],
    "Wheat": ["Wheat", "Bread", "Pasta", "Chapati", "Naan", "Biscuits", "Cakes", "Semolina (Rava)"],
    "Soy": ["Soybeans", "Tofu", "Soy Milk", "Soy Sauce", "Edamame", "Tempeh", "Miso", "Soy Protein"],
    "Sesame": ["Sesame Seeds", "Tahini", "Sesame Oil", "Gingelly Oil"],
    "Milk": ["Milk", "Cheese", "Butter", "Ghee", "Yogurt", "Curd", "Cream", "Paneer", "Ice Cream", "Condensed Milk"],
}


# ---------------------------------------------------------------------------
# Diagnosed conditions the profile form + disease-specific prompt guidance
# both recognize.
# ---------------------------------------------------------------------------

VERIFIED_DISEASES = [
    "Type 2 Diabetes Mellitus",
    "Diabetes",
    "Type 1 Diabetes Mellitus",
    "Prediabetes",
    "Hypertension",
    "Obesity",
    "Metabolic Syndrome",
    "Dyslipidemia",
    "Atherosclerotic Cardiovascular Disease (ASCVD)",
    "Polycystic Ovary Syndrome (PCOS)",
    "Nonalcoholic Fatty Liver Disease (NAFLD)",
    "Gallstones",
    "Celiac Disease",
    "Vitamin B12 Deficiency",
    "Vitamin D Deficiency",
    "Hyperuricemia",
    "Gastroparesis",
    "Crohn's Disease",
    "Lactose Intolerance",
    "Chronic Diarrhea",
    "H. pylori Infection",
    "Pancreatitis",
    "Constipation",
    "IBS" 
]


# ---------------------------------------------------------------------------
# Foods that commonly aggravate digestive issues, grouped by trigger category.
# ---------------------------------------------------------------------------

DIGESTIVE_AGGRAVATING_FOODS = {
    "Raw Vegetables": ["salad", "sandwich", "burger", "wrap", "taco", "poke bowl", "grain bowl", "spring rolls", "raita", "chaat"],
    "Spicy Foods": ["Chili", "Green Chili", "Red Chili Powder", "Hot Sauce", "Spicy Curries", "Pepper"],
    "Fried Foods": ["French Fries", "Samosa", "Pakora", "Fried Chicken", "Fritters", "Chips"],
    "Carbonated Drinks": ["Soda", "Cola", "Sparkling Water", "Energy Drinks"],
    "Caffeine": ["Coffee", "Tea", "Energy Drinks", "Chocolate", "Cola"],
    "Alcohol": ["Beer", "Wine", "Whiskey", "Rum", "Vodka"],
    "High-Fat Dairy": ["Full-Fat Milk", "Cream", "Cheese", "Butter", "Ghee"],
    "Artificial Sweeteners": ["Sorbitol", "Xylitol", "Diet Soda", "Sugar-Free Candy", "Sugar-Free Gum"],
    "Processed/Ultra-Processed Foods": ["Packaged Snacks", "Instant Noodles", "Frozen Meals", "Processed Meats", "Canned Foods"],
    "Beans/Legumes": ["Rajma (Kidney Beans)", "Chickpeas", "Black Beans", "Lentils", "Soybeans"],
    "Cruciferous Vegetables": ["Broccoli", "Cabbage", "Cauliflower", "Brussels Sprouts", "Kale"],
    "Raw Onion/Garlic": ["Raw Onion", "Raw Garlic", "Onion Salad", "Garlic Chutney"],
    "Citrus Fruits": ["Orange", "Lemon", "Lime", "Grapefruit", "Tangerine"],
}


# ---------------------------------------------------------------------------
# Preferred-cuisine -> typical eating-pattern guidance, used to steer the
# meal-plan LLM prompt toward realistic, cuisine-appropriate dishes.
# ---------------------------------------------------------------------------

CUISINE_EATING_PATTERNS = {
    "South Indian": (
        "South Indian cuisine generally includes idli, dosa, and upma for breakfast, with a "
        "preference for rice-based meals with sambar/rasam and vegetable curries for lunch, "
        "and lighter rice- or dosa/idli-based meals for dinner, "
        "and there should not be poached eggs in south indian"
    ),
    "North Indian": (
        "North Indian cuisine generally centers lunch and dinner around chapati/roti or rice "
        "paired with dal and a sabzi (vegetable curry), with paneer- or legume-based dishes as "
        "common protein sources; breakfast often features paratha, poha, or besan chilla."
    ),
    "North American": (
        "North American cuisine typically features eggs, oats, or cereal-based breakfasts; "
        "sandwiches, salads, or bowls for lunch; and a protein (meat, poultry, fish, or a "
        "plant-based substitute) with a starch and vegetable side for dinner."
    ),
    "Mediterranean": (
        "Mediterranean cuisine emphasizes olive oil, whole grains, legumes, vegetables, and fish "
        "or lean protein, typically as mezze-style plates or composed salads/bowls rather than "
        "a single heavy protein-and-starch plate."
    ),
    "Continental": (
        "Continental cuisine typically features bread- or egg-based breakfasts, and lunch/dinner "
        "built around a roasted or grilled protein with potatoes/pasta and a vegetable side."
    ),
    "Chinese": (
        "Chinese cuisine typically pairs stir-fried or braised protein and vegetable dishes with "
        "steamed rice or noodles, often with a light soup alongside the main meal."
    ),
    "Mexican": (
        "Mexican cuisine typically builds meals around corn or wheat tortillas, beans, and rice, "
        "combined with a protein filling (e.g. tacos, burritos, bowls) and fresh vegetable/salsa "
        "toppings."
    ),
    "Middle Eastern": (
        "Middle Eastern cuisine typically features flatbread, legumes (hummus, lentils, falafel), "
        "grilled meats or plant-based protein, and fresh salads like tabbouleh or fattoush."
    ),
    "Italian": (
        "Italian cuisine typically centers meals around pasta, risotto, or a protein-and-vegetable "
        "second course, with breakfast usually light (e.g. yogurt, fruit, or a simple bake)."
    ),
}


# ---------------------------------------------------------------------------
# Goal recommendations by BMI-derived weight condition.
# ---------------------------------------------------------------------------

GOAL_RECOMMENDATIONS = {
    "Underweight": [
        "Muscle Gain (Bulking)",
        "General Fitness / Body Recomposition",
    ],
    "Normal weight": [
        "General Fitness / Body Recomposition",
        "Muscle Gain (Bulking)",
    ],
    "Overweight": [
        "Fat Loss (Cutting)",
        "General Fitness / Body Recomposition",
    ],
    "Obese": [
        "Fat Loss (Cutting)",
    ],
}


CALORIES_RECOMMENDATIONS = {
    "Fat Loss (Cutting)": {

        "Conservative": {
            "calorie_change": -500,
            "expected_weight_change_per_week": "-~0.5 kg/week",
            "description": (
                "A moderate calorie deficit intended to support steady fat loss "
                "of roughly 0.5 kg per week. The actual rate may vary between individuals."
            ),
        },

        "Moderate": {
            "calorie_change": -750,
            "expected_weight_change_per_week": "-~0.7 kg/week",
            "description": (
                "A larger calorie deficit intended to produce faster fat loss, "
                "but it may be harder to sustain and can increase the risk of "
                "fatigue and muscle loss. The deficit may be capped at 20% of "
                "TDEE to avoid an excessively large calorie restriction."
            ),
        },
    },

    "Muscle Gain (Bulking)": {

        "Lean Bulk": {
            "calorie_change": 350,
            "expected_weight_change_per_week": "+~0.25–0.3 kg/week",
            "description": (
                "A small calorie surplus designed to support muscle growth "
                "while limiting unnecessary fat gain. Actual weight gain will "
                "vary depending on training, body composition, and individual "
                "energy needs."
            ),
        },

        "Standard Bulk": {
            "calorie_change": 500,
            "expected_weight_change_per_week": "+~0.4–0.5 kg/week",
            "description": (
                "A larger calorie surplus intended to support faster weight "
                "and muscle gain, with a greater possibility of fat gain. "
                "The surplus may be capped at 15% of TDEE to limit excessive "
                "calorie intake."
            ),
        },
    },

    "General Fitness / Body Recomposition": {

        "Maintain": {
            "calorie_change": 0,
            "expected_weight_change_per_week": "Maintain",
            "description": (
                "Eat approximately at maintenance calories (TDEE) while "
                "following an appropriate training program. This can support "
                "body recomposition, where body fat decreases while muscle "
                "is maintained or gained, even when overall body weight "
                "changes very little."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Macro-split rules used by utils.calculate_macros()
# ---------------------------------------------------------------------------

CALORIES_PER_GRAM = {
    "Protein": 4,
    "Carbohydrates": 4,
    "Fats": 9,
}

# ---------------------------------------------------------------------------
# Protein target as a g/kg-bodyweight range, keyed by weight condition
# (BMI-derived) and then by activity level. This replaces the old
# goal-based table.
#
# Source table only defines 3 weight-condition tiers (Normal BMI,
# Underweight, Obese) and each has fewer activity tiers than our 5
# ACTIVITY_LEVELS keys, so entries were mapped onto ACTIVITY_LEVELS in
# increasing-intensity order as follows:
#
#   Normal weight (5 source tiers -> 5 activity levels, 1:1):
#     sedentary          -> "Maintenance / Sedentary"            0.8 g/kg
#     lightly_active      -> "Lightly active"                    0.8-1.0 g/kg
#     moderately_active   -> "Moderately Active"                 1.2-1.4 g/kg
#     very_active          -> "Active or Resistance Training"    1.4-1.6 g/kg
#     extra_active         -> "Very active"                      1.6-2.0 g/kg
#
#   "Overweight" (BMI 25-29.9) isn't covered by the source table - the
#   Adjusted-Body-Weight/Obese method is explicitly gated on BMI >= 30, so
#   Overweight reuses the Normal-weight tiers below.
#
#   Underweight (4 source tiers -> 5 activity levels; lightly_active and
#   moderately_active are grouped into "Active"; very_active and
#   extra_active are grouped into "Very Active"):
#     sedentary                          -> "Sedentary"          1.0-1.2 g/kg
#     lightly_active, moderately_active  -> "Active"              1.2-1.6 g/kg
#     very_active, extra_active          -> "Very Active"         1.4-1.6 g/kg
#   (A separate "Lean mass/muscle gain with resistance training" tier,
#   1.6-2.0 g/kg, applies instead when goal == "Muscle Gain (Bulking)" and
#   activity_level is very_active/extra_active - see
#   PROTEIN_LEAN_MASS_GAIN_UNDERWEIGHT below.)
#
#   Obese / BMI >= 30 (uses Adjusted Body Weight, not actual weight; 3
#   source tiers -> 5 activity levels, same grouping as Underweight):
#     sedentary                          -> "Sedentary"          1.0-1.2 g/kg ABW
#     lightly_active, moderately_active  -> "Moderate"            1.2-1.4 g/kg ABW
#     very_active, extra_active          -> "Very/Extra Active"   1.4-1.6 g/kg ABW
# ---------------------------------------------------------------------------

PROTEIN_RECOMMENDATIONS = {
    "Normal weight": {
        "sedentary": {"min_g_per_kg": 0.8, "max_g_per_kg": 0.8},
        "lightly_active": {"min_g_per_kg": 0.8, "max_g_per_kg": 1.0},
        "moderately_active": {"min_g_per_kg": 1.2, "max_g_per_kg": 1.4},
        "very_active": {"min_g_per_kg": 1.4, "max_g_per_kg": 1.6},
        "extra_active": {"min_g_per_kg": 1.6, "max_g_per_kg": 2.0},
    },
    "Underweight": {
        "sedentary": {"min_g_per_kg": 1.0, "max_g_per_kg": 1.2},
        "lightly_active": {"min_g_per_kg": 1.2, "max_g_per_kg": 1.6},
        "moderately_active": {"min_g_per_kg": 1.2, "max_g_per_kg": 1.6},
        "very_active": {"min_g_per_kg": 1.4, "max_g_per_kg": 1.6},
        "extra_active": {"min_g_per_kg": 1.4, "max_g_per_kg": 1.6},
    },
    "Obese": {
        "sedentary": {"min_g_per_kg": 1.0, "max_g_per_kg": 1.2},
        "lightly_active": {"min_g_per_kg": 1.2, "max_g_per_kg": 1.4},
        "moderately_active": {"min_g_per_kg": 1.2, "max_g_per_kg": 1.4},
        "very_active": {"min_g_per_kg": 1.4, "max_g_per_kg": 1.6},
        "extra_active": {"min_g_per_kg": 1.4, "max_g_per_kg": 1.6},
    },
}
# BMI 25-29.9 isn't covered by the source table; reuse the Normal-weight
# tiers since the Adjusted-Body-Weight/Obese methodology is explicitly
# gated on BMI >= 30 (see comment block above).
PROTEIN_RECOMMENDATIONS["Overweight"] = PROTEIN_RECOMMENDATIONS["Normal weight"]

# Underweight + "Lean mass/muscle gain with resistance training" override:
# applies instead of the Underweight table above when the user's goal is
# Muscle Gain (Bulking) and their activity level is very_active/extra_active.
PROTEIN_LEAN_MASS_GAIN_UNDERWEIGHT = {"min_g_per_kg": 1.6, "max_g_per_kg": 2.0}

# ---------------------------------------------------------------------------
# Carbohydrates and fat as a % of total daily calories for the standard
# diet (flat ranges - no longer goal-specific). Protein is calculated by
# g/kg body weight above, not as a %, so these two ranges plus whatever
# protein ends up contributing are reconciled in utils.calculate_macros.
# ---------------------------------------------------------------------------
CARB_PERCENTAGE = {"min_percent": 50, "max_percent": 60}
FAT_PERCENTAGES = {"min_percent": 30, "max_percent": 35}


# ---------------------------------------------------------------------------
# Meal-slot proportions (must sum to 1.0). Slot names match the 5 meal slots
# meal_gpt_core.py's DayMealPlan schema expects (breakfast, morning_snack,
# lunch, afternoon_snack, dinner), so a profile built here can be sent
# straight to the meal-generation API without any renaming.
# ---------------------------------------------------------------------------

MEAL_PROPORTIONS = {
    "breakfast": 0.25,
    "morning_snack": 0.10,
    "lunch": 0.30,
    "afternoon_snack": 0.10,
    "dinner": 0.25,
}