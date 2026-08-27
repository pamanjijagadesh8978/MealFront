from goals import (
    CALORIES_PER_GRAM,
    CARB_PERCENTAGE,
    MEAL_PROPORTIONS,
    PROTEIN_RECOMMENDATIONS,
    PROTEIN_LEAN_MASS_GAIN_UNDERWEIGHT,
    FAT_PERCENTAGES,
)


def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
) -> float:
    """
    Calculate Total Daily Energy Expenditure (TDEE).

    Parameters:
        weight_kg (float): Body weight in kilograms.
        height_cm (float): Height in centimeters.
        age (int): Age in years.
        gender (str): 'male' or 'female'.
        activity_level (str): One of:
            - sedentary
            - lightly_active
            - moderately_active
            - very_active
            - extra_active

    Returns:
        float: Estimated TDEE (kcal/day)
    """

    gender = gender.lower()

    # Calculate BMR using the Mifflin-St Jeor Equation
    if gender == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    elif gender == "female":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    else:
        raise ValueError("Gender must be 'male' or 'female'.")

    activity_factors = {
        "sedentary": 1.20,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.90,
    }

    if activity_level not in activity_factors:
        raise ValueError(
            f"Invalid activity level. Choose from: {list(activity_factors.keys())}"
        )

    tdee = bmr * activity_factors[activity_level]

    return round(tdee, 2)


def _gram_range_from_g_per_kg(weight_kg, min_g_per_kg, max_g_per_kg, cals_per_g):
    """Helper: builds a min/max/target grams+calories block from a g/kg range."""
    min_g = round(weight_kg * min_g_per_kg, 1)
    max_g = round(weight_kg * max_g_per_kg, 1)
    target_g = round((min_g + max_g) / 2, 1)

    return {
        "min_g": min_g,
        "max_g": max_g,
        "target_g": target_g,
        "min_calories": round(min_g * cals_per_g, 1),
        "max_calories": round(max_g * cals_per_g, 1),
        "target_calories": round(target_g * cals_per_g, 1),
    }

def calculate_ideal_body_weight(height_cm, gender):
    """
    Calculate Ideal Body Weight (IBW) using the Devine formula.

    Male:
        IBW = 50 + 2.3 kg for every inch over 5 feet

    Female:
        IBW = 45.5 + 2.3 kg for every inch over 5 feet
    """

    gender = gender.lower()

    height_inches = height_cm / 2.54

    five_feet_inches = 60

    if height_inches <= five_feet_inches:
        if gender == "male":
            return 50.0
        elif gender == "female":
            return 45.5
        else:
            raise ValueError(
                "Gender must be 'male' or 'female'."
            )

    inches_over_five_feet = (
        height_inches - five_feet_inches
    )

    if gender == "male":
        ibw = 50 + (
            2.3 * inches_over_five_feet
        )

    elif gender == "female":
        ibw = 45.5 + (
            2.3 * inches_over_five_feet
        )

    else:
        raise ValueError(
            "Gender must be 'male' or 'female'."
        )

    return round(ibw, 1)

def calculate_adjusted_body_weight(
    actual_weight_kg,
    ideal_body_weight_kg,
):
    """
    Calculate Adjusted Body Weight (AdjBW).

    AdjBW = IBW + 0.4 × (Actual BW − IBW)
    """

    adjusted_bw = (
        ideal_body_weight_kg
        + 0.4 * (
            actual_weight_kg
            - ideal_body_weight_kg
        )
    )

    return round(adjusted_bw, 1)


def _weight_condition_from_bmi(bmi):
    """Mirrors the BMI thresholds used in user_profile.build_profile /
    app.bmi_weight_condition, so protein tiers line up with the same
    weight-condition labels shown elsewhere in the app."""
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal weight"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def calculate_macros(
    weight_kg,
    activity_level,
    total_calories,
    goal,
    bmi,
    height_cm,
    gender,
):
    """
    Computes Protein, Carbohydrate, and Fat targets.

    Each macro is calculated independently first, using its own rule:
      - Protein:        g/kg body weight, based on weight condition
                         (BMI-derived) and activity level. Uses Adjusted
                         Body Weight instead of actual weight when BMI >= 30
                         (Obese), and factors in `goal` only for the
                         Underweight + "Muscle Gain (Bulking)" + high-activity
                         lean-mass-gain override tier.
      - Carbohydrates:  fixed 50-60% of total calories (standard diet)
      - Fats:            fixed 30-35% of total calories (standard diet)

    Because protein is weight-based (not calorie-based), the three targets
    will not automatically sum to total_calories. They are reconciled with
    this priority:

      1. Protein is fixed - it's a body-weight requirement, not a share
         of calories, and is never reduced to make room for the others.
      2. Fat must stay within its 30-35% floor/ceiling - this is a hard
         physiological requirement, not just a preference.
      3. Carbohydrates absorb whatever calories remain after protein and
         fat are satisfied. They're capped to the 50-60% range where
         possible; if there isn't enough room, a warning is attached
         instead of silently violating the range.
    """
    macros = {}
    cals_per_g = CALORIES_PER_GRAM

    # ===========================================================
    # 1. PROTEIN - g/kg rule, keyed by weight condition (BMI-derived)
    #    and activity level. AdjBW is used instead of actual body
    #    weight when BMI >= 30 (Obese). See goals.PROTEIN_RECOMMENDATIONS
    #    for the full tier table and the mapping notes.
    # ===========================================================
    weight_condition = _weight_condition_from_bmi(bmi)

    if activity_level not in PROTEIN_RECOMMENDATIONS["Normal weight"]:
        raise ValueError(
            f"Invalid activity level '{activity_level}' for protein "
            f"calculation. Choose from: "
            f"{list(PROTEIN_RECOMMENDATIONS['Normal weight'].keys())}"
        )

    # Underweight + Muscle Gain (Bulking) + high activity: use the
    # dedicated lean-mass-gain tier instead of the plain Underweight table.
    use_lean_mass_gain_tier = (
        weight_condition == "Underweight"
        and goal == "Muscle Gain (Bulking)"
        and activity_level in ("very_active", "extra_active")
    )

    if use_lean_mass_gain_tier:
        protein_min_g_per_kg = PROTEIN_LEAN_MASS_GAIN_UNDERWEIGHT["min_g_per_kg"]
        protein_max_g_per_kg = PROTEIN_LEAN_MASS_GAIN_UNDERWEIGHT["max_g_per_kg"]
        tier_description = "lean mass/muscle gain with resistance training"
    else:
        condition_table = PROTEIN_RECOMMENDATIONS.get(
            weight_condition, PROTEIN_RECOMMENDATIONS["Normal weight"]
        )
        protein_min_g_per_kg = condition_table[activity_level]["min_g_per_kg"]
        protein_max_g_per_kg = condition_table[activity_level]["max_g_per_kg"]
        tier_description = f"{weight_condition}, {activity_level.replace('_', ' ')}"

    if weight_condition == "Obese":
        # Obesity rule: g/kg of Adjusted Body Weight (BMI >= 30).
        ibw = calculate_ideal_body_weight(height_cm=height_cm, gender=gender)
        adjusted_bw = calculate_adjusted_body_weight(
            actual_weight_kg=weight_kg,
            ideal_body_weight_kg=ibw,
        )
        basis_weight_kg = adjusted_bw
        protein_basis = "Adjusted Body Weight"

        protein_description = (
            f"BMI is {bmi:.1f} (obesity range). Protein is calculated using "
            f"adjusted body weight ({adjusted_bw:.1f} kg) at "
            f"{protein_min_g_per_kg:.2f}-{protein_max_g_per_kg:.2f} g/kg/day "
            f"for {tier_description}. Target is the average of the range."
        )
        protein_extra = {
            "actual_weight_kg": weight_kg,
            "ideal_body_weight_kg": ibw,
            "adjusted_body_weight_kg": adjusted_bw,
        }
    else:
        basis_weight_kg = weight_kg
        protein_basis = "Actual Body Weight"

        protein_description = (
            f"Protein target is based on {protein_min_g_per_kg:.2f}-"
            f"{protein_max_g_per_kg:.2f} g/kg body weight for "
            f"{tier_description}. Target is the average of the range."
        )
        protein_extra = {}

    protein_min_g = round(basis_weight_kg * protein_min_g_per_kg, 1)
    protein_max_g = round(basis_weight_kg * protein_max_g_per_kg, 1)
    protein_target_g = round((protein_min_g + protein_max_g) / 2, 1)

    protein_target_calories = round(protein_target_g * cals_per_g["Protein"], 1)

    protein = {
        "min_g": protein_min_g,
        "max_g": protein_max_g,
        "target_g": protein_target_g,
        "min_calories": round(protein_min_g * cals_per_g["Protein"], 1),
        "max_calories": round(protein_max_g * cals_per_g["Protein"], 1),
        "target_calories": protein_target_calories,
        "basis": protein_basis,
        "min_g_per_kg": protein_min_g_per_kg,
        "max_g_per_kg": protein_max_g_per_kg,
        "description": protein_description,
        **protein_extra,
    }
    macros["Protein"] = protein

    # ===========================================================
    # 2. CARBOHYDRATES - fixed 50-60% of TOTAL calories (standard diet)
    #    (computed here as the *target* range; the final grams
    #    awarded are reconciled below, in step 4)
    # ===========================================================
    carb_min_percent = CARB_PERCENTAGE["min_percent"]
    carb_max_percent = CARB_PERCENTAGE["max_percent"]
    carb_target_percent = (carb_min_percent + carb_max_percent) / 2

    carb_min_calories = total_calories * carb_min_percent / 100
    carb_max_calories = total_calories * carb_max_percent / 100
    carb_target_calories = total_calories * carb_target_percent / 100

    # ===========================================================
    # 3. FATS - fixed 30-35% of TOTAL calories, target 32.5%
    # ===========================================================
    fat_min_percent = FAT_PERCENTAGES["min_percent"]
    fat_max_percent = FAT_PERCENTAGES["max_percent"]
    fat_target_percent = (fat_min_percent + fat_max_percent) / 2

    fat_min_calories = total_calories * fat_min_percent / 100
    fat_max_calories = total_calories * fat_max_percent / 100
    fat_target_calories = total_calories * fat_target_percent / 100

    # ===========================================================
    # 4. RECONCILE
    #
    #    Protein is fixed. Carbs and fat then split whatever
    #    calories remain, starting from their target percentages
    #    but scaled so they actually fit - fat's floor/ceiling is
    #    protected first, and carbohydrates absorb the rest.
    # ===========================================================
    remaining_after_protein = max(total_calories - protein_target_calories, 0)

    combined_target = carb_target_calories + fat_target_calories
    scale = (remaining_after_protein / combined_target) if combined_target > 0 else 0

    carb_calories = carb_target_calories * scale
    fat_calories = fat_target_calories * scale

    fat_adjusted = False

    # Protect the fat floor/ceiling - this range is a hard requirement,
    # not just a preference, so it takes priority over hitting the
    # carbohydrate midpoint.
    if fat_calories < fat_min_calories:
        fat_calories = min(fat_min_calories, remaining_after_protein)
        fat_adjusted = True
    elif fat_calories > fat_max_calories:
        fat_calories = fat_max_calories
        fat_adjusted = True

    # Carbohydrates get whatever is left after protein and fat.
    carb_calories = max(remaining_after_protein - fat_calories, 0)

    carb_warning = None
    if carb_calories > carb_max_calories:
        # More calories are available than the standard-diet carb range
        # needs - give the surplus back to fat (still capped at fat's own
        # ceiling).
        leftover = carb_calories - carb_max_calories
        carb_calories = carb_max_calories
        room_in_fat = max(fat_max_calories - fat_calories, 0)
        add_to_fat = min(leftover, room_in_fat)
        if add_to_fat > 0:
            fat_calories += add_to_fat
            fat_adjusted = True
            leftover -= add_to_fat
        if leftover > 0:
            # Neither range has room for the surplus (rare) - rather than
            # discard calories, let carbs absorb the remainder and flag it.
            carb_calories += leftover
            carb_warning = (
                f"Carbohydrate target exceeded the standard-diet range "
                f"({carb_min_percent}-{carb_max_percent}%) because there were "
                f"more calories available than protein and fat (at its "
                f"{fat_max_percent}% ceiling) could use."
            )
    elif carb_calories < carb_min_calories:
        carb_warning = (
            f"Carbohydrate target had to be reduced below the standard-diet "
            f"range ({carb_min_percent}-{carb_max_percent}%) because protein "
            f"and the fat floor ({fat_min_percent}%) take priority within "
            f"the available calories."
        )

    carb_target_g = round(carb_calories / cals_per_g["Carbohydrates"], 1)
    fat_target_g = round(fat_calories / cals_per_g["Fats"], 1)

    carbs = {
        "min_g": round(carb_min_calories / cals_per_g["Carbohydrates"], 1),
        "max_g": round(carb_max_calories / cals_per_g["Carbohydrates"], 1),
        "target_g": carb_target_g,
        "min_calories": round(carb_min_calories, 1),
        "max_calories": round(carb_max_calories, 1),
        "target_calories": round(carb_calories, 1),
        "min_percent": carb_min_percent,
        "target_percent": carb_target_percent,
        "max_percent": carb_max_percent,
        "description": (
            f"Carbohydrates provide {carb_min_percent}-{carb_max_percent}% of "
            f"daily calories (standard-diet range). Target is the average of "
            f"the range ({carb_target_percent:.1f}%)."
        ),
    }
    if carb_warning:
        carbs["warning"] = carb_warning
    macros["Carbohydrates"] = carbs

    fats = {
        "min_g": round(fat_min_calories / cals_per_g["Fats"], 1),
        "max_g": round(fat_max_calories / cals_per_g["Fats"], 1),
        "target_g": fat_target_g,
        "min_calories": round(fat_min_calories, 1),
        "max_calories": round(fat_max_calories, 1),
        "target_calories": round(fat_calories, 1),
        "min_percent": fat_min_percent,
        "target_percent": fat_target_percent,
        "max_percent": fat_max_percent,
        "description": (
            f"Fat provides {fat_min_percent}-{fat_max_percent}% of daily "
            f"calories. Target is the average of the range "
            f"({fat_target_percent:.1f}%)."
        ),
    }
    if fat_adjusted:
        fats["warning"] = (
            f"Fat was adjusted to stay within its required "
            f"{fat_min_percent}-{fat_max_percent}% range given the calories "
            f"available after protein."
        )
    macros["Fats"] = fats

    return macros



def calculate_meal_breakdown(total_calories, macros, meal_proportions=MEAL_PROPORTIONS):
    """
    Splits total calories and each macro's target grams across meals
    according to meal_proportions. Returns a dict keyed by meal name.
    """
    meals = {}
    for meal_name, proportion in meal_proportions.items():
        meal = {
            "calories": round(total_calories * proportion, 1),
            "macros": {},
        }
        for macro_name, macro_data in macros.items():
            meal["macros"][macro_name] = {
                "grams": round(macro_data["target_g"] * proportion, 1),
                "calories": round(macro_data["target_calories"] * proportion, 1),
            }
        meals[meal_name] = meal
    return meals

