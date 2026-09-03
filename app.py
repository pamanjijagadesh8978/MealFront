import json
import time
import uuid
from datetime import date

import requests
import streamlit as st

from user_profile import build_profile, format_profile
from goals import (
    ACTIVITY_LEVELS,
    ALLERGIES,
    VERIFIED_DISEASES,
    CALORIES_RECOMMENDATIONS,
    GOAL_RECOMMENDATIONS,
    MEAL_PROPORTIONS,
    CUISINE_EATING_PATTERNS,
    DIGESTIVE_AGGRAVATING_FOODS,
)

st.set_page_config(page_title="Nutrition & Fitness Profile Builder", page_icon="🥗", layout="wide")

# ---------------------------------------------------------------------------
# Meal Generation API config
# ---------------------------------------------------------------------------
# DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_API_BASE_URL = "https://mealback-recommendation-api-523501105526.asia-south1.run.app"
REQUEST_TIMEOUT_S = 600

# The base URL and API key are no longer exposed in the UI (they were
# previously editable in a sidebar "API Settings" panel, which meant any
# front-end user could see/copy the API key and hit arbitrary base URLs).
# Both are now resolved silently:
#   - api_base_url always comes from DEFAULT_API_BASE_URL above.
#   - api_key always comes from Streamlit secrets (MEAL_API_KEY), which is
#     never rendered to the page. Set it in .streamlit/secrets.toml locally,
#     or the "Secrets" panel on Streamlit Community Cloud.
api_base_url = DEFAULT_API_BASE_URL.rstrip("/")
api_key = st.secrets.get("MEAL_API_KEY", "") if hasattr(st, "secrets") else ""

if not api_key:
    # Only warn — don't block — in case a dev backend has no API_KEYS set.
    # This message is intentionally generic and doesn't reveal any secret
    # value, just that one is missing.
    st.sidebar.warning(
        "⚠️ No MEAL_API_KEY found in secrets. Requests will be sent without "
        "an API key, which only works against a backend with no API_KEYS "
        "configured."
    )


def _api_headers() -> dict:
    """Headers sent on every request to the meal-generation API. Only
    includes X-API-Key when a key is actually set, so a blank key against a
    dev backend with no API_KEYS configured still works (see
    require_api_key()'s no-op path in main.py)."""
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def call_food_recommendations_api(profile: dict) -> tuple[dict, float]:
    """POSTs the profile to /api/v1/food-recommendations and returns a tuple of
    (the full FoodRecommendationsResponse JSON body [user_id, username,
    timestamp, file_path, food_recommendations, token_usage], elapsed_seconds)."""
    start = time.perf_counter()
    resp = requests.post(
        f"{api_base_url}/api/v1/food-recommendations",
        json={"profile": profile},
        headers=_api_headers(),
        timeout=REQUEST_TIMEOUT_S,
    )
    elapsed = time.perf_counter() - start
    if resp.status_code == 401:
        st.error("The API rejected the request: missing or invalid API key. "
                  "Enter the correct key in the sidebar under **API Settings**.")
    elif resp.status_code == 429:
        st.error("Rate limit hit on the meal-generation API. Wait a bit and try again.")
    resp.raise_for_status()
    return resp.json(), elapsed


def call_meal_plan_api(profile: dict, food_recommendations: dict, food_recommendation_id: str = None) -> tuple[dict, float]:
    """POSTs profile + food_recommendations (the `food_recommendations` field
    from the response above) + food_recommendation_id to
    /api/v1/meal-plan-with-ingredients and returns a tuple of (the full
    MealPlanWithIngredientsResponse JSON body [user_id, username, timestamp,
    meal_plan_id, food_recommendation_id, ...file_path fields,
    meal_plan_with_ingredients, token_usage], elapsed_seconds).

    food_recommendation_id is simply echoed back by the API in its response,
    not regenerated - if it isn't sent here, the response's
    `food_recommendation_id` field will come back null."""
    start = time.perf_counter()
    resp = requests.post(
        f"{api_base_url}/api/v1/meal-plan-with-ingredients",
        json={
            "profile": profile,
            "food_recommendations": food_recommendations,
            "food_recommendation_id": food_recommendation_id,
        },
        headers=_api_headers(),
        timeout=REQUEST_TIMEOUT_S,
    )
    elapsed = time.perf_counter() - start
    if resp.status_code == 401:
        st.error("The API rejected the request: missing or invalid API key. "
                  "Enter the correct key in the sidebar under **API Settings**.")
    elif resp.status_code == 429:
        st.error("Rate limit hit on the meal-generation API. Wait a bit and try again.")
    resp.raise_for_status()
    return resp.json(), elapsed


def humanize(key: str) -> str:
    return key.replace("_", " ").title()


def compute_day_macros(day: dict) -> dict:
    """Sums each meal's `meal_totals` for the day to get calories, protein,
    carbs, fat, fiber, sugar and sodium — computed client-side rather than
    trusting the API's own `day_totals` field, so the numbers always reflect
    exactly what's shown in the meal breakdown below them."""
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0,
              "fiber": 0.0, "sugar": 0.0, "sodium": 0.0}
    meal_slots = day.get("meals", {}) or {}
    for meal in meal_slots.values():
        meal_totals = meal.get("meal_totals", {}) or {}
        for key in totals:
            totals[key] += meal_totals.get(key, 0) or 0
    return totals

DIETARY_PREFERENCE_OPTIONS = [
    "Vegetarian", "Non-Vegetarian", "Vegan", "Ovo-Vegetarian (Eggetarian)", "Pescatarian"]

FOOD_RESTRICTIONS = [
    "Dairy-Free", "Gluten-Free", "No Red Meat", "No Beef", "No Pork", "No Duck", "No Mutton"
]

# Sourced directly from goals.py so these match, category-for-category, the
# exact keys the meal-generation backend uses to build its exclusion lists -
# a value here that doesn't exactly match a key in CUISINE_EATING_PATTERNS /
# DIGESTIVE_AGGRAVATING_FOODS would silently produce no cuisine guidance or
# no exclusions for that entry.
CUISINE_OPTIONS = list(CUISINE_EATING_PATTERNS.keys())

DIGESTIVE_ISSUE_FOOD_OPTIONS = list(DIGESTIVE_AGGRAVATING_FOODS.keys())


def bmi_weight_condition(height_cm, weight_kg):
    if height_cm <= 0 or weight_kg <= 0:
        return None, None
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 2)
    if bmi < 18.5:
        condition = "Underweight"
    elif bmi < 25:
        condition = "Normal weight"
    elif bmi < 30:
        condition = "Overweight"
    else:
        condition = "Obese"
    return bmi, condition


def build_cuisine_eating_patterns(preferred_cuisines, custom_eating_pattern=""):
    """Build the cuisine_eating_patterns dict sent to the API.

    Starts from the built-in CUISINE_EATING_PATTERNS (goals.py). If the user
    described their own usual eating habits in the free-text box, that
    description overrides the built-in pattern for every one of their
    preferred cuisines (the API matches guidance per preferred cuisine name,
    so the same user-provided text is applied under each selected cuisine).
    """
    custom_eating_pattern = (custom_eating_pattern or "").strip()
    patterns = dict(CUISINE_EATING_PATTERNS)
    if custom_eating_pattern:
        for cuisine in preferred_cuisines:
            patterns[cuisine] = custom_eating_pattern
    return patterns


def build_export_json(profile, sodium_mg, custom_eating_pattern=""):
    """Reshapes the computed profile dict into the flat export schema."""
    macros = profile["macros"]
    protein, carbs, fats = macros["Protein"], macros["Carbohydrates"], macros["Fats"]

    meal_distribution = {}
    for meal_name, meal_data in profile["meals"].items():
        meal_macros = meal_data["macros"]
        meal_distribution[meal_name] = {
            "percentage": round(MEAL_PROPORTIONS[meal_name] * 100, 2),
            "calories_kcal": meal_data["calories"],
            "protein_gr": meal_macros["Protein"]["grams"],
            "carbs_gr": meal_macros["Carbohydrates"]["grams"],
            "fats_gr": meal_macros["Fats"]["grams"],
            "fiber_gr": meal_data["fiber_g"],
            "sodium_mg": round(sodium_mg * MEAL_PROPORTIONS[meal_name], 1),
        }

    return {
        "username": profile["name"],
        "user_id": profile["user_id"],
        "age_years": profile["age"],
        "gender": profile["gender"],
        "height_cm": profile["height_cm"],
        "weight_kg": profile["weight_kg"],
        "activity_level": profile["activity_level"],
        "allergies": profile["allergies"],
        "diseases": profile["diseases"],
        "dietary_preferences": profile["dietary_preferences"],
        "preferred_cuisines": profile["preferred_cuisines"],
        # Sent through explicitly so the backend (RedMeal.py) always builds
        # meal-plan prompts from the exact same eating-pattern definitions
        # this frontend shows/uses, even if goals.py on the API side drifts
        # out of sync. The API falls back to its own goals.py copy of
        # CUISINE_EATING_PATTERNS if this is omitted or empty. If the user
        # described their own eating habits above, that description is used
        # here instead of the built-in pattern - see
        # build_cuisine_eating_patterns().
        "cuisine_eating_patterns": build_cuisine_eating_patterns(
            profile["preferred_cuisines"], custom_eating_pattern
        ),
        "foods_aggravating_digestive_issues": profile["foods_aggravating_digestive_issues"],
        "goal": [profile["goal"]],
        "restricted_foods": profile.get("restricted_foods", []),
        "calories_kcal": profile["calories"],
        "protein_lower_limit_gr": protein["min_g"],
        "protein_upper_limit_gr": protein["max_g"],
        "protein_target_gr": protein["target_g"],
        "carbs_lower_limit_gr": carbs["min_g"],
        "carbs_upper_limit_gr": carbs["max_g"],
        "carbs_target_gr": carbs["target_g"],
        "fats_lower_limit_gr": fats["min_g"],
        "fats_upper_limit_gr": fats["max_g"],
        "fats_target_gr": fats["target_g"],
        "fiber_gr": profile["fiber_g"],
        "sodium_mg": sodium_mg,
        "meal_distribution": meal_distribution,
    }


st.title("🥗 Nutrition & Fitness Profile Builder")
st.caption("Fill in your details below to generate a personalized calorie, macro, and meal plan.")

# ---------------------------------------------------------------------------
# Personal details
# ---------------------------------------------------------------------------
st.header("1. Personal Details")
col1, col2, col3 = st.columns(3)
with col1:
    name = st.text_input("Name", value="Jagadesh")
    gender = st.selectbox("Gender", ["Male", "Female"])
with col2:
    birth_date = st.date_input(
        "Date of birth", value=date(2000, 11, 15),
        min_value=date(1920, 1, 1), max_value=date.today(),
    )

    height_unit = st.radio("Height unit", ["cm", "ft/in"], horizontal=True, key="height_unit")
    if height_unit == "cm":
        height_cm = st.number_input(
            "Height (cm)", min_value=1.0, max_value=250.0, value=182.22, step=0.1
        )
    else:
        hcol1, hcol2 = st.columns(2)
        with hcol1:
            height_ft = st.number_input("Height (ft)", min_value=0, max_value=8, value=5, step=1)
        with hcol2:
            height_in = st.number_input(
                "Height (in)", min_value=0.0, max_value=11.9, value=11.7, step=0.1
            )
        # 1 ft = 30.48 cm, 1 in = 2.54 cm
        height_cm = round(height_ft * 30.48 + height_in * 2.54, 2)
        st.caption(f"= {height_cm:.2f} cm")
with col3:
    weight_unit = st.radio("Weight unit", ["kg", "lb"], horizontal=True, key="weight_unit")
    if weight_unit == "kg":
        weight_kg = st.number_input(
            "Weight (kg)", min_value=1.0, max_value=400.0, value=107.0, step=0.1
        )
    else:
        weight_lb = st.number_input(
            "Weight (lb)", min_value=2.0, max_value=880.0, value=235.9, step=0.1
        )
        # 1 lb = 0.45359237 kg
        weight_kg = round(weight_lb * 0.45359237, 2)
        st.caption(f"= {weight_kg:.2f} kg")

    activity_level = st.selectbox(
        "Activity level",
        options=list(ACTIVITY_LEVELS.keys()),
        format_func=lambda k: ACTIVITY_LEVELS[k]["name"],
    )
st.caption(ACTIVITY_LEVELS[activity_level]["description"])

bmi_preview, condition_preview = bmi_weight_condition(height_cm, weight_kg)
if bmi_preview is not None:
    st.info(f"Current BMI: **{bmi_preview}** ({condition_preview})")

# ---------------------------------------------------------------------------
# Dietary & health details
# ---------------------------------------------------------------------------
st.header("2. Dietary & Health Details")
col4, col5 = st.columns(2)
with col4:
    allergies = st.multiselect("Allergies", options=list(ALLERGIES.keys()), accept_new_options=True)
    diseases = st.multiselect("Diagnosed conditions", options=VERIFIED_DISEASES)
with col5:
    dietary_preferences = st.multiselect("Dietary preferences", options=DIETARY_PREFERENCE_OPTIONS, default=["Vegetarian"])
    preferred_cuisines = st.multiselect("Preferred cuisines", options=CUISINE_OPTIONS, default=["North American", "South Indian"], accept_new_options=True)
    restricted_foods = st.multiselect("Restricted foods", options=FOOD_RESTRICTIONS, default=["No Red Meat"], accept_new_options=True)

custom_eating_pattern = st.text_area(
    "Describe your usual eating pattern (optional)",
    value="",
    placeholder=(
        "e.g. I usually eat idli or dosa for breakfast, and rice with curry "
        "for lunch and dinner."
    ),
    help=(
        "Tell us what you actually eat day-to-day. If you fill this in, it "
        "replaces the built-in typical eating pattern for each of your "
        "preferred cuisines above when the meal plan is generated - leave "
        "it blank to use the standard patterns instead."
    ),
)

st.subheader("Foods That Cause or Aggravate Digestive Issues")
has_digestive_triggers = st.radio(
    "Do specific foods or beverages cause or aggravate your digestive symptoms?",
    options=["No", "Yes"],
    horizontal=True,
    key="has_digestive_triggers_radio",
)

foods_aggravating_digestive_issues = []

if has_digestive_triggers == "Yes":
    foods_aggravating_digestive_issues = st.multiselect(
        "What specific foods or beverages cause or aggravate your digestive symptoms?",
        options=DIGESTIVE_ISSUE_FOOD_OPTIONS,
        accept_new_options=True,
        help="Pick any that apply, or type your own and press Enter to add it.",
    )

# ---------------------------------------------------------------------------
# Goal & calorie option (reactive to BMI-based recommendations)
# ---------------------------------------------------------------------------
st.header("3. Goal & Calorie Plan")

if condition_preview is not None:
    recommended_goals = GOAL_RECOMMENDATIONS[condition_preview]
    col6, col7 = st.columns(2)
    with col6:
        goal = st.selectbox(
            f"Goal (recommended for {condition_preview})",
            options=recommended_goals,
        )
    with col7:
        calorie_options = CALORIES_RECOMMENDATIONS[goal]

        def _calorie_option_label(k, _options=calorie_options):
            change = _options[k]["calorie_change"]
            if change > 0:
                kind = "Surplus"
            elif change < 0:
                kind = "Deficit"
            else:
                kind = "Maintain"
            if change != 0:
                return (
                    f"{kind} — {change:+d} kcal/day "
                    f"({_options[k]['expected_weight_change_per_week']})"
                )
            return f"{kind} — no change"

        calorie_option = st.selectbox(
            "Calorie plan option (deficit / surplus / maintain)",
            options=list(calorie_options.keys()),
            format_func=_calorie_option_label,
            help=(
                "Choose how large a calorie deficit (for fat loss) or surplus "
                "(for muscle gain) you'd like. If the amount you pick exceeds the "
                "safe limit for your calculated TDEE, it will automatically be "
                "capped to a safe value after you click Generate — you'll see "
                "both the requested and the final (effective) numbers in the "
                "results."
            ),
        )
        st.caption(calorie_options[calorie_option]["description"])
else:
    st.warning("Enter a valid height and weight above to see goal recommendations.")
    goal, calorie_option = None, None

sodium_mg = st.number_input(
    "Daily sodium target (mg)", min_value=0, max_value=10000, value=2300, step=100,
    help="Not computed elsewhere in the pipeline — defaults to the standard 2300 mg/day guideline. Used only in the JSON export below.",
)

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
st.divider()
generate = st.button("✨ Generate Profile", type="primary", width='stretch')

if generate:
    raw_profile = {
        "user_id": st.session_state.get("user_id") or str(uuid.uuid4()),
        "name": name,
        "birth_year": birth_date.year,
        "birth_month": birth_date.month,
        "birth_day": birth_date.day,
        "gender": gender,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "activity_level": activity_level,
        "allergies": allergies,
        "diseases": diseases,
        "dietary_preferences": dietary_preferences,
        "preferred_cuisines": preferred_cuisines,
        "foods_aggravating_digestive_issues": foods_aggravating_digestive_issues,
        "has_digestive_triggers": has_digestive_triggers == "Yes",
        "restricted_foods": restricted_foods,
        "goal": goal,
        "calorie_option": calorie_option,
    }
    st.session_state["user_id"] = raw_profile["user_id"]

    try:
        profile = build_profile(raw_profile)
    except (ValueError, KeyError) as e:
        st.error(f"Could not generate profile: {e}")
    else:
        st.session_state["profile"] = profile
        st.session_state["sodium_mg"] = sodium_mg
        st.session_state["custom_eating_pattern"] = custom_eating_pattern
        st.session_state["has_digestive_triggers"] = has_digestive_triggers == "Yes"

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
if "profile" in st.session_state:
    profile = st.session_state["profile"]
    st.header(f"📋 Profile Summary — {profile['name']}")
    st.caption(f"User ID: {profile['user_id']}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Age", f"{profile['age']} yrs")
    m2.metric("BMI", f"{profile['bmi']}", profile["weight_condition"])
    m3.metric("TDEE", f"{profile['tdee']:.0f} kcal")
    m4.metric("Daily Target", f"{profile['calories']:.0f} kcal")

    tabs = st.tabs(["Overview", "Calorie Options", "Macronutrients", "Meal Plan", "Raw Report", "JSON Export"])

    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Personal Details")
            st.write(f"**Gender:** {profile['gender']}")
            st.write(f"**Height:** {profile['height_cm']} cm")
            st.write(f"**Weight:** {profile['weight_kg']} kg")
            st.write(f"**Activity Level:** {profile['activity_level'].replace('_', ' ').title()}")
            st.subheader("Goal")
            st.write(f"**Selected:** {profile['goal']}")
            other_goals = [g for g in profile["recommended_goals"] if g != profile["goal"]]
            st.write(f"**Other options:** {', '.join(other_goals) or 'None'}")
        with c2:
            st.subheader("Dietary & Health")
            st.write(f"**Allergies:** {', '.join(profile['allergies']) or 'None'}")
            st.write(f"**Diseases:** {', '.join(profile['diseases']) or 'None'}")
            st.write(f"**Dietary Preferences:** {', '.join(profile['dietary_preferences']) or 'None'}")
            st.write(f"**Preferred Cuisines:** {', '.join(profile['preferred_cuisines']) or 'None'}")
            if st.session_state.get("has_digestive_triggers"):
                st.write(f"**Foods to Avoid:** {', '.join(profile['foods_aggravating_digestive_issues']) or 'None'}")
            else:
                st.write("**Foods to Avoid:** None reported")

        st.subheader("Calorie Summary")
        sign = "+" if profile["calorie_change"] > 0 else ""
        st.write(f"**Selected Option:** {profile['calorie_option']} ({sign}{profile['calorie_change']} kcal/day)")
        st.write(f"**Expected Change:** {profile['expected_weight_change_per_week']}")
        st.write(f"**Notes:** {profile['calorie_description']}")
        st.write(f"**Fiber Target:** {profile['fiber_g']} g/day")

    with tabs[1]:
        rows = []
        for key, opt in profile["available_calorie_options"].items():
            rows.append({
                "Option": key,
                "Recommended": f"{opt['recommended_change']:+d} kcal",
                "Effective": f"{opt['effective_change']:+d} kcal",
                "Adjusted": "Yes" if opt["adjusted"] else "No",
                "Daily Calories": f"{opt['daily_calories']:.0f} kcal",
                "Expected Change": opt["expected_weight_change_per_week"],
                "Description": opt["description"],
            })
        st.dataframe(rows, width='stretch', hide_index=True)

    with tabs[2]:
        for macro_name, macro_data in profile["macros"].items():
            with st.container(border=True):
                st.markdown(f"**{macro_name}**")
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Target", f"{macro_data['target_g']} g", f"{macro_data['target_calories']:.0f} kcal")
                mc2.metric("Min", f"{macro_data['min_g']} g")
                mc3.metric("Max", f"{macro_data['max_g']} g")
                st.caption(macro_data["description"])
                if "warning" in macro_data:
                    st.warning(macro_data["warning"])
        total_target_cals = sum(m["target_calories"] for m in profile["macros"].values())
        st.info(f"Macro calories total: {total_target_cals:.0f} kcal (target: {profile['calories']:.0f} kcal)")

    with tabs[3]:
        for meal_name, meal_data in profile["meals"].items():
            with st.expander(f"{meal_name.replace('_', ' ').title()} — {meal_data['calories']:.0f} kcal", expanded=True):
                mrows = []
                for macro_name, vals in meal_data["macros"].items():
                    mrows.append({"Macro": macro_name, "Grams": vals["grams"], "Calories": f"{vals['calories']:.0f}"})
                st.dataframe(mrows, width='stretch', hide_index=True)
                st.write(f"**Fiber:** {meal_data['fiber_g']} g")
                if meal_data.get("guidance"):
                    st.write(f"**Focus on:** {', '.join(meal_data['guidance'])}")

    with tabs[4]:
        st.code(format_profile(profile), language=None)

    with tabs[5]:
        st.caption(
            "A flat JSON representation of this profile, ready to copy or feed into "
            "another system. Click the copy icon in the top-right corner of the code block."
        )
        export_json = build_export_json(
            profile,
            st.session_state.get("sodium_mg", 2300),
            st.session_state.get("custom_eating_pattern", ""),
        )
        json_str = json.dumps(export_json, indent=4)
        st.code(json_str, language="json")
        st.download_button(
            "⬇️ Download JSON",
            data=json_str,
            file_name=f"{profile['name'].replace(' ', '_').lower()}_profile.json",
            mime="application/json",
            width='stretch',
        )

    # -----------------------------------------------------------------
    # Step 2: Food Recommendations (Stage 1 - GreenFoods)
    # -----------------------------------------------------------------
    st.divider()
    st.header("🥦 2. Food Recommendations")
    st.caption(
        "Calls the Meal Generation API's Stage 1 endpoint "
        "(`POST /api/v1/food-recommendations`) with your profile above."
    )

    get_recs = st.button("🥦 Get Food Recommendations", type="primary", width='stretch')

    if get_recs:
        api_profile = build_export_json(
            profile,
            st.session_state.get("sodium_mg", 2300),
            st.session_state.get("custom_eating_pattern", ""),
        )
        try:
            with st.spinner("Contacting food-recommendations service…"):
                food_recs_response, food_recs_elapsed_s = call_food_recommendations_api(api_profile)
        except requests.exceptions.RequestException as e:
            st.error(f"Could not reach the food-recommendations API: {e}")
        except ValueError as e:
            st.error(f"The API returned a response that wasn't valid JSON: {e}")
        else:
            st.session_state["food_recs_response"] = food_recs_response
            st.session_state["food_recs_elapsed_s"] = food_recs_elapsed_s
            # Any previously generated meal plan is now stale.
            st.session_state.pop("meal_plan_response", None)
            # Selections were made against the old set of recommended items;
            # they no longer apply to the freshly generated list.
            st.session_state.pop("selected_food_items", None)

    if "food_recs_response" in st.session_state:
        food_recs_response = st.session_state["food_recs_response"]
        # This is exactly the `food_recommendations` field: a dict of
        # category_name -> list[str] (e.g. "protein": ["Skinless chicken breast", ...]).
        # user_id / food_recommendation_id are top-level fields on the
        # FoodRecommendationsResponse (sibling to `food_recommendations`),
        # not nested inside the food_recommendations object itself.
        food_recommendations_raw = food_recs_response.get("food_recommendations", {}) or {}
        id_keys = {"user_id", "food_recommendation_id"}
        food_recommendations = {k: v for k, v in food_recommendations_raw.items() if k not in id_keys}
        resp_user_id = food_recs_response.get("user_id", food_recommendations_raw.get("user_id", "—"))
        resp_food_rec_id = food_recs_response.get(
            "food_recommendation_id", food_recommendations_raw.get("food_recommendation_id", "—")
        )
        food_recs_elapsed_s = st.session_state.get("food_recs_elapsed_s")
        elapsed_suffix = f" — took {food_recs_elapsed_s:.2f}s" if food_recs_elapsed_s is not None else ""
        st.success(f"Food recommendations ready (generated {food_recs_response.get('timestamp', '')}){elapsed_suffix}.")

        id_col1, id_col2, id_col3 = st.columns(3)
        id_col1.caption(f"**User ID:** {resp_user_id}")
        id_col2.caption(f"**Food Recommendation ID:** {resp_food_rec_id}")
        if food_recs_elapsed_s is not None:
            id_col3.caption(f"**Response Time:** {food_recs_elapsed_s:.2f}s")

        food_recs_json = json.dumps(food_recs_response, indent=4)
        st.download_button(
            "⬇️ Download Food Recommendations JSON",
            data=food_recs_json,
            file_name=f"{profile['name'].replace(' ', '_').lower()}_food_recommendations.json",
            mime="application/json",
            width='stretch',
        )

        # Persisted checkbox state: {category: {item: bool}}. Defaults to all
        # items selected the first time we see this response.
        selection_state = st.session_state.setdefault("selected_food_items", {})

        if food_recommendations:
            st.caption(
                "Uncheck any items you'd like to exclude. Only the checked items "
                "below will be sent to the meal plan generator."
            )
            sel_col1, sel_col2, _ = st.columns([1, 1, 4])
            if sel_col1.button("Select all", width='stretch'):
                for category, items in food_recommendations.items():
                    selection_state[category] = {item: True for item in items}
                st.rerun()
            if sel_col2.button("Deselect all", width='stretch'):
                for category, items in food_recommendations.items():
                    selection_state[category] = {item: False for item in items}
                st.rerun()

            category_keys = list(food_recommendations.keys())
            cat_tabs = st.tabs([humanize(k) for k in category_keys])
            for tab, category in zip(cat_tabs, category_keys):
                with tab:
                    # De-duplicate while preserving order, in case the backend
                    # returned the same item twice for this category.
                    items = list(dict.fromkeys(food_recommendations[category]))
                    if not items:
                        st.caption("No items in this category.")
                    else:
                        cat_selection = selection_state.setdefault(category, {})
                        # Render as a tidy multi-column checkbox grid rather than one long list.
                        n_cols = 2 if len(items) > 6 else 1
                        cols = st.columns(n_cols)
                        for i, item in enumerate(items):
                            # Default new/unseen items to selected.
                            default_checked = cat_selection.get(item, True)
                            checked = cols[i % n_cols].checkbox(
                                item,
                                value=default_checked,
                                key=f"food_item_{category}_{item}_{i}",
                            )
                            cat_selection[item] = checked

            # Only the checked items get sent on to meal-plan generation.
            selected_food_recommendations = {
                category: [item for item in items if selection_state.get(category, {}).get(item, True)]
                for category, items in food_recommendations.items()
            }

            total_selected = sum(len(v) for v in selected_food_recommendations.values())
            total_available = sum(len(v) for v in food_recommendations.values())
            st.caption(f"**{total_selected} of {total_available}** food items selected.")
        else:
            st.warning("The API response didn't include a `food_recommendations` field.")
            selected_food_recommendations = {}

        with st.expander("Raw API response"):
            st.json(food_recs_response)

        # -----------------------------------------------------------------
        # Step 3: Meal Plan with Ingredients (Stages 2-4 - MealGeneration)
        # -----------------------------------------------------------------
        st.divider()
        st.header("🍽️ 3. Generate Meal Plan")
        st.caption(
            "Calls the Meal Generation API's Stages 2-4 endpoint "
            "(`POST /api/v1/meal-plan-with-ingredients`) using your profile and "
            "the food recommendations above."
        )

        generate_plan_disabled = not any(selected_food_recommendations.values())
        if generate_plan_disabled:
            st.warning("Select at least one food item above before generating a meal plan.")

        generate_plan = st.button(
            "🍽️ Generate Meal Plan with Ingredients",
            type="primary",
            width='stretch',
            disabled=generate_plan_disabled,
        )

        if generate_plan:
            try:
                with st.spinner(
                    "Generating your multi-day meal plan with ingredients — this can "
                    "take a minute or two…"
                ):
                    api_profile = build_export_json(
                        profile,
                        st.session_state.get("sodium_mg", 2300),
                        st.session_state.get("custom_eating_pattern", ""),
                    )
                    meal_plan_response, meal_plan_elapsed_s = call_meal_plan_api(
                        api_profile, selected_food_recommendations, resp_food_rec_id
                    )
            except requests.exceptions.RequestException as e:
                st.error(f"Could not reach the meal-plan API: {e}")
            except ValueError as e:
                st.error(f"The API returned a response that wasn't valid JSON: {e}")
            else:
                st.session_state["meal_plan_response"] = meal_plan_response
                st.session_state["meal_plan_elapsed_s"] = meal_plan_elapsed_s

        if "meal_plan_response" in st.session_state:
            meal_plan_response = st.session_state["meal_plan_response"]
            # Current API shape: user_id / username / timestamp / meal_plan_id /
            # food_recommendation_id are top-level, and `days`, `plan_totals`,
            # `plan_average_daily_totals` all live nested one level down inside
            # `meal_plan_with_macros` (not top-level, and not the old
            # `meal_plan_with_ingredients` key).
            meal_plan = meal_plan_response.get("meal_plan_with_macros", {}) or {}
            days = meal_plan.get("days", [])
            mp_user_id = meal_plan_response.get("user_id", "—")
            meal_plan_id = meal_plan_response.get("meal_plan_id", "—")
            plan_totals = meal_plan.get("plan_totals", {}) or {}
            plan_avg_totals = meal_plan.get("plan_average_daily_totals", {}) or {}
            meal_plan_elapsed_s = st.session_state.get("meal_plan_elapsed_s")
            elapsed_suffix = f" — took {meal_plan_elapsed_s:.2f}s" if meal_plan_elapsed_s is not None else ""
            st.success(f"Meal plan ready (generated {meal_plan_response.get('timestamp', '')}){elapsed_suffix}.")

            mp_id_col1, mp_id_col2, mp_id_col3 = st.columns(3)
            mp_id_col1.caption(f"**User ID:** {mp_user_id}")
            mp_id_col2.caption(f"**Meal Plan ID:** {meal_plan_id}")
            if meal_plan_elapsed_s is not None:
                mp_id_col3.caption(f"**Response Time:** {meal_plan_elapsed_s:.2f}s")

            if plan_totals or plan_avg_totals:
                pt_col1, pt_col2, pt_col3, pt_col4 = st.columns(4)
                pt_col1.metric("Plan Total Calories", f"{plan_totals.get('calories') or 0:.0f}")
                pt_col2.metric("Plan Total Protein", f"{plan_totals.get('protein') or 0:.0f} g")
                pt_col3.metric("Avg Daily Calories", f"{plan_avg_totals.get('calories') or 0:.0f}")
                pt_col4.metric("Avg Daily Protein", f"{plan_avg_totals.get('protein') or 0:.0f} g")

            if days:
                day_labels = [f"Day {d.get('day', i + 1)}" for i, d in enumerate(days)]
                day_tabs = st.tabs(day_labels)
                for tab, day in zip(day_tabs, days):
                    with tab:
                        # Meal slots now live under the `meals` key of each day
                        # (rather than as sibling keys of `day` itself).
                        meal_slots = day.get("meals", {}) or {}
                        # Computed client-side from each meal's meal_totals, so
                        # it's guaranteed consistent with the meal breakdown
                        # below even if the API's own day_totals is missing.
                        computed_day_macros = compute_day_macros(day)

                        st.markdown("**Day totals**")
                        dt_col1, dt_col2, dt_col3, dt_col4 = st.columns(4)
                        dt_col1.metric("Calories", f"{computed_day_macros['calories']:.0f}")
                        dt_col2.metric("Protein", f"{computed_day_macros['protein']:.0f} g")
                        dt_col3.metric("Carbs", f"{computed_day_macros['carbs']:.0f} g")
                        dt_col4.metric("Fat", f"{computed_day_macros['fat']:.0f} g")

                        dt_col5, dt_col6, dt_col7 = st.columns(3)
                        dt_col5.caption(f"**Fiber:** {computed_day_macros['fiber']:.1f} g")
                        dt_col6.caption(f"**Sugar:** {computed_day_macros['sugar']:.1f} g")
                        dt_col7.caption(f"**Sodium:** {computed_day_macros['sodium']:.0f} mg")

                        for meal_key, meal in meal_slots.items():
                            dish_name = meal.get("dish_name", humanize(meal_key))
                            meal_totals = meal.get("meal_totals", {}) or {}
                            protein_g = meal_totals.get("protein")
                            label = f"{humanize(meal_key)} — {dish_name}"
                            if protein_g is not None:
                                label += f" ({protein_g:.0f} g protein)"
                            with st.expander(label, expanded=(meal_key == "breakfast")):
                                if meal.get("description"):
                                    st.write(meal["description"])

                                if meal_totals:
                                    st.markdown("**Meal totals:**")
                                    totals_rows = [
                                        {"Nutrient": "Calories", "Amount": f"{meal_totals.get('calories') or 0:.0f}"},
                                        {"Nutrient": "Protein (g)", "Amount": f"{meal_totals.get('protein') or 0:.1f}"},
                                        {"Nutrient": "Carbs (g)", "Amount": f"{meal_totals.get('carbs') or 0:.1f}"},
                                        {"Nutrient": "Fat (g)", "Amount": f"{meal_totals.get('fat') or 0:.1f}"},
                                        {"Nutrient": "Fiber (g)", "Amount": f"{meal_totals.get('fiber') or 0:.1f}"},
                                        {"Nutrient": "Sugar (g)", "Amount": f"{meal_totals.get('sugar') or 0:.1f}"},
                                        {"Nutrient": "Sodium (mg)", "Amount": f"{meal_totals.get('sodium') or 0:.0f}"},
                                    ]
                                    st.dataframe(totals_rows, width='stretch', hide_index=True)

                                ingredients = meal.get("ingredients", [])
                                if ingredients:
                                    st.markdown("**Ingredients:**")
                                    ing_rows = []
                                    for ing in ingredients:
                                        macros = ing.get("scaled_macros", {}) or {}
                                        ing_rows.append({
                                            "Ingredient": ing.get("ingredient_name", ""),
                                            "Selected Ingrediant": ing.get("selected_food_name", ""),
                                            "LLM Generated": ing.get("source") == "llm_generated",
                                            "Quantity": ing.get("quantity", ""),
                                            "Calories": f"{macros.get('calories') or 0:.0f}" if macros else "",
                                            "Protein (g)": f"{macros.get('protein') or 0:.1f}" if macros else "",
                                            "Carbs (g)": f"{macros.get('carbs') or 0:.1f}" if macros else "",
                                            "Fat (g)": f"{macros.get('fat') or 0:.1f}" if macros else "",
                                            "Fiber (g)": f"{macros.get('fiber') or 0:.1f}" if macros else "",
                                            "Sugar (g)": f"{macros.get('sugar') or 0:.1f}" if macros else "",
                                            "Sodium (mg)": f"{macros.get('sodium') or 0:.0f}" if macros else "",
                                        })
                                    st.dataframe(ing_rows, width='stretch', hide_index=True)

                                steps = meal.get("preparation_steps", [])
                                if steps:
                                    st.markdown("**Preparation:**")
                                    for i, step in enumerate(steps, 1):
                                        st.markdown(f"{i}. {step}")
            else:
                st.warning("The API response didn't include any `days`.")

            meal_plan_json = json.dumps(meal_plan_response, indent=4)
            st.download_button(
                "⬇️ Download Meal Plan JSON",
                data=meal_plan_json,
                file_name=f"{profile['name'].replace(' ', '_').lower()}_meal_plan.json",
                mime="application/json",
                width='stretch',
            )

            with st.expander("Raw API response"):
                st.json(meal_plan_response)
else:
    st.info("Fill in the form above and click **Generate Profile** to see your results.")
