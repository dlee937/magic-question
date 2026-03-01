# Magic Garden RAG Bot — Architecture v3
## Rebuilt Against Game Source Code (Feb 2026 Client Build)

> **Data provenance:** All entity counts, stats, formulas, and relationships in this
> document are extracted directly from the game's client-side JavaScript source code.
> This supersedes all wiki-derived data from v1/v2. Where wiki display names differ
> from source internal IDs, both are noted.

---

## 1. Entity Inventory (Source of Truth)

| Entity Type | Count | Source | Change from v2 |
|-------------|-------|--------|----------------|
| Pets | 21 | `Ie` object | — |
| Crops | 44 | `z0` object | — |
| Abilities | **67** | `_s` object | was 29 (wiki only showed base tiers) |
| Mutations | 10 | `bs` object | — |
| Weather Events | 5 | `s7` object | was 6 (Sunny is not a code-level event) |
| Plant Abilities | 2 | `ir` object | NEW (Dawnbinder/Moonbinder crop abilities) |
| Eggs | **8** | `Jt` object | was 7 (Snow Egg + Winter Egg are separate) |
| Tools | **11** | `oi` object | was 15 (wiki counted differently) |
| Decor | **43** | `Ti` object | NEW category (39 cosmetic + 4 functional) |
| Rarity Tiers | **7** | `T0` enum | was 5 (adds Divine, Celestial) |

**Total unique entities: ~218** (was ~138)
**Estimated total chunks (all layers): ~500–650**

---

## 2. Rarity Tier System (7 tiers)

The source code defines 7 rarity tiers, not the 5 visible on the wiki. This affects crop classification, egg naming, and the entity registry.

| # | Tier | Enum Value | Used By |
|---|------|-----------|---------|
| 1 | Common | `T0.Common` | 5 crops, 3 pets, basic tools, 16 decor |
| 2 | Uncommon | `T0.Uncommon` | 7 crops, 3 pets, Shovel/Dawnlit Potion, 7 decor |
| 3 | Rare | `T0.Rare` | 7 crops, 3 pets, Frozen/Amberlit Potion, 11 decor |
| 4 | Legendary | `T0.Legendary` | 8 crops, 9 pets (incl. Snow/Horse tiers), Gold Potion, 4 decor |
| 5 | Mythical | `T0.Mythic` | 7 crops, 4 pets (FireHorse, Butterfly, Peacock, Capybara), 2 decor |
| 6 | Divine | `T0.Divine` | 7 crops (Pepper→Sunflower), 3 functional decor |
| 7 | Celestial | `T0.Celestial` | 3 crops (Starweaver, Dawnbinder, Moonbinder), Rainbow Potion |

**RAG implication:** Queries like "what are the divine crops" or "celestial seeds" need to resolve against this tier system. The entity registry must map rarity terms to the correct tier.

---

## 3. Internal vs Display Name Mapping

The source code uses internal IDs that differ from what players see. This is **critical** for the entity registry — a player will type "Amberbound" but the source stores it as "Ambercharged".

| Internal ID | Display Name | Type | Context |
|------------|-------------|------|---------|
| `Ambershine` | Amberlit | Mutation | Used in mutation code, potion code, granter abilities |
| `Ambercharged` | Amberbound | Mutation | Upgrade from Amberlit via Moonbinder |
| `Dawncharged` | Dawnbound | Mutation | Upgrade from Dawnlit via Dawnbinder |
| `OrangeTulip` | Tulip | Crop | Seed name, diet references |
| `WhiteCaribou` | Caribou | Pet | Hatches from Snow/Winter Egg |
| `DawnCelestial` | Dawnbinder | Crop | Celestial crop with plant ability |
| `MoonCelestial` | Moonbinder | Crop | Celestial crop with plant ability |
| `MoonKisser` | Amberbinder | Plant Ability | Moonbinder's passive effect (name swap!) |
| `DawnKisser` | Dawnbinder | Plant Ability | Dawnbinder's passive effect |
| `Frost` | Snow | Weather Event | Internal event ID vs display name |
| `FireHorse` | Fire Horse | Pet | Two words in display |
| `SnowFox` | Snow Fox | Pet | Two words in display |
| `BurrosTail` | Burro's Tail | Crop | Apostrophe in display |
| `FavaBean` | Fava Bean | Crop | Two words in display |
| `DragonFruit` | Dragon Fruit | Crop | Two words in display |
| `PassionFruit` | Passion Fruit | Crop | Two words in display |
| `VioletCort` | Violet Cort | Crop | Two words in display |
| `PineTree` | Pine Tree | Crop | Two words in display |
| `ProduceEater` | Crop Eater | Ability | Completely different name |
| `ProduceMutationBoost` | Weather Mutation Boost I | Ability | "Produce" → "Weather" rename |
| `ProduceScaleBoost` | Crop Size Boost I | Ability | "Produce" → "Crop" rename |
| `ProduceRefund` | Crop Refund | Ability | "Produce" → "Crop" rename |
| `RainDance` | Rain Granter | Ability | Completely different name |
| `EggGrowthBoostII` | Egg Growth Boost **III** | Ability | Legacy ID mismatch (II_NEW = II, II = III) |

**RAG implication:** The entity registry must store both internal and display forms, and the query analyser must normalise user input against display names. Chunk text should use display names exclusively. Internal IDs are only needed for the data pipeline.

---

## 4. Complete Relationship Graph

```
RARITY TIERS (7): Common → Uncommon → Rare → Legendary → Mythical → Divine → Celestial

EGGS (8)
├── CommonEgg (100K coins) → Worm 60%, Snail 35%, Bee 5%
├── UncommonEgg (1M) → Chicken 65%, Bunny 25%, Dragonfly 10%
├── RareEgg (10M) → Pig 80%, Cow 15%, Turkey 5%
├── LegendaryEgg (100M) → Squirrel 60%, Turtle 30%, Goat 10%
├── SnowEgg (200M, requires Snow weather) → Snow Fox 75%, Stoat 20%, Caribou 5%
├── WinterEgg (80M, seasonal) → Snow Fox 75%, Stoat 20%, Caribou 5%
├── HorseEgg (200M) → Pony 60%, Horse 35%, Fire Horse 5%
└── MythicalEgg (1B) → Butterfly 75%, Peacock 20%, Capybara 5%

PETS (21) → each has: diet (3-5 crops), weighted ability pool, hunger cost, maturity time
├── Common (3):  Worm, Snail, Bee           — 12h maturity
├── Uncommon (3): Chicken, Bunny, Dragonfly  — 24h maturity
├── Rare (3):    Pig, Cow, Turkey            — 72h maturity
├── Legendary (9): Squirrel, Turtle, Goat    — 100h maturity
│   ├── Snow pets: Snow Fox, Stoat, Caribou  — 100h maturity
│   └── Horse pets: Pony (72h), Horse (100h)
├── Mythical (4): Fire Horse (144h), Butterfly (144h), Peacock (144h), Capybara (144h)

CROPS (44) → each has: seed price, sell price, base weight, max scale, harvest type
├── Common (5):     Carrot → Beet              [10 → 210 coins]
├── Uncommon (7):   Rose → Tomato              [229 → 800 coins]
├── Rare (7):       Daffodil → Gentian         [1K → 9K coins]
├── Legendary (8):  Coconut → Burro's Tail     [10K → 93K coins]
├── Mythical (7):   Mushroom → Grape           [150K → 850K coins]
├── Divine (7):     Pepper → Sunflower         [1M → 100M coins]
└── Celestial (3):  Starweaver → Moonbinder    [1B → 50B coins]

ABILITIES (67) → owned by pets via weighted pools, scale with STR
├── Continuous (49): Coin Finding, Crop Effects, Growth Boosts, Hunger, Weather/Mutation Granting
├── Hatch Triggers (10): Hatch XP, Max Strength, Pet Mutation, Double Hatch
├── Sell Triggers (5): Sell Boost I-IV, Crop Refund
├── Harvest Triggers (1): Double Harvest
└── Sell Pet Triggers (2): Pet Refund I-II

WEATHER EVENTS (5)
├── Hydro (regular, every 20-30 min, 5 min duration)
│   ├── Rain → Wet (×2) at 7%/min; Chilled crops → Frozen (×6)
│   ├── Snow [internal: Frost] → Chilled (×2) at 7%/min; Wet crops → Frozen (×6)
│   └── Thunderstorm → Thunderstruck (×5) at 7%/min
└── Lunar (every 4 hours, 10 min duration)
    ├── Dawn (67%) → Dawnlit (×4) at 1%/min; + Dawnbinder crop → Dawnbound (×7) at 25%/min
    └── Amber Moon (33%) → Amberlit [Ambershine] (×6) at 1%/min; + Moonbinder → Amberbound [Ambercharged] (×10) at 25%/min

MUTATIONS (10)
├── Weather: Wet (×2), Chilled (×2), Frozen (×6), Thunderstruck (×5)
│   └── Mutually exclusive within group; Thunderstruck also exclusive with Wet/Chilled/Frozen
├── Lunar: Dawnlit (×4), Amberlit (×6), Dawnbound (×7), Amberbound (×10)
│   └── Dawnbound replaces Dawnlit; Amberbound replaces Amberlit
├── Colour: Gold (×25, 1% base plant chance), Rainbow (×50, 0.1% base plant chance)
│   └── Mutually exclusive with each other
└── STACKING: Weather + Lunar = ADDITIVE; (Weather+Lunar) × Colour = MULTIPLICATIVE

TOOLS (11)
├── Consumable: Watering Can (5K), Planter Pot (25K), Crop Cleanser (80K)
├── Permanent: Garden Shovel (1M)
└── Potions (carnival/ability only, 1B+ coin price = unpurchasable): Wet, Chilled, Dawnlit, Frozen, Amberlit, Gold, Rainbow

DECOR (43)
├── Cosmetic (39): Rocks, Benches, Arches, Bridges, Lamp Posts, etc. — wood/stone/marble tiers
├── Functional (4): Feeding Trough (9 slots), Decor Shed (25), Pet Hutch (25), Seed Silo (25)
└── Seasonal items have expiry dates
```

### Key Cross-Entity Links

**Pet → Ability (NEW: weighted pools)**
Each pet's abilities aren't fixed — they're drawn from a weighted probability pool at hatch time. This is critical information the wiki never showed:
- Turkey: 60% Rain Granter, 35% Egg Growth II, 5% Double Hatch
- Squirrel: 70% Coin Finder III, 20% Sell Boost III, 10% Pet Mutation Boost II
- Pony: 25% each of Sell Boost III, Coin Finder III, Hunger Restore II, Seed Finder II
- Capybara: 50% Double Harvest, 50% Crop Refund

**Crop → Pet diet** (35 of 44 crops fed to at least one pet):
- Most-fed: Pumpkin (4 pets: Chicken, Pig, Squirrel, Goat)
- Exclusive diets: Fava Bean→Turkey, Beet→Pony, Gentian→Horse, Cacao→Fire Horse
- Unfed (sell-only): Cabbage, Rose, Delphinium, Pine Tree, Peach, Violet Cort, Starweaver, Dawnbinder, Moonbinder

**Pet weight system** (source reveals two-part formula):
- `matureWeight` = base weight at maturity (source field)
- `maxScale` = maximum size multiplier (from Crop Size Boost abilities)
- Wiki "Max Weight" = `matureWeight × maxScale` (verified: 14/14 match)
- Example: Turtle base 150kg × maxScale 2.5 = 375kg max weight

**Ability tier system** (67 abilities across progression tiers):
- Most ability families have 3 tiers (I/II/III) owned by progressively rarer pets
- Snow-conditional variants exist for most families (active only during Snow weather)
- Dawn/Amber Moon conditional variants exist for mutation/growth families
- NEW abilities not on wiki: Copycat, Seed Finder IV (0.01% base!), Tier III of most families

---

## 5. Chunk Architecture (Revised)

### Layer 1 — Entity Chunks (~218 chunks)

Every entity gets one self-contained chunk using display names.

**Pet chunk template** (21 chunks):
```
[PET] Bee
Egg: Common Egg (5% hatch chance)
Rarity: Common | Maturity: 12 hours | Max Scale: 2.5
Hunger Cost: 1,500 coins to fill | Mature Weight: 0.2 kg (max 0.5 kg)
Maturity Sell Price: 30,000 coins
Diet: Strawberry, Blueberry, Daffodil, Lily, Chrysanthemum
Ability Pool: Crop Size Boost I (50%), Weather Mutation Boost I (50%)
  - Crop Size Boost I: 0.30% × STR chance/min, 6% × STR scale increase
  - Weather Mutation Boost I: 15% × STR chance increase for weather mutations
```

**Crop chunk template** (44 chunks):
```
[CROP] Strawberry
Rarity: Common | Harvest: Multi (5 slots, 70s regrow)
Seed Price: 50 coins (21 credits) | Base Sell: 14 coins
Base Weight: 0.05 kg | Max Scale: 2× (max weight: 0.10 kg)
Fed to: Worm, Bee, Bunny
Source: Seed Shop
```

**Ability chunk template** (67 chunks):
```
[ABILITY] Weather Mutation Boost I
Internal ID: ProduceMutationBoost
Trigger: continuous (passive)
Effect: Increases chance of garden crops gaining weather mutations by 15% × STR
Owned by: Bee (50% weight in ability pool)
Tier progression: I (Bee, 15%) → II (Butterfly, 20%) → III (unknown pet, 25%)
Weather variants: Snow Boost (Stoat, 32%), Dawn Boost (Horse, 36%), Amber Moon Boost (Fire Horse, 40%)
```

**Mutation chunk template** (10 chunks):
```
[MUTATION] Amberbound
Internal ID: Ambercharged | Display: Amberbound
Category: Lunar | Multiplier: ×10
Source: During Amber Moon, Amberlit crops adjacent to a Moonbinder crop have 25%/min chance
Replaces: Amberlit (×6) — does not stack, upgrades it
Stacks with: Any weather mutation (additive) + Gold or Rainbow (multiplicative)
Best combo: Frozen (×6) + Amberbound (×10) + Rainbow (×50) = ×800
```

**Weather event chunk** (5 chunks):
```
[WEATHER] Amber Moon
Internal ID: AmberMoon | Group: Lunar
Frequency: Every 4 hours (33% chance; Dawn is 67%) | Duration: 10 min
Mutation: Amberlit [Ambershine] (×6) at 1% chance/min per mature crop
Upgrade path: Amberlit → Amberbound (×10) if adjacent to Moonbinder crop (25%/min)
Pet abilities that boost: Amber Moon Boost (Fire Horse, +40%), Weather Mutation Boost I/II/III (Bee/Butterfly/?, +15/20/25%)
Pet that grants Amberlit directly: Fire Horse (Amberlit Granter, 2% × STR/min)
```

**Egg chunk template** (8 chunks):
```
[EGG] Snow Egg
Internal ID: SnowEgg | Price: 200,000,000 coins (269 credits)
Rarity: Legendary | Hatch Time: 12 hours
Requires: Active Snow weather to purchase
Spawns: Snow Fox (75%), Stoat (20%), Caribou (5%)
See also: Winter Egg (same pets, 80M coins, seasonal availability, no weather requirement)
```

**Tool chunk template** (11 chunks):
```
[TOOL] Frozen Potion
Internal ID: FrozenPotion
Price: 1,000,000,004 coins (effectively unpurchasable)
Rarity: Rare | One-time use
Effect: Instantly applies Frozen mutation to target crop
Source: Carnival Stand prize only — cannot be bought from Tool Shop
```

**Decor chunk** (functional only, 4 chunks — cosmetic decor gets summary chunks):
```
[DECOR] Feeding Trough
Price: 10,000,000 coins (199 credits)
Rarity: Rare | Permanent (one-time purchase)
Capacity: 9 crop items
Effect: Stores crops and automatically feeds hungry active pets
```

**Game constants chunk** (1 chunk):
```
[SYSTEM] Game Constants
Active pet slots: 3
Main inventory: 100 slots
Pet Hutch: 25 pets | Decor Shed: 25 items | Seed Silo: 25 items | Feeding Trough: 9 items
Strength range: 80 (base at scale 1) to 100 (at max scale)
Base strength = max strength - 30; grows with XP (3,600 XP/hour of maturity)
Friend bonus: +10% sell price per additional player (max +50% with 6 players)
Insta-grow cost: ~0.003 credits per second remaining
```

### Layer 2 — Relationship Chunks (~120–150 chunks)

**Diet chains** (21 chunks, one per pet):
```
[DIET CHAIN] Turkey
Turkey eats: Fava Bean (250 coins, multi 8 slots, 15min regrow),
  Corn (1,300 coins, multi 1 slot, 2min 10s regrow),
  Squash (55,000 coins, multi 3 slots, 25min regrow)
Turkey hunger cost: 500 coins (lowest in game tied with Worm)
Best budget: Fava Bean (cheapest seed, 8 slots = 8 harvests per plant)
Best hunger/coin: All 3 are cheap; Squash has highest per-crop sell (3,500)
Note: Fava Bean is exclusive to Turkey's diet — no other pet eats it
```

**Crop feeder reverse map** (35 chunks):
```
[CROP FEEDERS] Pumpkin
Pumpkin feeds: Chicken (Uncommon), Pig (Rare), Squirrel (Legendary), Goat (Legendary)
Pumpkin stats: 3,000 coin seed, 3,700 base sell, single-harvest, 6 kg base, max 18 kg
Strategy: High sell value = good hunger restore per feed. Single-harvest = rebuy seeds each time.
```

**Ability tier progressions** (grouped into ~20 family chunks instead of 67 individual):
```
[ABILITY FAMILY] Sell Boost (I → II → III → IV)
Tier I: Bunny (40% weight) — 10% × STR prob, 20% × STR sell bonus
Tier II: Pig (30% weight) — 12% × STR prob, 30% × STR sell bonus
Tier III: Squirrel (20% weight) — 14% × STR prob, 40% × STR sell bonus
Tier IV: Peacock (40% weight) — 16% × STR prob, 50% × STR sell bonus
Also: Pony has Sell Boost III (25% weight)
Trigger: sellAllCrops — procs when you sell your crop batch
Strategy: At STR 100, Peacock gives 16% chance of +50% on entire sell batch. Stack with mutations.
```

```
[ABILITY FAMILY] Weather Mutation Boost (I → II → III + conditional variants)
Base tiers:
  I: Bee (50% weight) — 15% × STR increase
  II: Butterfly (40% weight) — 20% × STR increase
  III: [no assigned pet found in source] — 25% × STR increase
Conditional variants (active only during specific weather):
  Snow Boost: Stoat (20% weight) — 32% × STR increase (Snow only)
  Dawn Boost: Horse (30% weight) — 36% × STR increase (Dawn only)
  Amber Moon Boost: Fire Horse (30% weight) — 40% × STR increase (Amber Moon only)
Trigger: continuous (passive)
Note: These boost the BASE mutation chance of weather events, not the multiplier.
  E.g. Rain gives 7% base → with Bee at STR 100, becomes 7% × 1.15 = 8.05%/min/crop
```

```
[ABILITY FAMILY] Mutation Granters
Rain Granter: Turkey (60% weight) — 10% × STR chance/min to apply Wet
Snow Granter: Snow Fox (30%), Stoat (40%) — 8% × STR chance/min to apply Chilled
Frost Granter: Caribou (50%) — 6% × STR chance/min to apply Frozen
Dawnlit Granter: Horse (40%) — 4% × STR chance/min to apply Dawnlit
Amberlit Granter: Fire Horse (40%) — 2% × STR chance/min to apply Amberlit
Gold Granter: [pet unknown] — 0.72% × STR chance/min to apply Gold
Rainbow Granter: [pet unknown] — 0.72% × STR chance/min to apply Rainbow
These bypass weather requirements entirely — pet applies mutation directly to random crops.
```

**Weather-mutation combo chains** (6 chunks):
```
[WEATHER COMBO] Frozen mutation path
Step 1: Rain → Wet (×2) at 7%/min per crop
Step 2: Snow → Wet crops upgrade to Frozen (×6) at 7%/min
Alternative paths:
  - Turkey (Rain Granter 10%/min) + Snow Fox/Stoat (Snow Granter 8%/min)
  - Caribou (Frost Granter 6%/min) — applies Frozen directly, no Wet step needed
  - Frozen Potion (Carnival Stand prize)
Cannot combine: Frozen is exclusive with Thunderstruck
Can combine: + any Lunar mutation (additive) + Gold or Rainbow (multiplicative)
```

**Multiplier stacking guide** (3 chunks):
```
[MULTIPLIER GUIDE] Maximum sell value
RULE 1: Weather + Lunar = ADDITIVE
  Frozen (×6) + Amberbound (×10) = ×16
  Thunderstruck (×5) + Dawnbound (×7) = ×12

RULE 2: (Weather+Lunar) × Colour = MULTIPLICATIVE
  ×16 × Rainbow (×50) = ×800 (theoretical maximum)
  ×16 × Gold (×25) = ×400

RULE 3: Size scales sell price linearly
  Weight = baseWeight × currentScale; sell = baseSell × (weight / baseWeight)

RULE 4: Friend bonus is additive
  +10% per other player in garden, max +50% (6 total players)

Top 5 multiplier combos:
  1. Frozen + Amberbound + Rainbow = ×800
  2. Thunderstruck + Amberbound + Rainbow = ×750
  3. Frozen + Dawnbound + Rainbow = ×650
  4. Frozen + Amberlit + Rainbow = ×600 (tied)
  4. Wet/Chilled + Amberbound + Rainbow = ×600 (tied)
  4. Thunderstruck + Dawnbound + Rainbow = ×600 (tied)
```

**Snow Egg vs Winter Egg** (1 chunk — common confusion):
```
[COMPARISON] Snow Egg vs Winter Egg
Both hatch the same pets: Snow Fox (75%), Stoat (20%), Caribou (5%)

Snow Egg: 200M coins / 269 credits. Requires active Snow weather to buy.
  Available permanently but weather-gated.
Winter Egg: 80M coins / 199 credits. No weather requirement.
  Seasonal availability (has expiry date).

Strategy: Winter Egg is cheaper and easier to obtain, but only during winter events.
Snow Egg costs more but is always technically available if Snow weather is active.
```

### Layer 3 — Category Summaries (~30–40 chunks)

```
[SUMMARY] All pets by egg type (with ability weights)
Common Egg (100K coins, 10 min hatch):
  Worm 60% — Seed Finder I (50%), Crop Eater (50%)
  Snail 35% — Coin Finder I (100%)
  Bee 5% — Crop Size Boost I (50%), Weather Mutation Boost I (50%)

Uncommon Egg (1M coins, 1h hatch):
  Chicken 65% — Egg Growth Boost I (80%), Pet Refund I (20%)
  Bunny 25% — Coin Finder II (60%), Sell Boost I (40%)
  Dragonfly 10% — Hunger Restore I (70%), Pet Mutation Boost I (30%)

Rare Egg (10M coins, 6h hatch):
  Pig 80% — Sell Boost II (30%), Hatch XP Boost I (30%), Max Strength Boost I (30%)
  Cow 15% — Seed Finder II (30%), Hunger Boost I (30%), Plant Growth Boost I (30%)
  Turkey 5% — Rain Granter (60%), Egg Growth Boost II (35%), Double Hatch (5%)

Legendary Egg (100M coins, 12h hatch):
  Squirrel 60% — Coin Finder III (70%), Sell Boost III (20%), Pet Mutation Boost II (10%)
  Turtle 30% — Hunger Restore II (25%), Hunger Boost II (25%), Plant Growth Boost II (25%), Egg Growth Boost III (25%)
  Goat 10% — Max Strength Boost II (10%), Hatch XP Boost II (40%), XP Boost I (40%)

Snow/Winter Egg (200M/80M coins, 12h hatch):
  Snow Fox 75% — Snow Granter (30%), Snow Coin Finder (30%), Snow XP Boost (30%)
  Stoat 20% — Snow Granter (40%), Snow Hunger Boost (40%), Snow Boost (20%)
  Caribou 5% — Frost Granter (50%), Snow Plant Growth Boost (40%), Snow Crop Size Boost (10%)

Horse Egg (200M coins, 12h hatch):
  Pony 60% — Sell Boost III (25%), Coin Finder III (25%), Hunger Restore II (25%), Seed Finder II (25%)
  Horse 35% — Dawn Boost (30%), Dawnlit Granter (40%), Dawn Plant Growth Boost (10%), Hatch XP Boost II (20%)
  Fire Horse 5% — Amber Moon Boost (30%), Max Strength Boost II (20%), Amberlit Granter (40%), Amber Plant Growth Boost (10%)

Mythical Egg (1B coins, 24h hatch):
  Butterfly 75% — Crop Size Boost II (40%), Weather Mutation Boost II (40%), Seed Finder III (20%)
  Peacock 20% — Sell Boost IV (40%), XP Boost II (50%), Pet Refund II (10%)
  Capybara 5% — Double Harvest (50%), Crop Refund (50%)
```

```
[SUMMARY] Crops by rarity tier (source code confirmed)
Common (5): Carrot (10), Cabbage (30), Strawberry (50), Aloe (135), Beet (210)
Uncommon (7): Rose (229), Fava Bean (250), Delphinium (300), Blueberry (400), Apple (500), Tulip (600), Tomato (800)
Rare (7): Daffodil (1K), Corn (1.3K), Watermelon (2.5K), Pumpkin (3K), Echeveria (4.2K), Pear (6K), Gentian (9K)
Legendary (8): Coconut (10K), Pine Tree (12K), Banana (15K), Lily (20K), Camellia (55K), Squash (55K), Peach (85K), Burro's Tail (93K)
Mythical (7): Mushroom (150K), Cactus (250K), Bamboo (400K), Poinsettia (500K), Violet Cort (520K), Chrysanthemum (670K), Grape (850K)
Divine (7): Pepper (1M), Lemon (2M), Passion Fruit (2.75M), Dragon Fruit (5M), Cacao (10M), Lychee (25M), Sunflower (100M)
Celestial (3): Starweaver (1B), Dawnbinder (10B), Moonbinder (50B)
```

```
[SUMMARY] Most cost-effective pets to maintain
Cheapest hunger cost:
  1. Dragonfly — 250 coins to fill (cheapest in game)
  2. Turkey — 500 coins (tied with Worm)
  3. Worm — 500 coins
  4. Bunny — 750 coins
  5. Snail — 1,000 coins
Most expensive:
  1. Fire Horse — 200,000 coins
  2. Capybara — 150,000 coins
  3. Peacock — 100,000 coins / Turtle — 100,000 coins
```

### Layer 4 — Strategy/Guide Chunks (~20–30 chunks)

```
[STRATEGY] Early game progression
1. Plant free Carrot seed → sell for 20 coins
2. Buy Common Egg (100K) → likely Worm (60%). Worm has Seed Finder I + Crop Eater.
3. Crop Eater auto-sells non-mutated crops at 150% × STR bonus. Seed Finder I finds free common/uncommon seeds.
4. Buy Strawberry (50) / Blueberry (400) seeds to feed Worm.
5. Save for Uncommon Egg (1M) → Chicken (65%) has Egg Growth I (80% chance) + Pet Refund I (20%)
6. Chicken speeds egg hatching by 7 min × STR per proc. Pet Refund recycles unlucky hatches.
7. Target: Bunny (25%) for Coin Finder II (60%) + Sell Boost I (40%) = passive income
8. 3 active pet slots → run Worm + Chicken + Bunny early; replace Worm→Cow mid-game
```

```
[STRATEGY] Maximizing coin income
Income pets (pick 1-2 for active slots):
  - Squirrel: Coin Finder III (70%) finds up to 10M × STR coins
  - Peacock: Sell Boost IV (40%) gives 16% chance of +50% sell bonus
  - Pony: Coin Finder III (25%) + Sell Boost III (25%) — jack of all trades
  - Snow Fox: Snow Coin Finder during Snow — up to 5M × STR coins

Mutation stacking for max crop value:
  1. Grow high-value single-harvest: Mushroom (160K), Cactus (261K), Bamboo (500K), Violet Cort (600K)
  2. Get Frozen: wait for Rain→Snow combo, or use Caribou (Frost Granter 6%/min)
  3. Get Amberbound: plant Moonbinder adjacent, wait for Amber Moon
  4. Get Rainbow: extremely rare (0.1% base, or Rainbow Granter pet at 0.72%/min)
  5. Sell with Sell Boost active

Max theoretical single crop sale:
  Frozen (6) + Amberbound (10) + Rainbow (50) = ×800
  Violet Cort at max weight: 600,000 × 800 × 3.5 scale = 1,680,000,000 coins
  + Friend bonus (50%): 2,520,000,000 coins
```

```
[STRATEGY] Optimal 3-pet loadout by game stage
Early: Worm (seeds+auto-sell) + Snail (coin finding) + Chicken (egg speed+pet refund)
Mid: Turkey (rain+egg speed+double hatch) + Cow (seeds+hunger+growth) + Bunny (coins+sell boost)
Late: Butterfly (mutation+size+seeds) + Squirrel (coins+sell+pet mutation) + Turtle (hunger+growth+eggs)
Winter: Snow Fox + Stoat + Caribou (full snowy suite — massive boost during Snow weather)
Horse: Horse (dawn boost+dawnlit granting) + Fire Horse (amber boost+amberlit granting) + Turtle (support)
Max income: Squirrel + Peacock + Pony (triple coin finding + sell boost stacking)
```

```
[STRATEGY] Garden Journal completion
Crop variants: 44 crops × 12 variants = 528 entries
  Variants: Normal, Wet, Chilled, Frozen, Dawnlit, Ambershine, Thunderstruck, Gold, Rainbow, Dawncharged, Ambercharged, Max Weight
Pet variants: 21 pets × 4 variants = 84 entries
  Variants: Normal, Gold, Rainbow, Max Weight
Total: 612 journal entries

Tips:
  - Use Planter Pot (25K) to log crop variants without harvesting
  - Cheapest mutation path: Rain (Wet) → Snow (Frozen) covers 3 weather variants
  - Dawnlit/Amberlit from pet granters: Horse/Fire Horse are most reliable
  - Gold/Rainbow: 1%/0.1% base chance on planting, or use granter pets
  - Max Weight pets need STR 100 (max scale + full XP maturity)
  - Hardest: Celestial crop variants (1B+ seed cost), Capybara mutations (5% hatch × ability RNG)
```

---

## 6. Updated Metadata Schema

```json
{
  "chunk_id": "pet_bee_entity",
  "layer": "entity",
  "entity_type": "pet",
  "entity_name": "Bee",
  "internal_id": "Bee",
  "egg_type": "CommonEgg",
  "related_entities": ["Strawberry", "Blueberry", "Daffodil", "Lily", "Chrysanthemum",
                       "ProduceScaleBoost", "ProduceMutationBoost"],
  "related_display_names": ["Strawberry", "Blueberry", "Daffodil", "Lily", "Chrysanthemum",
                            "Crop Size Boost I", "Weather Mutation Boost I"],
  "related_types": ["crop", "ability"],
  "query_intents": ["lookup", "diet", "abilities", "hatching"],
  "rarity_tier": "Common",
  "token_count": 120
}
```

Full tag vocabulary:

| Field | Values |
|-------|--------|
| `layer` | entity, relationship, summary, strategy |
| `entity_type` | pet, crop, ability, mutation, weather, tool, egg, decor, plant_ability, constant |
| `rarity_tier` | Common, Uncommon, Rare, Legendary, Mythical, Divine, Celestial |
| `egg_type` | CommonEgg, UncommonEgg, RareEgg, LegendaryEgg, SnowEgg, WinterEgg, HorseEgg, MythicalEgg |
| `query_intents` | lookup, diet, feeding, abilities, hatching, weather, mutation, selling, growing, comparison, strategy, journal, progression, income |
| `harvest_type` | Single, Multiple |
| `weather_relevant` | Rain, Frost, Thunderstorm, Dawn, AmberMoon |
| `ability_trigger` | continuous, hatchEgg, sellAllCrops, harvest, sellPet |
| `ability_family` | coin_finder, seed_finder, sell_boost, crop_size, weather_mutation, hunger_boost, hunger_restore, plant_growth, egg_growth, xp_boost, mutation_granter, hatch_xp, max_strength, pet_mutation, refund, special |

---

## 7. Entity Name Registry (for Query Analysis)

This is the lookup table the regex-based query analyser uses to detect entities in user input. All entries use **display names** (what players type). Aliases handle common variations.

```python
ENTITY_REGISTRY = {
    # PETS (21) — key: display name, value: internal ID
    "worm": "Worm", "snail": "Snail", "bee": "Bee",
    "chicken": "Chicken", "bunny": "Bunny", "dragonfly": "Dragonfly",
    "pig": "Pig", "cow": "Cow", "turkey": "Turkey",
    "squirrel": "Squirrel", "turtle": "Turtle", "goat": "Goat",
    "snow fox": "SnowFox", "snowfox": "SnowFox",
    "stoat": "Stoat", "caribou": "WhiteCaribou",
    "pony": "Pony", "horse": "Horse",
    "fire horse": "FireHorse", "firehorse": "FireHorse",
    "butterfly": "Butterfly", "peacock": "Peacock", "capybara": "Capybara",

    # CROPS (44) — display names → internal IDs
    "carrot": "Carrot", "cabbage": "Cabbage", "strawberry": "Strawberry",
    "aloe": "Aloe", "beet": "Beet", "rose": "Rose",
    "delphinium": "Delphinium", "fava bean": "FavaBean", "favabean": "FavaBean",
    "blueberry": "Blueberry", "apple": "Apple",
    "tulip": "OrangeTulip", "orange tulip": "OrangeTulip",
    "tomato": "Tomato", "daffodil": "Daffodil", "corn": "Corn",
    "watermelon": "Watermelon", "pumpkin": "Pumpkin",
    "echeveria": "Echeveria", "pear": "Pear", "gentian": "Gentian",
    "coconut": "Coconut", "pine tree": "PineTree", "pinetree": "PineTree",
    "banana": "Banana", "lily": "Lily", "camellia": "Camellia",
    "squash": "Squash", "peach": "Peach",
    "burro's tail": "BurrosTail", "burros tail": "BurrosTail",
    "mushroom": "Mushroom", "cactus": "Cactus", "bamboo": "Bamboo",
    "poinsettia": "Poinsettia", "violet cort": "VioletCort",
    "chrysanthemum": "Chrysanthemum", "mum": "Chrysanthemum", "chrys": "Chrysanthemum",
    "grape": "Grape", "pepper": "Pepper", "lemon": "Lemon",
    "passion fruit": "PassionFruit", "passionfruit": "PassionFruit",
    "dragon fruit": "DragonFruit", "dragonfruit": "DragonFruit",
    "cacao": "Cacao", "lychee": "Lychee", "sunflower": "Sunflower",
    "starweaver": "Starweaver",
    "dawnbinder": "DawnCelestial", "dawn binder": "DawnCelestial",
    "moonbinder": "MoonCelestial", "moon binder": "MoonCelestial",

    # EGGS (8)
    "common egg": "CommonEgg", "uncommon egg": "UncommonEgg",
    "rare egg": "RareEgg", "legendary egg": "LegendaryEgg",
    "snow egg": "SnowEgg", "winter egg": "WinterEgg",
    "horse egg": "HorseEgg", "mythical egg": "MythicalEgg",

    # MUTATIONS (10) — display names (what players see)
    "wet": "Wet", "chilled": "Chilled", "frozen": "Frozen",
    "thunderstruck": "Thunderstruck",
    "dawnlit": "Dawnlit", "dawnbound": "Dawncharged",
    "amberlit": "Ambershine", "amberbound": "Ambercharged",
    "gold": "Gold", "rainbow": "Rainbow",

    # WEATHER (5) — display names
    "rain": "Rain", "snow": "Frost", "thunderstorm": "Thunderstorm",
    "dawn": "Dawn", "amber moon": "AmberMoon", "ambermoon": "AmberMoon",

    # TOOLS (11)
    "watering can": "WateringCan", "planter pot": "PlanterPot",
    "crop cleanser": "CropCleanser", "shovel": "Shovel", "garden shovel": "Shovel",
    "wet potion": "WetPotion", "chilled potion": "ChilledPotion",
    "dawnlit potion": "DawnlitPotion", "frozen potion": "FrozenPotion",
    "amberlit potion": "AmberlitPotion", "gold potion": "GoldPotion",
    "rainbow potion": "RainbowPotion",

    # FUNCTIONAL DECOR (4)
    "feeding trough": "FeedingTrough", "trough": "FeedingTrough",
    "decor shed": "DecorShed", "pet hutch": "PetHutch", "seed silo": "SeedSilo",
}
```

---

## 8. Intent Detection Patterns

| User Query Pattern | Intent | Chunks to Retrieve |
|-------------------|--------|-------------------|
| "what does [pet] eat" | diet | Pet entity + diet chain |
| "which pet eats [crop]" | reverse_diet | Crop feeders chunk |
| "[pet] abilities" / "what can [pet] do" | abilities | Pet entity + relevant ability family chunks |
| "how do I get [mutation]" | mutation_path | Mutation entity + weather combo chunk |
| "[mutation] + [mutation]" / "stacking" | multiplier_math | Multiplier guide chunks |
| "best pet for [purpose]" | strategy | Summary + strategy chunks |
| "how much does [crop] sell for" | selling | Crop entity |
| "best money making" / "how to get rich" | income | Income strategy + multiplier guide |
| "[crop] grow time" / "regrow" | growing | Crop entity |
| "what's in [egg]" / "what can I hatch" | hatching | Egg entity + pet summary by egg |
| "snow egg vs winter egg" | comparison | Snow/Winter egg comparison chunk |
| "divine crops" / "celestial" | rarity_lookup | Crop rarity summary |
| "what does [ability] do" | ability_detail | Ability entity + family chunk |
| "[pet] ability chance" / "weights" | ability_weights | Pet entity (ability pool section) |
| "journal" / "variants" / "completion" | journal | Journal strategy chunk |
| "how many [entity type]" | count | Relevant summary chunk |

---

## 9. Retrieval Pipeline

```
User Query: "How do I get Amberbound on my crops?"
    │
    ▼
STAGE 1: Query Analysis
    Entity registry match: "amberbound" → Mutation (internal: Ambercharged)
    Intent: mutation_path
    │
    ▼
STAGE 2: Direct Retrieval (filtered by entity + intent)
    Pull: [Amberbound mutation entity] + [Amber Moon weather combo]
    │
    ▼
STAGE 3: Graph Expansion
    Amberbound requires: Amberlit + adjacent Moonbinder + Amber Moon weather
    → Pull: [Amberlit mutation entity], [Moonbinder crop entity], [Amber Moon weather entity]
    → Check for pet granters: Fire Horse has Amberlit Granter (2%/min)
    → Pull: [Fire Horse pet entity] (if space in context)
    │
    ▼
STAGE 4: Context Assembly (~1200 tokens max)
    1. Amberbound mutation entity (what it is, ×10 multiplier)
    2. Weather combo chunk (step-by-step path)
    3. Moonbinder crop entity (50B seed cost, celestial)
    4. Fire Horse mention (Amberlit Granter shortcut)
    │
    ▼
STAGE 5: Generate (Mistral 7B)
    "Amberbound gives a ×10 multiplier and is the strongest lunar mutation.
     To get it: 1) Plant a Moonbinder crop (Celestial, 50B seed cost).
     2) Wait for Amber Moon weather (33% chance every 4 hours, lasts 10 min).
     3) During Amber Moon, your mature crops have 1%/min chance to get Amberlit (×6).
     4) Any Amberlit crop adjacent to a Moonbinder has 25%/min chance to upgrade to Amberbound (×10).
     Shortcut: Fire Horse's Amberlit Granter ability (2%/min) can apply Amberlit without
     waiting for weather, then you only need Amber Moon for the Amberbound upgrade step."
```

---

## 10. Model Stack

| Component | Model | Runs On | Memory |
|-----------|-------|---------|--------|
| Embeddings | `nomic-embed-text` | CPU | ~275 MB RAM |
| Generation | `mistral-7b-instruct-v0.3` Q4_K_M | GPU | ~4.5 GB VRAM |
| Vector Store | ChromaDB | CPU | Minimal |
| Query Analysis | Regex entity registry + intent rules | CPU | None |

Corpus: ~500-650 chunks × ~100 tokens avg = ~55,000 tokens. Still trivially small for ChromaDB. Retrieval remains sub-millisecond.

---

## 11. Data Pipeline: Source Code → Chunks

The source code extraction changes the update pipeline fundamentally. Instead of scraping wiki HTML (which can be stale), we can parse the game client directly.

### Pipeline stages:

```
1. EXTRACT: Parse JS source → structured JSON (source_truth.json)
   - Regex/AST extraction of Ie (pets), z0 (crops), _s (abilities), bs (mutations), etc.
   - Resolve internal→display name mapping
   - Validate: count entities, check for new additions

2. TRANSFORM: JSON → chunk text files
   - Apply chunk templates (Layer 1-4)
   - Pre-compute relationship chunks (diet chains, ability families, combos)
   - Generate metadata JSON per chunk

3. LOAD: Chunks → ChromaDB
   - Embed with nomic-embed-text
   - Upsert with metadata filters
   - Log: new/changed/deleted chunks

4. VALIDATE: Smoke test queries
   - "What does Bee eat?" → must return Strawberry, Blueberry, Daffodil, Lily, Chrysanthemum
   - "Amberbound multiplier" → must return ×10
   - "How many abilities are there?" → must return 67
```

### Update triggers:
- Game client JS changes (monitor bundle hash)
- Wiki History section shows new patch notes
- User reports incorrect answer → manual review

### Versioning:
Each chunk gets `source_version` field tied to the client build date. When source changes, diff against previous extraction to identify affected chunks only.

---

## 12. Implementation Priority

| # | Task | Chunks | Why |
|---|------|--------|-----|
| 1 | Source code parser → `source_truth.json` | — | Foundation: all data flows from here |
| 2 | Entity registry + name resolver | — | Query analysis needs this before anything |
| 3 | Layer 1: Pet entity chunks (21) | 21 | Most common query target |
| 4 | Layer 1: Crop entity chunks (44) | 44 | Second most common |
| 5 | Layer 2: Diet chains + crop feeders (56) | 56 | Diet = #1 query type |
| 6 | Layer 1: Ability entity chunks (67) | 67 | Now 67 not 29 |
| 7 | Layer 2: Ability family chunks (~20) | 20 | Tier progression context |
| 8 | ChromaDB + nomic-embed-text indexing | — | Enable retrieval |
| 9 | Mistral 7B generation + system prompt | — | Enable responses |
| 10 | Layer 1: Mutation + weather + egg chunks | 23 | Core game systems |
| 11 | Layer 2: Weather combos + multiplier guide | 9 | Strategy queries |
| 12 | Layer 3: Summary chunks | 35 | Comparison/ranking |
| 13 | Layer 4: Strategy chunks | 25 | Highest value-add |
| 14 | Layer 1: Tool + decor + constants chunks | 16 | Lower-priority lookups |
| 15 | FastAPI wrapper + Discord integration | — | Deployment |
| 16 | Conversation buffer + follow-up handling | — | Polish |

**Total chunks: ~500-650**
**Estimated chunk authoring: ~60% automated from source_truth.json, ~40% hand-written (relationship, summary, strategy layers)**
