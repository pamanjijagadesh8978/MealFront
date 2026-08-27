from datetime import date
from utils import calculate_tdee, calculate_macros, calculate_meal_breakdown
from goals import GOAL_RECOMMENDATIONS, CALORIES_RECOMMENDATIONS, MEAL_PROPORTIONS

# Maps meal keys (as used in MEAL_PROPORTIONS / profile["meals"]) to the
# food-guidance categories for that meal. Keeping this here means the
# guidance always lines up with whatever meals calculate_meal_breakdown
# actually produces.
MEAL_GUIDANCE = {
    "breakfast": ["Complex carbohydrates", "Lean protein", "Fiber"],
    "morning_snack": ["Fruit", "Protein or Fiber"],
    "lunch": ["Non-starchy vegetables", "Lean protein", "Controlled carbohydrates", "Healthy fats"],
    "afternoon_snack": ["Protein", "Healthy fats or Fiber"],
    "dinner": ["Non-starchy vegetables", "Lean protein", "Controlled carbohydrates"],
}


def calculate_age(birth_year, birth_month, birth_day, today=None):
    """Accurate age in whole years, accounting for whether the birthday
    has already happened this year (not just year subtraction)."""
    today = today or date.today()
    age = today.year - birth_year
    if (today.month, today.day) < (birth_month, birth_day):
        age -= 1
    return age


def build_profile(raw_profile):
    """
    Takes the raw user-supplied fields and returns a fully computed
    profile dict (age, BMI, goal, calories, macros, meals, fiber, guidance).

    Calorie rules:
    - Fat Loss:
        * Recommended options: -250, -500, -1000 kcal/day
        * Maximum allowed deficit = 20% of TDEE
        * If a recommended deficit exceeds 20% of TDEE,
          it is adjusted down to 20% of TDEE.

    - Muscle Gain:
        * Recommended options: +250, +500 kcal/day
        * Maximum allowed surplus = 15% of TDEE
        * If a recommended surplus exceeds 15% of TDEE,
          it is adjusted down to 15% of TDEE.

    - General Fitness / Body Recomposition:
        * Maintain TDEE.

    Raises ValueError on invalid input rather than failing silently later.
    """

    profile = dict(raw_profile)

    # ---------------------------------------------------------
    # Validate input
    # ---------------------------------------------------------
    if profile["height_cm"] <= 0 or profile["weight_kg"] <= 0:
        raise ValueError(
            "height_cm and weight_kg must be positive numbers"
        )

    # ---------------------------------------------------------
    # Age
    # ---------------------------------------------------------
    profile["age"] = calculate_age(
        profile["birth_year"],
        profile["birth_month"],
        profile["birth_day"]
    )

    # ---------------------------------------------------------
    # BMI
    # ---------------------------------------------------------
    profile["bmi"] = round(
        profile["weight_kg"]
        / ((profile["height_cm"] / 100) ** 2),
        2
    )

    # ---------------------------------------------------------
    # Weight condition
    # ---------------------------------------------------------
    if profile["bmi"] < 18.5:
        profile["weight_condition"] = "Underweight"

    elif profile["bmi"] < 25:
        profile["weight_condition"] = "Normal weight"

    elif profile["bmi"] < 30:
        profile["weight_condition"] = "Overweight"

    else:
        profile["weight_condition"] = "Obese"

    # ---------------------------------------------------------
    # Goals
    # ---------------------------------------------------------
    profile["recommended_goals"] = GOAL_RECOMMENDATIONS[
        profile["weight_condition"]
    ]

    profile.setdefault(
        "goal",
        profile["recommended_goals"][0]
    )

    if profile["goal"] not in profile["recommended_goals"]:
        raise ValueError(
            f"goal '{profile['goal']}' is not a valid option for "
            f"weight condition '{profile['weight_condition']}'"
        )

    # ---------------------------------------------------------
    # TDEE
    # ---------------------------------------------------------
    profile["tdee"] = calculate_tdee(
        weight_kg=profile["weight_kg"],
        height_cm=profile["height_cm"],
        age=profile["age"],
        gender=profile["gender"].lower(),
        activity_level=profile["activity_level"],
    )

    tdee = profile["tdee"]

    # ---------------------------------------------------------
    # Calorie options
    # ---------------------------------------------------------
    goal_calorie_options = CALORIES_RECOMMENDATIONS[
        profile["goal"]
    ]

    # Default to first option
    profile.setdefault(
        "calorie_option",
        next(iter(goal_calorie_options))
    )

    if profile["calorie_option"] not in goal_calorie_options:
        raise ValueError(
            f"calorie_option '{profile['calorie_option']}' is not valid "
            f"for goal '{profile['goal']}'. Choose from: "
            f"{list(goal_calorie_options.keys())}"
        )

    # ---------------------------------------------------------
    # Calorie safety rules
    # ---------------------------------------------------------
    MAX_DEFICIT_PERCENT = 20
    MAX_SURPLUS_PERCENT = 15

    max_allowed_deficit = tdee * (
        MAX_DEFICIT_PERCENT / 100
    )

    max_allowed_surplus = tdee * (
        MAX_SURPLUS_PERCENT / 100
    )

    # ---------------------------------------------------------
    # Calculate ALL available calorie options
    #
    # This is important because the user should be able to see:
    #
    # Recommended: -1000
    # Effective:   -574
    #
    # when -1000 exceeds 20% of TDEE.
    # ---------------------------------------------------------
    available_calorie_options = {}

    for option_key, option_plan in goal_calorie_options.items():

        requested_change = option_plan["calorie_change"]

        # -----------------------------------------------------
        # FAT LOSS
        # -----------------------------------------------------
        if profile["goal"] == "Fat Loss (Cutting)":

            requested_deficit = abs(requested_change)

            # Apply 20% TDEE maximum deficit
            effective_deficit = min(
                requested_deficit,
                max_allowed_deficit
            )

            effective_change = -round(
                effective_deficit
            )

        # -----------------------------------------------------
        # MUSCLE GAIN
        # -----------------------------------------------------
        elif profile["goal"] == "Muscle Gain (Bulking)":

            requested_surplus = max(
                requested_change,
                0
            )

            # Apply 15% TDEE maximum surplus
            effective_surplus = min(
                requested_surplus,
                max_allowed_surplus
            )

            effective_change = round(
                effective_surplus
            )

        # -----------------------------------------------------
        # GENERAL FITNESS / BODY RECOMPOSITION
        # -----------------------------------------------------
        else:

            effective_change = 0

        # -----------------------------------------------------
        # Effective daily calorie target
        # -----------------------------------------------------
        effective_daily_calories = round(
            tdee + effective_change
        )

        # -----------------------------------------------------
        # Effective percentage
        # -----------------------------------------------------
        if tdee > 0:
            effective_change_percent = round(
                abs(effective_change) / tdee * 100,
                1
            )
        else:
            effective_change_percent = 0

        # -----------------------------------------------------
        # Expected weekly weight change
        #
        # Approximation:
        # 7,700 kcal ≈ 1 kg body weight
        # -----------------------------------------------------
        weekly_weight_change = (
            abs(effective_change) * 7 / 7700
        )

        if effective_change < 0:

            expected_change = (
                f"-~{weekly_weight_change:.1f} kg/week"
            )

        elif effective_change > 0:

            expected_change = (
                f"+~{weekly_weight_change:.1f} kg/week"
            )

        else:

            expected_change = "Maintain"

        # -----------------------------------------------------
        # Determine whether the recommendation was adjusted
        # -----------------------------------------------------
        adjusted = (
            effective_change != requested_change
        )

        # -----------------------------------------------------
        # Explanation
        # -----------------------------------------------------
        if adjusted:

            if profile["goal"] == "Fat Loss (Cutting)":

                explanation = (
                    f"Recommended deficit: "
                    f"{requested_change} kcal/day. "
                    f"This exceeds the maximum allowed deficit "
                    f"of {MAX_DEFICIT_PERCENT}% of TDEE "
                    f"({max_allowed_deficit:.0f} kcal/day). "
                    f"Adjusted to {effective_change} kcal/day."
                )

            elif profile["goal"] == "Muscle Gain (Bulking)":

                explanation = (
                    f"Recommended surplus: "
                    f"+{requested_change} kcal/day. "
                    f"This exceeds the maximum allowed surplus "
                    f"of {MAX_SURPLUS_PERCENT}% of TDEE "
                    f"({max_allowed_surplus:.0f} kcal/day). "
                    f"Adjusted to +{effective_change} kcal/day."
                )

            else:

                explanation = option_plan["description"]

        else:

            explanation = option_plan["description"]

        # -----------------------------------------------------
        # Store option information
        # -----------------------------------------------------
        available_calorie_options[option_key] = {

            # Original recommendation from goals.py
            "recommended_change": requested_change,

            # Actual value after applying 20% / 15% rule
            "effective_change": effective_change,

            # Final daily calorie target for this option
            "daily_calories": effective_daily_calories,

            # Percentage of TDEE
            "calorie_change_percent": effective_change_percent,

            # Expected weekly weight change
            "expected_weight_change_per_week": expected_change,

            # Whether the original recommendation was capped
            "adjusted": adjusted,

            # Explanation
            "description": explanation,
        }

    # ---------------------------------------------------------
    # Store all available options in profile
    # ---------------------------------------------------------
    profile["available_calorie_options"] = (
        available_calorie_options
    )

    # ---------------------------------------------------------
    # Get the SELECTED calorie option
    # ---------------------------------------------------------
    selected_calorie_plan = available_calorie_options[
        profile["calorie_option"]
    ]

    profile["recommended_calorie_change"] = (
        selected_calorie_plan["recommended_change"]
    )

    profile["calorie_change"] = (
        selected_calorie_plan["effective_change"]
    )

    profile["calorie_change_percent"] = (
        selected_calorie_plan["calorie_change_percent"]
    )

    profile["calories"] = (
        selected_calorie_plan["daily_calories"]
    )

    profile["expected_weight_change_per_week"] = (
        selected_calorie_plan[
            "expected_weight_change_per_week"
        ]
    )

    profile["calorie_description"] = (
        selected_calorie_plan["description"]
    )

    # ---------------------------------------------------------
    # Macros
    # ---------------------------------------------------------
    profile["macros"] = calculate_macros(
        weight_kg=profile["weight_kg"],
        activity_level=profile["activity_level"],
        total_calories=profile["calories"],
        goal=profile["goal"],
        bmi=profile["bmi"],
        height_cm=profile["height_cm"],
        gender=profile["gender"],
    )
    # ---------------------------------------------------------
    # Meals
    # ---------------------------------------------------------
    profile["meals"] = calculate_meal_breakdown(
        total_calories=profile["calories"],
        macros=profile["macros"],
    )

    # ---------------------------------------------------------
    # Fiber
    # 14 g per 1,000 kcal
    # ---------------------------------------------------------
    profile["fiber_g"] = round(
        profile["calories"] / 1000 * 14,
        1
    )

    for meal_name, meal_data in profile["meals"].items():

        meal_data["fiber_g"] = round(
            profile["fiber_g"]
            * MEAL_PROPORTIONS[meal_name],
            1
        )

        meal_data["guidance"] = (
            MEAL_GUIDANCE.get(
                meal_name,
                []
            )
        )

    return profile

def format_profile(profile):
    """Builds a clean, human-readable summary string from the profile dict."""
    lines = []
    lines.append("=" * 50)
    lines.append(f"  UserId: {profile['user_id']}")
    lines.append(f"  PROFILE SUMMARY — {profile['name']}")
    lines.append("=" * 50)

    lines.append("")
    lines.append("Personal Details")
    lines.append("-" * 50)
    lines.append(f"  Age:              {profile['age']} years")
    lines.append(f"  Gender:           {profile['gender']}")
    lines.append(f"  Height:           {profile['height_cm']} cm")
    lines.append(f"  Weight:           {profile['weight_kg']} kg")
    lines.append(f"  Activity Level:   {profile['activity_level'].replace('_', ' ').title()}")

    lines.append("")
    lines.append("Dietary & Health Details")
    lines.append("-" * 50)
    lines.append(f"  Allergies:              {', '.join(profile['allergies']) or 'None'}")
    lines.append(f"  Diseases:               {', '.join(profile['diseases']) or 'None'}")
    lines.append(f"  Dietary Preferences:    {', '.join(profile['dietary_preferences']) or 'None'}")
    lines.append(f"  Preferred Cuisines:     {', '.join(profile['preferred_cuisines']) or 'None'}")
    lines.append(f"  Foods to Avoid (Digestive): {', '.join(profile['foods_aggravating_digestive_issues']) or 'None'}")
    lines.append(f"  Restricted Foods:       {', '.join(profile.get('restricted_foods', [])) or 'None'}")

    lines.append("")
    lines.append("Body Composition")
    lines.append("-" * 50)
    lines.append(f"  BMI:              {profile['bmi']} ({profile['weight_condition']})")

    lines.append("")
    lines.append("Goal")
    lines.append("-" * 50)
    lines.append(f"  Selected Goal:    {profile['goal']}")
    lines.append(f"  Other Options:    {', '.join(g for g in profile['recommended_goals'] if g != profile['goal']) or 'None'}")

    # lines.append("")
    # lines.append("Calories")
    # lines.append("-" * 50)
    # lines.append(f"  TDEE (Maintenance): {profile['tdee']:.0f} kcal/day")
    # sign = "+" if profile["calorie_change"] > 0 else ""
    # lines.append(f"  Calorie Adjustment: {sign}{profile['calorie_change']} kcal/day")
    # lines.append(f"  Daily Target:       {profile['calories']:.0f} kcal/day")
    # lines.append(f"  Expected Change:    {profile['expected_weight_change_per_week']}")
    # lines.append(f"  Notes:              {profile['calorie_description']}")
    lines.append("")
    lines.append("Calories")
    lines.append("-" * 50)
    lines.append(f"  TDEE (Maintenance): {profile['tdee']:.0f} kcal/day")
    lines.append(f"  Selected Option:    {profile['calorie_option']}")
    recommended_change = profile["recommended_calorie_change"]
    effective_change = profile["calorie_change"]
    recommended_sign = "+" if recommended_change > 0 else ""
    effective_sign = "+" if effective_change > 0 else ""

    lines.append(
        f"  Recommended:        "
        f"{recommended_sign}{recommended_change} kcal/day"
    )

    if recommended_change != effective_change:
        lines.append(
            f"  Adjusted To:        "
            f"{effective_sign}{effective_change} kcal/day"
        )
    else:
        lines.append(
            f"  Calorie Adjustment: "
            f"{effective_sign}{effective_change} kcal/day"
        )

    lines.append(
        f"  Daily Target:       {profile['calories']:.0f} kcal/day"
    )

    lines.append(
        f"  Expected Change:    "
        f"{profile['expected_weight_change_per_week']}"
    )

    lines.append(
        f"  Notes:              {profile['calorie_description']}"
    )

    # ---------------------------------------------------------
    # Available calorie options
    # ---------------------------------------------------------
    lines.append("")
    lines.append("  Available Calorie Options:")

    for option_key, option_data in profile["available_calorie_options"].items():

        recommended = option_data["recommended_change"]
        effective = option_data["effective_change"]

        recommended_sign = "+" if recommended > 0 else ""
        effective_sign = "+" if effective > 0 else ""

        if option_data["adjusted"]:

            lines.append(
                f"    {option_key}: "
                f"{recommended_sign}{recommended} kcal/day"
                f" → "
                f"{effective_sign}{effective} kcal/day"
                f" | "
                f"{option_data['expected_weight_change_per_week']}"
                f" | Adjusted"
            )

        else:

            lines.append(
                f"    {option_key}: "
                f"{effective_sign}{effective} kcal/day"
                f" | "
                f"{option_data['expected_weight_change_per_week']}"
            )

        lines.append(
            f"        {option_data['description']}"
        )

    lines.append("")
    lines.append("Macronutrients")
    lines.append("-" * 50)
    for macro_name, macro_data in profile["macros"].items():
        lines.append(f"  {macro_name}:")
        lines.append(
            f"    Range:          {macro_data['min_g']}–{macro_data['max_g']} g/day "
            f"({macro_data['min_calories']:.0f}–{macro_data['max_calories']:.0f} kcal)"
        )
        lines.append(
            f"    Target:         {macro_data['target_g']} g/day "
            f"({macro_data['target_calories']:.0f} kcal)"
        )
        lines.append(f"    Why:            {macro_data['description']}")
        if "warning" in macro_data:
            lines.append(f"    ⚠ Warning:      {macro_data['warning']}")

    total_target_cals = sum(m["target_calories"] for m in profile["macros"].values())
    lines.append("")
    lines.append(
        f"  Macro calories total: {total_target_cals:.0f} kcal "
        f"(target: {profile['calories']:.0f} kcal)"
    )
    lines.append(f"  Fiber:              {profile['fiber_g']} g/day (14 g per 1,000 kcal)")

    lines.append("")
    lines.append("Meal-wise Breakdown")
    lines.append("-" * 50)
    for meal_name, meal_data in profile["meals"].items():
        lines.append(f"  {meal_name.replace('_', ' ').title()} ({int(MEAL_PROPORTIONS[meal_name] * 100)}%):")
        lines.append(f"    Calories:       {meal_data['calories']:.0f} kcal")
        for macro_name, macro_vals in meal_data["macros"].items():
            lines.append(
                f"    {macro_name}:  {macro_vals['grams']} g "
                f"({macro_vals['calories']:.0f} kcal)"
            )
        lines.append(f"    Fiber:  {meal_data['fiber_g']} g")
        if meal_data.get("guidance"):
            lines.append(f"    Focus on:  {', '.join(meal_data['guidance'])}")
        lines.append("")

    lines.append("=" * 50)

    return "\n".join(lines)


def main():
    raw_profile = {
        "user_id": "2edfew8900woijdbdjkwowodiuyfue9u789",
        "name": "Jagadesh",
        "birth_year": 2000,
        "birth_month": 11,
        "birth_day": 15,
        "gender": "Male",
        "height_cm": 182.22,
        "weight_kg": 107,
        "activity_level": "lightly_active",
        "allergies": ["Nuts", "Dairy"],
        "diseases": ["Diabetes"],
        "dietary_preferences": ["Vegetarian"],
        "preferred_cuisines": ["Indian", "South Indian"],
        "foods_aggravating_digestive_issues": ["Spicy Foods", "Fried Foods"],
    }

    profile = build_profile(raw_profile)
    print(format_profile(profile))


if __name__ == "__main__":
    main()

