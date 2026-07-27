from functools import lru_cache
from typing import List, Dict, Any, Optional, Union, Literal
import json
import time
import sqlalchemy as sa
from pydantic import BaseModel, Field, root_validator, validator, ConfigDict, field_validator, model_validator

# ---------------------------------------------------------------------------
# Approved Category / Sub Category lists — derived from summary.py prompt
# These are the ONLY valid names. Any tag outside these lists is dropped.
# ---------------------------------------------------------------------------

_DEFAULT_APPROVED_CATEGORIES: set = {
    "Politics", "Business", "Economy", "Technology", "Sports",
    "Health & Science", "Education", "Environment", "Society",
    "Entertainment", "Lifestyle", "Explainers & Features",
    "National India", "Global", "State",
}

_APPROVED_CATEGORIES_CACHE_TTL_SECONDS = 300
_SUBCATEGORY_MAPPING_CACHE_TTL_SECONDS = 300

def _parse_approved_categories_config(raw: Any) -> set:
    if raw is None:
        return set()

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return set()

    categories = set()

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                val = item.strip()
                if val:
                    categories.add(val)
            elif isinstance(item, dict):
                # Only read the canonical "name" key — never "label" or "collectionName"
                # (those are UI labels, not approved category names, and would let
                # values like "National" slip through instead of "National India").
                val = item.get("name")
                if isinstance(val, str) and val.strip():
                    categories.add(val.strip())
    elif isinstance(raw, dict):
        nested = raw.get("categories")
        if isinstance(nested, list):
            categories = _parse_approved_categories_config(nested)

    return categories

@lru_cache(maxsize=1)
def _get_approved_categories_cached(cache_bucket: int) -> frozenset:
    try:
        from ..app_db import engine, app_config
        with engine.connect() as db2:
            config_value = db2.execute(
                sa.select(app_config.c.config_value).where(
                    app_config.c.config_key == "approved_categories"
                )
            ).scalar_one_or_none()

        parsed = _parse_approved_categories_config(config_value)
        if parsed:
            return frozenset(parsed)
    except Exception:
        pass

    return frozenset(_DEFAULT_APPROVED_CATEGORIES)

def _approved_categories() -> set:
    cache_bucket = int(time.time() // _APPROVED_CATEGORIES_CACHE_TTL_SECONDS)
    return set(_get_approved_categories_cached(cache_bucket))

_DEFAULT_SUB_CATEGORY_TO_PARENT: dict = {
    # Politics (from summary.py line 385-386)
    "Elections": "Politics",
    "Political Parties": "Politics",
    "Coalitions": "Politics",
    "Centre-State": "Politics",
    "Misconduct": "Politics",
    "Debate": "Politics",
    "Allegations": "Politics",

    # Business (from summary.py line 443)
    "Markets": "Business",
    "Banking": "Business",
    "Finance": "Business",
    "Corporate": "Business",
    "Mergers": "Business",
    "Regulation": "Business",
    "Trade": "Business",
    "Industry": "Business",
    "Agriculture": "Business",
    "Energy": "Business",
    "Infrastructure": "Business",
    "Real Estate": "Business",
    "Startups": "Business",
    "Tourism": "Business",
    "Healthcare": "Business",
    "Telecom": "Business",
    "Media": "Business",

    # Economy (from summary.py line 391-392)
    "Macro Economy": "Economy",
    "Monetary Policy": "Economy",
    "Fiscal Policy": "Economy",
    "Economic Data": "Economy",

    # Health & Science (from summary.py line 394-395)
    "Public Health": "Health & Science",
    "Medicine": "Health & Science",
    "Food Safety": "Health & Science",
    "Health Policy": "Health & Science",

    # Technology (from summary.py line 397-398)
    "Artificial Intelligence": "Technology",
    "Tech Policy": "Technology",
    "Cybersecurity": "Technology",
    "Digital Infrastructure": "Technology",
    "Semiconductors": "Technology",
    "Space Technology": "Technology",

    # Education (from summary.py line 400-401)
    "School Education": "Education",
    "Higher Education": "Education",
    "Entrance Exams": "Education",
    "Govt Jobs": "Education",
    "Education Policy": "Education",

    # Environment (from summary.py line 403-404)
    "Weather": "Environment",
    "Pollution": "Environment",
    "Wildlife": "Environment",
    "Clean Energy": "Environment",
    "Environmental Policy": "Environment",

    # Sports (from summary.py line 406-407)
    "Cricket": "Sports",
    "Football": "Sports",
    "Olympics": "Sports",
    "Formula 1": "Sports",
    "Badminton": "Sports",
    "Tennis": "Sports",
    "Table Tennis": "Sports",
    "Hockey": "Sports",
    "MMA": "Sports",
    "Wrestling": "Sports",
    "Boxing": "Sports",
    "Other Sports": "Sports",

    # Explainers & Features (from summary.py line 409-410)
    "Explainers": "Explainers & Features",
    "Opinion": "Explainers & Features",
    "Editorials": "Explainers & Features",
    "Analysis": "Explainers & Features",
    "Interviews": "Explainers & Features",

    # Society (from summary.py line 412-413)
    "Public Safety": "Society",
    "Crime and Justice": "Society",
    "Labour": "Society",
    "Housing": "Society",
    "Arts and Culture": "Society",
    "Civil Society and Rights": "Society",
    "Caste and Religion": "Society",

    # Entertainment (from summary.py line 415-416)
    "Bollywood": "Entertainment",
    "Regional Cinema": "Entertainment",
    "Global Entertainment": "Entertainment",
    "Streaming": "Entertainment",
    "Television": "Entertainment",
    "Awards and Festivals": "Entertainment",
    "Film Policy": "Entertainment",
    "Celebrity": "Entertainment",

    # Lifestyle (from summary.py line 418-419)
    "Fashion and Beauty": "Lifestyle",
    "Food and Dining": "Lifestyle",
    "Travel": "Lifestyle",
    "Wellness": "Lifestyle",
    "Home and Living": "Lifestyle",

    # National India (from summary.py line 423-424)
    "Parliament": "National India",
    "Foreign Affairs": "National India",
    "National Policy": "National India",
    "National Governance": "National India",
    "National Judiciary": "National India",
    "National Security": "National India",
    "National Defence": "National India",
    "National Diplomacy": "National India",
    "National Schemes": "National India",
    "National Crime": "National India",
    "National Regulators": "National India",
    "National Disaster": "National India",
    "National Aviation": "National India",
    "National Infrastructure": "National India",
    "Census": "National India",

    # Global (from summary.py line 426-427)
    "Geopolitics": "Global",
    "Global Defence": "Global",
    "War": "Global",
    "Global Judiciary": "Global",
    "Global Policy": "Global",
    "Global Governance": "Global",

    # State (from summary.py line 429-430)
    "State Governance": "State",
    "State Politics": "State",
    "State Elections": "State",
    "State Policy": "State",
    "State Schemes": "State",
    "State Economy": "State",
    "State Development": "State",
    "State Crime": "State",
    "State Disaster": "State",
    "State Infrastructure": "State",
    "Local": "State",
    "City": "State",
    "Municipal": "State",
}

def _parse_subcategory_mapping_config(raw: Any) -> dict:
    if raw is None:
        return {}

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}

    parsed = {}
    if isinstance(raw, dict):
        for sub_category, parent_category in raw.items():
            if isinstance(sub_category, str) and isinstance(parent_category, str):
                sub = sub_category.strip()
                parent = parent_category.strip()
                if sub and parent:
                    parsed[sub] = parent
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            sub = item.get("sub_category") or item.get("subCategory") or item.get("name")
            parent = item.get("parent_category") or item.get("parentCategory") or item.get("parent")
            if isinstance(sub, str) and isinstance(parent, str):
                sub = sub.strip()
                parent = parent.strip()
                if sub and parent:
                    parsed[sub] = parent

    return parsed

@lru_cache(maxsize=1)
def _get_subcategory_mapping_cached(cache_bucket: int) -> frozenset:
    try:
        from ..app_db import engine, app_config
        with engine.connect() as db2:
            config_value = db2.execute(
                sa.select(app_config.c.config_value).where(
                    app_config.c.config_key == "subcategory_to_parent_mapping"
                )
            ).scalar_one_or_none()

        parsed = _parse_subcategory_mapping_config(config_value)
        if parsed:
            return frozenset(parsed.items())
    except Exception:
        pass

    return frozenset(_DEFAULT_SUB_CATEGORY_TO_PARENT.items())

def _sub_category_to_parent() -> dict:
    cache_bucket = int(time.time() // _SUBCATEGORY_MAPPING_CACHE_TTL_SECONDS)
    return dict(_get_subcategory_mapping_cached(cache_bucket))

# ---------------------------------------------------------------------------
# Sub-Category Alias Mapping (short names for LLM → display names for output)
# LLM generates simple single-word names reliably, then we alias them to full names
# ---------------------------------------------------------------------------
_SUB_CATEGORY_ALIAS_MAP: dict = {
    # Business domain aliases
    "Markets": "Stock Markets",
    "Mergers": "Mergers Acquisitions",
    # Add more aliases as needed
}

def _apply_sub_category_aliases(tag_name: str) -> str:
    """Apply alias mapping to convert short names to display names."""
    return _SUB_CATEGORY_ALIAS_MAP.get(tag_name, tag_name)

_ALWAYS_CORE_TYPES: set = {"Category", "Core Event"}
_ALWAYS_CONTEXTUAL_TYPES: set = {"Sub Category", "Associated Event", "Impact"}

# ---------------------------------------------------------------------------
# Country names — must always be tagged as Place, NEVER as Entity.
# Stored in lowercase; comparison is done with tag.name.lower().
# ---------------------------------------------------------------------------
_COUNTRY_NAMES: frozenset = frozenset({
    "afghanistan", "albania", "algeria", "andorra", "angola",
    "antigua and barbuda", "argentina", "armenia", "australia", "austria",
    "azerbaijan", "bahamas", "bahrain", "bangladesh", "barbados", "belarus",
    "belgium", "belize", "benin", "bhutan", "bolivia",
    "bosnia and herzegovina", "botswana", "brazil", "brunei", "bulgaria",
    "burkina faso", "burundi", "cabo verde", "cape verde", "cambodia",
    "cameroon", "canada", "central african republic", "chad", "chile",
    "china", "colombia", "comoros", "congo",
    "democratic republic of congo", "dr congo", "drc", "costa rica",
    "croatia", "cuba", "cyprus", "czech republic", "czechia",
    "denmark", "djibouti", "dominica", "dominican republic",
    "east timor", "timor-leste", "ecuador", "egypt", "el salvador",
    "equatorial guinea", "eritrea", "estonia", "eswatini", "swaziland",
    "ethiopia", "fiji", "finland", "france", "gabon", "gambia",
    "georgia", "germany", "ghana", "greece", "grenada", "guatemala",
    "guinea", "guinea-bissau", "guyana", "haiti", "honduras", "hungary",
    "iceland", "india", "indonesia", "iran", "iraq", "ireland", "israel",
    "italy", "jamaica", "japan", "jordan", "kazakhstan", "kenya",
    "kiribati", "north korea", "south korea", "kosovo", "kuwait",
    "kyrgyzstan", "laos", "latvia", "lebanon", "lesotho", "liberia",
    "libya", "liechtenstein", "lithuania", "luxembourg", "madagascar",
    "malawi", "malaysia", "maldives", "mali", "malta", "marshall islands",
    "mauritania", "mauritius", "mexico", "micronesia", "moldova", "monaco",
    "mongolia", "montenegro", "morocco", "mozambique", "myanmar", "burma",
    "namibia", "nauru", "nepal", "netherlands", "new zealand", "nicaragua",
    "niger", "nigeria", "north macedonia", "norway", "oman", "pakistan",
    "palau", "palestine", "panama", "papua new guinea", "paraguay", "peru",
    "philippines", "poland", "portugal", "qatar", "romania", "russia",
    "rwanda", "saint kitts and nevis", "saint lucia",
    "saint vincent and the grenadines", "samoa", "san marino",
    "sao tome and principe", "saudi arabia", "senegal", "serbia",
    "seychelles", "sierra leone", "singapore", "slovakia", "slovenia",
    "solomon islands", "somalia", "south africa", "south sudan", "spain",
    "sri lanka", "sudan", "suriname", "sweden", "switzerland", "syria",
    "taiwan", "tajikistan", "tanzania", "thailand", "togo", "tonga",
    "trinidad and tobago", "tunisia", "turkey", "turkiye", "turkmenistan",
    "tuvalu", "uganda", "ukraine", "united arab emirates", "uae",
    "united kingdom", "uk", "britain", "great britain",
    "united states", "united states of america", "usa", "america",
    "uruguay", "uzbekistan", "vanuatu", "vatican", "venezuela", "vietnam",
    "yemen", "zambia", "zimbabwe",
})

# ---------------------------------------------------------------------------

class WeightedCategory(BaseModel):
    name: str = Field(..., description="Category Name")
    weight: int = Field(..., ge=0, le=100, description="Category relevance weight between 0 and 100")
    model_config = ConfigDict(extra="forbid")

class WeightedTagNew(BaseModel):
    """New WeightedTag with all required fields for new prompt structure."""
    name: str = Field(..., description="Tag name (1-2 words)")
    type: Literal['Category', 'Sub Category', 'Core Event', 'Associated Event', 'Entity', 'Place', 'Impact'] = Field(..., description="Tag type")
    relevance_type: Literal['Core', 'Contextual'] = Field(
        ...,
        description=(
            "Relevance type. ALWAYS 'Core': Category, Core Event. "
            "ALWAYS 'Contextual': Sub Category, Associated Event, Impact. "
            "Entity and Place: 'Core' if central to story, else 'Contextual'."
        )
    )
    linked_to_tag: Optional[str] = Field(
        None,
        description=(
            "Exact name of the Core tag this links to. "
            "ALWAYS null: Category, Core Event, and Core Entity/Place. "
            "Sub Category → exact parent Category name. "
            "Associated Event, Impact, Contextual Entity, Contextual Place → exact Core Event name."
        )
    )
    weight: int = Field(..., ge=0, le=100, description="Relevance weight 0-100")
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode='after')
    def enforce_wiring_relevance(self) -> 'WeightedTagNew':
        if self.type in _ALWAYS_CORE_TYPES:
            self.relevance_type = "Core"
        elif self.type in _ALWAYS_CONTEXTUAL_TYPES:
            self.relevance_type = "Contextual"
        # Entity and Place: keep LLM output
        return self

class Facts(BaseModel):
    claim: str = Field(..., description="Information which is claimed. ")
    sources: str = Field(..., description="In number of sources it is claimed/Total Numner of Sources")
    confidence: float = Field(...,
                              description="Confidence of the claim. This is based on Number of sources and reasoning.")
    reason_for_confidence: str = Field(..., description="Reason for the confidence reason")
    model_config = ConfigDict(extra="forbid")

class Quote(BaseModel):
    quote: str = Field(..., description="Quote provided by the speaker.")
    speaker: str = Field(..., description="Speaker of the quote")
    source: str = Field(..., description="Source of the quote")
    model_config = ConfigDict(extra="forbid")


class Source(BaseModel):
    source_id: str = Field(..., description="Unique ID of the source")
    url: str = Field(..., description="source url link")
    title: str = Field(..., description="Title of the Source")
    model_config = ConfigDict(extra="forbid")


class Metadata(BaseModel):
    sources_used: List[str] = Field(...,
                                    description="List of source ids used to generate the information. Same ids present in the sources section.")
    sources_excluded: List[str] = Field(...,
                                        description="List of source ids excluded while generating the information. Same ids present in the sources section.")
    last_updated_article: str = Field(..., description="Last Updated Article DateTime in YYYY-MM-DD HH:MM:SS")
    confidence_score: float = Field(..., description="Confidence in generation of the article.")
    model_config = ConfigDict(extra="forbid")


class ClassificationOutputNew(BaseModel):
    """New ClassificationOutput for new prompt structure - only categories."""
    categories: List[WeightedCategory] = Field(
        ...,
        description="All relevant categories with weights, sorted by importance."
    )
    model_config = ConfigDict(extra="forbid")


class FAQItem(BaseModel):
    question: str = Field(..., description="Frequently asked question for this article.")
    answer: str = Field(..., description="2-3 sentence answer to the FAQ, grounded in the article.")
    model_config = ConfigDict(extra="forbid")

class AudioScripts(BaseModel):
    """Audio scripts for summary in both languages."""
    en: str = Field(..., description="English audio script (40-60 words)")
    hi: str = Field(..., description="Hindi audio script (40-60 words)")
    model_config = ConfigDict(extra="forbid")


class StorySoFarTitle(BaseModel):
    en: str = Field(..., description="Story So Far title in English")
    hi: str = Field(..., description="Story So Far title in Hindi")
    model_config = ConfigDict(extra="forbid")


class StorySoFarTimelineEntry(BaseModel):
    date: str = Field(..., description="Timeline entry date (YYYY-MM or YYYY-MM-DD)")
    event: str = Field(..., description="Timeline event summary in English")
    event_hi: str = Field(..., description="Timeline event summary in Hindi")
    source_id: List[str] = Field(..., description="Source identifiers for the event")
    model_config = ConfigDict(extra="forbid")


class StorySoFarTimeline(BaseModel):
    title: StorySoFarTitle = Field(..., description="Title block")
    type: Literal["timeline"] = Field(..., description="timeline")
    entries: List[StorySoFarTimelineEntry] = Field(..., description="Chronological events (min 2)")

    @validator("entries")
    def _min_entries(cls, v):
        if len(v) < 2:
            raise ValueError("timeline requires at least 2 entries")
        return v
    model_config = ConfigDict(extra="forbid")


class StorySoFarConcept(BaseModel):
    concept_en: str = Field(..., description="Key concept or term in English")
    concept_hi: str = Field(..., description="Key concept or term in Hindi (Devanagari script)")
    explanation_en: str = Field(..., description="Concept explanation in English")
    explanation_hi: str = Field(..., description="Concept explanation in Hindi")
    model_config = ConfigDict(extra="forbid")


class StorySoFarConceptsDecoded(BaseModel):
    title: StorySoFarTitle = Field(..., description="Title block")
    type: Literal["concepts_decoded"] = Field(..., description="concepts_decoded")
    concepts: List[StorySoFarConcept] = Field(..., description="List of concepts (min 2)")

    @validator("concepts")
    def _min_concepts(cls, v):
        if len(v) < 2:
            raise ValueError("concepts_decoded requires at least 2 concepts")
        return v
    model_config = ConfigDict(extra="forbid")


class StorySoFarSkipped(BaseModel):
    type: Literal["skipped"] = Field(..., description="Skipped output flag")
    reason: str = Field(..., description="Reason for skipping")
    model_config = ConfigDict(extra="forbid")


class StorySoFarSource(BaseModel):
    url: str = Field(..., description="Source URL")
    title: Optional[str] = Field(None, description="Source title")
    date: Optional[str] = Field(None, description="Article publish date")
    logo: Optional[str] = Field(None, description="Logo URL if provided")
    model_config = ConfigDict(extra="forbid")


class MultiLanguageStorySoFar(BaseModel):
    """Story So Far output (timeline/concepts/skip) with audio scripts."""
    story_so_far: Union[StorySoFarTimeline, StorySoFarConceptsDecoded, StorySoFarSkipped] = Field(
        ..., description="Story So Far content block"
    )
    audio_script: Optional[AudioScripts] = Field(
        None, description="Audio script in English and Hindi (required unless skipped)"
    )
    sources: Optional[List[StorySoFarSource]] = Field(
        None, description="Optional sources list passed through from prompt context"
    )

    # Pydantic v2 requires skip_on_failure=True for post root validators.
    @root_validator(skip_on_failure=True)
    def _audio_required_unless_skipped(cls, values):
        ssf = values.get("story_so_far")
        audio = values.get("audio_script")
        if isinstance(ssf, StorySoFarSkipped):
            return values
        if not audio:
            raise ValueError("audio_script is required for timeline or concepts_decoded")
        return values
    model_config = ConfigDict(extra="forbid")


class MultiLanguageSummaryNew(BaseModel):
    """New MultiLanguageSummary with flat structure - all fields at top level."""
    title_en: str = Field(..., description="Title in English (10-12 words)")
    title_hi: str = Field(..., description="Title in Hindi (10-12 words)")
    summary_en: str = Field(..., description="Summary in English (70-80 words, single paragraph)")
    summary_hi: str = Field(..., description="Summary in Hindi (70-80 words, single paragraph)")
    latest_angle: Optional[str] = Field(None, description="Cluster-specific angle (max 6 words, noun phrase only). Describes what makes THIS cluster distinct from other clusters covering the same ongoing story. Used to differentiate titles when multiple clusters share the same Core Event tag. Examples: 'Merger agreement details announced', 'Plant expansion in India', 'Record fundraising amount achieved'")
    last_updated_at: Optional[str] = Field(None, description="Last updated/published timestamp (ISO8601)")
    classification: ClassificationOutputNew = Field(..., description="Classification with categories")
    tags: List[WeightedTagNew] = Field(..., description="List of tags with weights (8-12 tags)")
    faqs_en: List[FAQItem] = Field(..., description="FAQs in English (5 items)")
    faqs_hi: List[FAQItem] = Field(..., description="FAQs in Hindi (5 items)")
    audio_scripts_summary: AudioScripts = Field(..., description="Audio scripts for summary")
    google_news_queries: List[str] = Field(..., description="Google News queries (8-10 plain text queries)")
    sources: List[Source] = Field(..., description="List of Sources")

    @model_validator(mode='after')
    def enforce_tag_wiring(self) -> 'MultiLanguageSummaryNew':
        tags = self.tags or []

        # --- Job A: Strip invalid Category / Sub Category names ---
        approved_categories = _approved_categories()
        sub_category_to_parent = _sub_category_to_parent()
        approved_sub_categories = set(sub_category_to_parent.keys())
        tags = [
            t for t in tags
            if not (t.type == "Category" and t.name not in approved_categories)
            and not (t.type == "Sub Category" and t.name not in approved_sub_categories)
        ]

        # --- Job C: Country names must always be Place, never Entity ---
        for tag in tags:
            if tag.type == "Entity" and tag.name.lower() in _COUNTRY_NAMES:
                tag.type = "Place"

        # --- Job D: Approved category names must always be Category type ---
        approved_categories_lower = {c.lower() for c in approved_categories}
        for tag in tags:
            if tag.type != "Category" and tag.name.lower() in approved_categories_lower:
                tag.type = "Category"

        # --- Job B: Enforce linked_to_tag per wiring table ---
        category_names = {t.name for t in tags if t.type == "Category"}
        core_event_names = {t.name for t in tags if t.type == "Core Event"}
        first_category = next((t.name for t in tags if t.type == "Category"), None)
        first_core_event = next((t.name for t in tags if t.type == "Core Event"), None)

        for tag in tags:
            tt = tag.type

            if tt in ("Category", "Core Event"):
                tag.linked_to_tag = None

            elif tt == "Sub Category":
                correct_parent = sub_category_to_parent.get(tag.name)
                if correct_parent and correct_parent in category_names:
                    tag.linked_to_tag = correct_parent
                elif tag.linked_to_tag not in category_names:
                    tag.linked_to_tag = first_category  # last resort

            elif tt in ("Associated Event", "Impact"):
                if tag.linked_to_tag not in core_event_names:
                    tag.linked_to_tag = first_core_event

            elif tt in ("Entity", "Place"):
                if tag.relevance_type == "Core":
                    tag.linked_to_tag = None
                elif tag.relevance_type == "Contextual":
                    if tag.linked_to_tag not in core_event_names:
                        tag.linked_to_tag = first_core_event

        # --- Job E: MANDATORY SUB-CATEGORY VALIDATION (DOMAIN CATEGORIES ONLY) ---
        # This enforces the critical rule from the prompt:
        # "If ANY Domain Category lacks a Sub Category → STOP. Do NOT output."
        # Note: Geography sub-categories are OPTIONAL, so we only check Domain categories

        approved_domain_categories = _approved_categories()
        geography_categories = {"National India", "Global", "State", "Regional"}

        # Get all category tags and filter to ONLY domain categories (not geography)
        all_categories = [t.name for t in tags if t.type == "Category"]
        domain_cats_only = [c for c in all_categories if c in approved_domain_categories and c not in geography_categories]

        sub_categories = [t for t in tags if t.type == "Sub Category"]

        # --- Job E1: MANDATORY SUB-CATEGORY VALIDATION (PRIMARY DOMAIN CATEGORIES ONLY) ---
        # Enforce rule: PRIMARY Domain categories (weight=95) MUST have sub-categories
        # SECONDARY Domain categories (weight<95) are optional for sub-categories

        domain_cats_primary = [
            t for t in tags
            if t.type == "Category" and t.name in domain_cats_only and t.weight == 95
        ]

        for domain_cat_obj in domain_cats_primary:
            has_linked_sub = any(
                s.linked_to_tag == domain_cat_obj.name
                for s in sub_categories
            )
            if not has_linked_sub:
                raise ValueError(
                    f"INVALID OUTPUT: PRIMARY Domain Category '{domain_cat_obj.name}' (weight=95) has no linked Sub-Category. "
                    f"Per prompt rules, every PRIMARY Domain Category (weight=95) MUST have a Sub-Category. "
                    f"This is a mandatory requirement and output cannot proceed without it."
                )

        # --- Job E2: MANDATORY SUB-CATEGORY VALIDATION (PRIMARY GEOGRAPHY CATEGORIES) ---
        # Enforce rule from prompt: PRIMARY Geography categories (weight=95) MUST have sub-categories
        # SECONDARY Geography categories (weight<95) are optional

        geography_cats_primary = [
            t for t in tags
            if t.type == "Category" and t.name in geography_categories and t.weight == 95
        ]

        for geo_cat in geography_cats_primary:
            has_linked_sub = any(
                s.linked_to_tag == geo_cat.name and s.weight is not None
                for s in sub_categories
            )
            if not has_linked_sub:
                raise ValueError(
                    f"INVALID OUTPUT: PRIMARY Geography Category '{geo_cat.name}' (weight=95) has no linked Sub-Category. "
                    f"Per prompt rules, every PRIMARY Geography Category (weight=95) MUST have a Sub-Category. "
                    f"For Global: use Geopolitics, War, Global Defence, etc. "
                    f"This is a mandatory requirement and output cannot proceed without it."
                )

        # --- Job F: Apply Sub-Category Aliases (short names → display names) ---
        # Transform short names (e.g., "Markets") to display names (e.g., "Stock Markets")
        for tag in tags:
            if tag.type == "Sub Category":
                tag.name = _apply_sub_category_aliases(tag.name)

        self.tags = tags
        return self


def apply_tag_wiring(tags: List[dict]) -> List[dict]:
    """Enforce tag wiring table rules on a list of raw tag dicts.

    This is the authoritative enforcement layer. It runs on plain dicts after
    model_dump() so it is completely independent of Pydantic/LangChain internals.
    """
    if not tags:
        return tags

    # --- Job A: Strip invalid Category / Sub Category names ---
    approved_categories = _approved_categories()
    sub_category_to_parent = _sub_category_to_parent()
    approved_sub_categories = set(sub_category_to_parent.keys())
    tags = [
        t for t in tags
        if not (t.get("type") == "Category" and t.get("name") not in approved_categories)
        and not (t.get("type") == "Sub Category" and t.get("name") not in approved_sub_categories)
    ]

    # --- Job C: Country names must always be Place, never Entity ---
    for tag in tags:
        if tag.get("type") == "Entity" and tag.get("name", "").lower() in _COUNTRY_NAMES:
            tag["type"] = "Place"

    # --- Job D: Approved category names must always be Category type ---
    approved_categories_lower = {c.lower() for c in approved_categories}
    for tag in tags:
        if tag.get("type") != "Category" and tag.get("name", "").lower() in approved_categories_lower:
            tag["type"] = "Category"

    # --- Fix relevance_type for ALWAYS rows ---
    for tag in tags:
        tt = tag.get("type")
        if tt in _ALWAYS_CORE_TYPES:
            tag["relevance_type"] = "Core"
        elif tt in _ALWAYS_CONTEXTUAL_TYPES:
            tag["relevance_type"] = "Contextual"

    # --- Job B: Enforce linked_to_tag per wiring table ---
    category_names = {t["name"] for t in tags if t.get("type") == "Category"}
    core_event_names = {t["name"] for t in tags if t.get("type") == "Core Event"}
    first_category = next((t["name"] for t in tags if t.get("type") == "Category"), None)
    first_core_event = next((t["name"] for t in tags if t.get("type") == "Core Event"), None)

    for tag in tags:
        tt = tag.get("type")

        if tt in ("Category", "Core Event"):
            tag["linked_to_tag"] = None

        elif tt == "Sub Category":
            correct_parent = sub_category_to_parent.get(tag.get("name", ""))
            if correct_parent and correct_parent in category_names:
                tag["linked_to_tag"] = correct_parent
            elif tag.get("linked_to_tag") not in category_names:
                tag["linked_to_tag"] = first_category  # last resort

        elif tt in ("Associated Event", "Impact"):
            if tag.get("linked_to_tag") not in core_event_names:
                tag["linked_to_tag"] = first_core_event

        elif tt in ("Entity", "Place"):
            if tag.get("relevance_type") == "Core":
                tag["linked_to_tag"] = None
            elif tag.get("relevance_type") == "Contextual":
                if tag.get("linked_to_tag") not in core_event_names:
                    tag["linked_to_tag"] = first_core_event

    # --- Apply Sub-Category Aliases (short names → display names) ---
    # Transform short names (e.g., "Markets") to display names (e.g., "Stock Markets")
    for tag in tags:
        if tag.get("type") == "Sub Category":
            tag["name"] = _apply_sub_category_aliases(tag.get("name", ""))

    return tags


class TagsOutput(BaseModel):
    """SEO-style tags output."""
    seo_tags: List[str] = Field(..., description="List of SEO-style tags with hashtags (2-4 words each). Format: #tag1, #tag2, etc.")


class FilterOutput(BaseModel):
    """Editorial filter output from prompt0.txt."""
    status: Literal["YES", "NO"] = Field(..., description="Filter decision: YES to approve, NO to reject")


class Content(BaseModel):
    heading: str = Field(..., description="Heading or title for the content text")
    text: List[str] = Field(..., description="Content Text only. Source Ids shouldn't be here.")
    source_id: List[str] = Field(..., description="List of Source Id of the content text if applicable. ")


class Slide(BaseModel):
    success: bool = Field(..., description="Success in creating slide")
    failure_reason: str = Field(..., description="Failure reason for creating the slide")
    heading: Optional[str] = Field(..., description="Heading of the slide")
    content: Optional[List[Content]] = Field(..., description="List of bullet points for the story.")


class Source(BaseModel):
    source_id: str = Field(..., description="Unique numeric IDs of the source")
    url: str = Field(..., description="source url link")
    title: str = Field(..., description="Title of the Source")
    date: str = Field(description="Date of the article")


class Metadata(BaseModel):
    sources_used: List[str] = Field(..., description="List of source ids used to generate the information.")
    sources_excluded: List[str] = Field(...,
                                        description="List of source ids excluded while generating the information.")
    last_updated_article: str = Field(..., description="Last Updated Article DateTime in YYYY-MM-DD HH:MM:SS")
    confidence_score: float = Field(..., description="Confidence in generation of the article.")


class StakeHolderContent(BaseModel):
    heading: str = Field(..., description="Stakeholder Name")
    text: str = Field(..., description="Content Text")
    source_id: List[str] = Field(..., description="List of Source Id of the content text if applicable. ")
    impact: str = Field(..., description="Stakeholder Impact: either Positive, Negative or Neutral")


class StakeHolderSlide(BaseModel):
    success: bool = Field(..., description="Success in creating slide")
    failure_reason: str = Field(..., description="Failure reason for creating the slide")
    heading: Optional[str] = Field(..., description="Heading of the slide")
    content: Optional[List[StakeHolderContent]] = Field(..., description="List of bullet points for the story.")


class QA(BaseModel):
    question: str = Field(..., description="Question")
    answer: str = Field(..., description="Answer")
    model_config = ConfigDict(extra="forbid")


class FAQs(BaseModel):
    """FAQs structure with explicit English and Hindi fields."""
    faqs_en: List[QA] = Field(..., description="FAQs in English (exactly 3)")
    faqs_hi: List[QA] = Field(..., description="FAQs in Hindi (exactly 3)")
    model_config = ConfigDict(extra="forbid")


class StakeHolderViewContent(BaseModel):
    heading: str = Field(..., description="Stakeholder Name")
    text: str = Field(..., description="Content Text")
    source_id: List[str] = Field(..., description="List of Source Id of the content text if applicable. ")
    stance: str = Field(..., description="Stakeholder Stance: either Aganist, Neutral or In Favour")


class StakeholderViewSlide(BaseModel):
    success: bool = Field(..., description="Success in creating slide")
    failure_reason: str = Field(..., description="Failure reason for creating the slide")
    heading: Optional[str] = Field(..., description="Heading of the slide")
    content: Optional[List[StakeHolderViewContent]] = Field(..., description="List of bullet points for the story.")


class TimelineViewContent(BaseModel):
    date: str = Field(..., description="Timeline date")
    text: str = Field(..., description="Content Text")
    source_id: List[str] = Field(..., description="List of Source Id of the content text if applicable. ")


class TimelineViewSlide(BaseModel):
    success: bool = Field(..., description="Success in creating slide")
    failure_reason: str = Field(..., description="Failure reason for creating the slide")
    heading: Optional[str] = Field(..., description="Heading of the slide")
    content: Optional[List[TimelineViewContent]] = Field(..., description="List of Timeline view details for the story.")


class TrendlineViewContent(BaseModel):
    date: str = Field(..., description="Timeline date")
    text: str = Field(..., description="Content Text")
    metric_data: str = Field(..., description="Metric Data Text")
    source_id: List[str] = Field(..., description="List of Source Id of the content text if applicable. ")


class TrendlineViewSlide(BaseModel):
    success: bool = Field(..., description="Success in creating slide")
    failure_reason: str = Field(..., description="Failure reason for creating the slide")
    heading: Optional[str] = Field(..., description="Heading of the slide")
    content: Optional[List[TrendlineViewContent]] = Field(..., description="List of bullet points for the story.")


class ScenarioContent(BaseModel):
    scenario: str = Field(..., description="Scenario Name")
    description: str = Field(..., description="Description Text")
    source_id: List[str] = Field(..., description="List of Source Id of the content text if applicable. ")
    probability: int = Field(..., description="Probability in Int. Ex: 10,20,30,40 etc..")
    implications: str = Field(..., description="Implications")


class ScenarioSlide(BaseModel):
    success: bool = Field(..., description="Success in creating slide")
    failure_reason: str = Field(..., description="Failure reason for creating the slide")
    heading: Optional[str] = Field(..., description="Heading of the slide")
    content: Optional[List[ScenarioContent]] = Field(..., description="List of bullet points for the story.")


# Helper classes for new looking_ahead.py prompt structure
class StakeholderImpactEntry(BaseModel):
    """Stakeholder impact entry with flat bilingual fields."""
    stakeholder_name_en: str = Field(..., description="Stakeholder name in English (MAX 2 words)")
    stakeholder_name_hi: str = Field(..., description="Stakeholder name in Hindi, Devanagari script (MAX 2 words)")
    stakeholder_impact_en: str = Field(..., description="Impact summary in English (Max 120 chars)")
    stakeholder_impact_hi: str = Field(..., description="Impact summary in Hindi (Max 140 chars)")
    stakeholder_sentiment: Literal["hopeful", "worried", "supportive", "opposed", "neutral", "uncertain"] = Field(..., description="Sentiment (language-neutral key - same for all languages)")
    model_config = ConfigDict(extra="forbid")


class StakeholderImpactSlide(BaseModel):
    """Stakeholder impact slide with entries."""
    entries: List[StakeholderImpactEntry] = Field(..., description="List of stakeholder impact entries (3-4 entries)")
    model_config = ConfigDict(extra="forbid")


class ScenarioEntry(BaseModel):
    """Scenario entry with flat bilingual fields."""
    time_horizon: Literal["Short Term", "Long Term"] = Field(..., description="Time horizon for the scenario")
    scenario_en: List[str] = Field(..., description="Scenario description points in English (2-3 points, each Max 140 chars)")
    scenario_hi: List[str] = Field(..., description="Scenario description points in Hindi (2-3 points, each Max 160 chars)")
    scenario_type: Literal["positive", "negative", "neutral"] = Field(..., description="Scenario type")
    probability_pct: int = Field(..., ge=0, le=100, description="Probability percentage (0-100)")
    model_config = ConfigDict(extra="forbid")


class ScenariosSection(BaseModel):
    """Scenarios section with entries."""
    entries: List[ScenarioEntry] = Field(..., description="List of scenario entries (exactly 2)")
    model_config = ConfigDict(extra="forbid")


class HindiAudioScript(BaseModel):
    """Audio script with bilingual fields."""
    audio_en: str = Field(..., description="Audio script in English (40-60 words)")
    audio_hi: str = Field(..., description="Audio script in Hindi (40-60 words)")
    model_config = ConfigDict(extra="forbid")


class LookingAhead(BaseModel):
    """Looking ahead structure matching new looking_ahead.py JSON format."""
    stakeholder_impact_slide: StakeholderImpactSlide = Field(..., description="Stakeholder Impact Slide")
    scenarios: ScenariosSection = Field(..., description="Scenarios Section")
    faqs: FAQs = Field(..., description="FAQs with 'faqs_en' and 'faqs_hi' keys")
    audio_script: HindiAudioScript = Field(..., description="Audio script in both languages") #need to check later if HindiAudioScript can be renamed to AudioScripts safely.
    model_config = ConfigDict(extra="forbid")


class MultiLanguageLookingAhead(BaseModel):
    """Multi-language looking ahead output matching new looking_ahead.py structure."""
    stakeholder_impact_slide: StakeholderImpactSlide = Field(..., description="Stakeholder Impact Slide")
    scenarios: ScenariosSection = Field(..., description="Scenarios Section")
    faqs: FAQs = Field(..., description="FAQs with 'faqs_en' and 'faqs_hi' keys")
    audio_script: HindiAudioScript = Field(..., description="Audio script in both languages")
    sources: List[Source] = Field(..., description="List of Sources provided to creating the section.")
    model_config = ConfigDict(extra="forbid")


class MultiLanguageAudioText(BaseModel):
    english_lang: str = Field(description="English Language Audio Text Output")
    hindi_lang: str = Field(description="Hindi Language Audio Text Output")


class MultiLanguageFullStoryAudio(BaseModel):
    audio_scripts_full_story: AudioScripts = Field(..., description="Full story audio scripts in English and Hindi")


def _bullets(sections: List[Dict[str, Any]], heading: Optional[str] = None) -> List[str]:
    """Flatten nested bullet sections into a simple list of strings."""
    out: List[str] = []
    for sec in sections or []:
        if sec.get("heading"):
            out.append(sec["heading"])
        for bullet in sec.get("text") or []:
            out.append(bullet)
    return out

def _slide_type(sections: List[Dict[str, Any]], heading: Optional[str] = None):
    return [{"title": sec.get('heading') or '', "contentType": "bullets", "content": sec.get("text") or []} for sec in sections]


def _timeline(rows: List[Dict[str, Any]], heading: Optional[str] = None) -> List[Dict[str, Any]]:
    return [{"date": r.get("date"), "content": r.get("text")} for r in rows or []]


def _trend_table(rows: List[Dict[str, Any]], heading: Optional[str] = None) -> List[Dict[str, Any]]:
    data = {r['date']: f"{r.get('text')} {r.get('metric_data')}" for r in (rows or [])}
    return [{"title": heading or "Trendline", "data": data}]


def _concepts_decoded(rows: List[Dict[str, Any]], heading: Optional[str] = None) -> List[Dict[str, Any]]:
    return [
        {
            "title": r.get("heading") or r.get("concept") or "",
            "contentType": "bullets",
            "content": r.get("text") or [],
        }
        for r in rows or []
    ]


def _stakeholder_view(rows: List[Dict[str, Any]], heading: Optional[str] = None) -> List[Dict[str, Any]]:
    def stance_to_impact(stance: Optional[str]) -> str:
        s = (stance or "").lower()
        if s in ("in_favour", "in favor", "in favour", "support", "pro"):
            return "positive"
        if s in ("against", "oppose", "con"):
            return "negative"
        return "neutral"

    return [
        {
            "title": r.get("heading"),
            "description": r.get("text"),
            "impact": stance_to_impact(r.get("stance")),
        }
        for r in rows or []
    ]


def _stakeholder_impact(rows: List[Dict[str, Any]], heading: Optional[str] = None) -> List[Dict[str, Any]]:
    return [
        {
            "title": r.get("heading"),
            "description": r.get("text"),
            "impact": (r.get("impact") or "neutral"),
            "sentiment": r.get("sentiment"),  # Preserve original sentiment if available
        }
        for r in rows or []
    ]


def _scenarios(rows: List[Dict[str, Any]], heading: Optional[str] = None) -> List[Dict[str, Any]]:
    return [
        {
            "scenario": r.get("scenario"),
            "implications": r.get("implications") or r.get("text"),
            "probability": r.get("probability"),
            "description": r.get("description"),
            "timeframe": r.get("timeframe"),  # Preserve timeframe field for proper short_term/long_term separation
            "sentiment": r.get("sentiment")  # Preserve sentiment field
        }
        for r in rows or []
    ]


def transform_slide_content(slide_type: str, content: List[Dict[str, Any]], heading: Optional[str]) -> tuple:
    """Convert raw slide content to the structure expected by DB2.

    Returns a tuple of (content_type, transformed_content).
    """
    if slide_type == "explainer":
        return "bullets", _slide_type(content, heading)
    if slide_type == "timeline":
        return "timeline", _timeline(content, heading)
    if slide_type == "trendline":
        return "table", _trend_table(content, heading)
    if slide_type == "stakeholder_view":
        return "stakeholder_impact", _stakeholder_view(content, heading)
    if slide_type == "stakeholder_impact":
        return "stakeholder_impact", _stakeholder_impact(content, heading)
    if slide_type == "forecast":
        return "bullets", _slide_type(content, heading)
    if slide_type == "scenarios":
        return "scenario", _scenarios(content, heading)
    if slide_type == "concepts_decoded":
        return "concepts_decoded", _concepts_decoded(content, heading)
    return "text", content
