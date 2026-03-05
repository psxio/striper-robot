# Strype Business Plan — Internal Strategy Document

**Last updated:** March 2026
**Audience:** Founding team only. Not for external distribution.
**Product:** Strype autonomous parking lot striping robot + cloud platform.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Market Opportunity](#market-opportunity)
3. [Moat Analysis](#moat-analysis)
4. [Revenue Streams](#revenue-streams)
5. [Pricing Strategy](#pricing-strategy)
6. [Unit Economics](#unit-economics)
7. [Go-to-Market](#go-to-market)
8. [Competitive Landscape](#competitive-landscape)
9. [Growth Flywheel](#growth-flywheel)
10. [Key Metrics](#key-metrics)
11. [Risk Analysis](#risk-analysis)
12. [Financial Projections](#financial-projections)
13. [Technical Moat Details](#technical-moat-details)
14. [Appendix: Reference Documents](#appendix-reference-documents)

---

## Executive Summary

Strype is an autonomous parking lot line striping robot paired with a cloud
platform for lot design and fleet management.

**The numbers:**
- US parking lot maintenance market: ~$4B/year
- Striping is ~15% of that: ~$600M/year
- Average manual striping job: $800-2,000 per lot
- Strype robot COGS: ~$780 (see `docs/bom.md`, Tier 2)
- Strype retail price: $2,495
- Gross margin on hardware: 69%
- Time to stripe a 50-space lot: 30-60 minutes (vs. 3-4 hours manual crew)
- Paint cost per lot: $60-100 (4-5 gallons traffic latex)

**The thesis:**
Manual parking lot striping is slow, inconsistent, expensive, and hard to
schedule. Property managers hate dealing with it. Striping contractors hate
the labor. Strype replaces a 2-person crew with a robot that does the job
faster, straighter, and cheaper. The robot is open-source hardware. The
business model layers recurring revenue on top: cloud platform SaaS,
pre-filled paint cartridges, and Robot-as-a-Service for property managers
who do not want to own equipment.

**Why now:**
- RTK GPS accuracy hit 8mm at $120 module cost (UM980 triband) -- this was
  $500+ three years ago
- ArduPilot/ArduRover is mature enough to run a striping robot with ~30 lines
  of Lua (no custom firmware needed)
- Hoverboard motors provide 700W of drive power for $30 from the used market
- The parking lot striping market has zero commercial autonomous solutions
  available for purchase in the US today (10Lines in Estonia is pre-commercial)
- Every funded competitor (TurfTank, TinyMobileRobots, SWOZI) targets sports
  fields, not parking lots

---

## Market Opportunity

### Market Size

| Segment | US Market Size | Strype Addressable? |
|---------|---------------|-------------------|
| Parking lot maintenance (total) | ~$4B/year | Partial |
| Parking lot striping | ~$600M/year | Yes -- primary target |
| Sports field marking | ~$200M/year | No -- crowded, different paint |
| Road/highway striping | ~$2B/year | No -- requires DOT certification |
| Warehouse floor marking | ~$100M/year | Future -- indoor GPS challenge |

### Customer Segments (in priority order)

**1. Striping contractors (primary buyer of hardware)**
- ~15,000 striping contractors in the US
- Average contractor does 200-500 lots/year
- Pain points: labor shortage, inconsistent quality, scheduling
- They buy the robot, use the platform, reorder consumables
- Lifetime value: $2,495 (robot) + $1,188/year (platform) + $2,000/year (consumables)

**2. Property management companies (primary buyer of RaaS)**
- ~50,000 property management companies in the US
- Manage 100-5,000+ parking lots each
- Pain points: vendor reliability, cost control, compliance documentation
- They subscribe to RaaS -- Strype owns the robot, does the job
- Lifetime value: $299/lot/year, 10-50 lots = $2,990-$14,950/year

**3. Facility maintenance teams (secondary hardware buyer)**
- Large campuses: universities, hospitals, corporate parks, airports
- Own 5-20 parking lots, need restriping 1-2x/year
- Buy one robot, use it across all their lots
- Lifetime value: $2,495 (robot) + $600/year (platform + consumables)

**4. Municipalities and HOAs (future)**
- Smaller lots, lower volume, price-sensitive
- Better served by RaaS than hardware purchase
- Reach through property management companies first

### Why Parking Lots, Not Sports Fields

Sports fields have 6+ funded competitors (TurfTank at $61K, TinyMobileRobots
at $30K+, SWOZI, FJD, Fleet Robot, CivDot). The market is being carved up.

Parking lots have exactly one pre-commercial competitor (10Lines, Estonia,
EUR 1.5M seed, launching 2026). The technical requirements are similar
(RTK GPS + differential drive + spray nozzle) but the go-to-market is
completely different: parking lot customers are property managers and
striping contractors, not athletic directors.

Parking lots are also more numerous. The US has ~800 million parking spaces
across ~100 million lots. Each lot needs restriping every 12-24 months.

---

## Moat Analysis

### Why Open-Source Hardware Is a Strength

The repo is public. Anyone can clone it and build a robot. This sounds like
a weakness. It is not, for five reasons:

**1. Credibility signal.**
Open-source hardware tells contractors and property managers: "We have
nothing to hide. The robot works. Here is exactly how." In a market where
every other vendor sells a $30K-$61K black box with a monthly subscription,
radical transparency is a differentiator. Contractors are tradespeople --
they respect seeing the wiring diagram.

**2. Community-driven validation.**
DIY builders are free QA. They find bugs, suggest improvements, and post
build videos. Every YouTube build video is free marketing. Every GitHub
issue is free testing. The community validates the product before we spend
a dollar on advertising.

**3. Press and word-of-mouth.**
"Open-source autonomous robot" is a story. "Another subscription robot" is
not. Open source generates disproportionate press coverage, Reddit threads,
Hacker News posts, and trade publication articles relative to marketing spend.

**4. Talent acquisition.**
Engineers want to work on open-source projects. When we hire, the entire
codebase is the interview -- candidates can evaluate us before we evaluate
them.

**5. Ecosystem lock-in without lock-in.**
Users who build DIY robots still need the cloud platform for lot design.
They still buy nozzles and paint cartridges. They become the most
passionate advocates because they chose us without being locked in.

### Five Layers of Defensibility

Each layer is harder to replicate than the last:

```
Layer 5: Data flywheel (lot layouts, optimization, pricing intelligence)
Layer 4: RaaS fleet operations (logistics, maintenance, scheduling)
Layer 3: Consumables ecosystem (cartridges, nozzles, replacement parts)
Layer 2: Cloud platform (lot designer, fleet mgmt, job scheduling)
Layer 1: Assembled, tested, calibrated hardware (the robot itself)
Layer 0: Open-source repo (freely available -- this is the base, not the moat)
```

**Layer 1 -- Assembled hardware.**
Cloning the repo is step 1 of a 20-step process. You still need to:
source a compatible hoverboard (must be STM32F103R or GD32F103R chip, Gen1
single-board only -- most cheap new hoverboards use incompatible AT32 chips),
flash FOC firmware with an ST-Link programmer, build the frame, wire
everything per the wiring guide (`docs/wiring_guide.md`), flash ArduRover
to the Pixhawk, load parameters, install Lua scripts, calibrate
accelerometer/compass/RC/GPS, tune PID gains, test paint solenoid timing,
and run field validation. Estimated build time: 20-25 hours over 2 weekends
(see `docs/quick_start.md`). An assembled, tested, calibrated Strype robot
eliminates all of that. Most contractors will pay $2,495 to skip 25 hours
of electronics work they are not qualified to do.

**Layer 2 -- Cloud platform.**
The lot designer turns a satellite image or DXF file into a mission plan
in minutes. Fleet management tracks which lots need restriping, schedules
jobs, and dispatches robots. Job history provides compliance documentation
for property managers. This is SaaS revenue that does not exist in the repo.

**Layer 3 -- Consumables.**
Pre-filled snap-in paint cartridges eliminate the mess and guesswork of
filling a paint reservoir. Nozzle packs with pre-configured spray patterns
for different line widths (4" standard, 12" crosswalk, 24" stop bar) mean
contractors do not need to source and test nozzles. Replacement parts
(solenoid valves, pump diaphragms, GPS antennas) are stocked and shipped
next-day. This is razor-and-blade recurring revenue.

**Layer 4 -- RaaS.**
Robot-as-a-Service for property management companies. Strype owns the
hardware, handles maintenance, supplies paint, and charges per-lot-per-year.
The property manager never touches the robot. This requires fleet operations
infrastructure (logistics, technician network, inventory management) that
cannot be cloned from a GitHub repo.

**Layer 5 -- Data flywheel.**
Every job generates lot layout data: dimensions, space count, line positions,
paint consumption, time-to-complete, GPS accuracy metrics. Aggregated and
anonymized, this data improves path optimization (better segment ordering =
less transit time = faster jobs), paint consumption estimates (more accurate
quotes), and lot layout templates (common patterns auto-detected). Over time,
this data becomes a moat: new entrants start from zero, Strype starts from
thousands of real lot layouts.

### Why Cloning the Repo Does Not Equal Competing

A competitor who clones the repo gets:
- Python path generation library (striper_pathgen)
- ArduRover parameter file and Lua scripts
- BOM and wiring documentation

A competitor who clones the repo does NOT get:
- Tested, calibrated hardware that works out of the box
- Cloud lot designer with satellite imagery integration
- Fleet management and job scheduling platform
- Snap-in paint cartridge system
- Supply chain for hoverboards with verified-compatible mainboards
- Customer support and field service
- Insurance and liability coverage for autonomous operation
- Lot layout database with optimization data
- Brand trust with contractors who need equipment that works on Monday morning

The repo is the recipe. Strype is the restaurant.

---

## Revenue Streams

### 1. Hardware Sales — Assembled Strype Robot

| Item | Price | COGS | Margin |
|------|-------|------|--------|
| Strype Robot (assembled, tested, calibrated) | $2,495 | $780 | 69% ($1,715) |
| Strype Starter Kit (robot + 1yr Pro platform + 10 cartridges) | $3,495 | $1,280 | 63% ($2,215) |

The robot ships assembled, with firmware loaded, parameters configured, PID
gains tuned for the standard frame, and a 30-minute phone onboarding session
included. The customer unpacks it, sets up their NTRIP connection in Mission
Planner, and runs their first job.

**Why $2,495:** This positions Strype as a professional tool, not a toy or
a hobby project. Striping contractors spend $500-2,000 on a manual striping
machine (Graco LineLazer, Titan PowrLiner). A $2,495 autonomous robot that
pays for itself in 2-3 jobs is an obvious purchase. It is also 12-24x
cheaper than competing autonomous solutions (TinyMobileRobots at $30K+,
TurfTank at $61K lease).

**Volume assumptions (conservative):**
- Year 1: 50 robots (mostly early adopters from the open-source community)
- Year 2: 200 robots (word-of-mouth + trade show presence)
- Year 3: 500 robots (channel partnerships + content marketing)

### 2. Platform SaaS — Strype Cloud

| Tier | Price | Features |
|------|-------|----------|
| Free | $0/month | 1 lot, manual waypoint export, community templates |
| Pro | $99/month ($999/year) | Unlimited lots, fleet management, job scheduling, satellite imagery import, priority support |
| Enterprise | Custom ($2,500+/year) | API access, white-label, SSO, custom integrations, dedicated support |

**What the platform does:**

*Lot Designer:*
- Import satellite imagery, DXF, or SVG of the parking lot
- Drop templates for standard spaces (90-degree, angled, parallel, ADA)
- Auto-generate arrows, crosswalks, stop bars, fire lanes, "NO PARKING" stencils
- Export mission waypoints file for Mission Planner / QGroundControl
- Store lot layouts for future restriping (one-click re-export)

*Fleet Management (Pro+):*
- Track multiple robots: battery status, GPS position, job progress
- Job scheduling: assign robots to lots, set dates, track completion
- Maintenance alerts: pump hours, nozzle wear, firmware updates
- Compliance reports: before/after photos, GPS accuracy logs, paint coverage

*Job Costing (Pro+):*
- Estimate paint consumption based on lot layout (linear meters x line width)
- Calculate job time based on lot size and transit distances
- Generate customer quotes directly from the platform

**Revenue assumptions:**
- Year 1: 30 paid subscribers (60% of hardware buyers convert) = $36K ARR
- Year 2: 150 paid subscribers = $180K ARR
- Year 3: 400 paid subscribers = $480K ARR
- Free tier users (DIY builders) convert at ~10% to Pro over 12 months

### 3. Consumables — Paint Cartridges, Nozzles, Parts

| Item | Price | COGS | Margin | Frequency |
|------|-------|------|--------|-----------|
| Paint cartridge (pre-filled, 1 gal, snap-in) | $45 | $20 | 56% | 4-5 per 50-space lot |
| Nozzle pack (3 tips: 4", 12", 24") | $25 | $8 | 68% | Every 50-100 lots |
| Solenoid valve replacement | $35 | $12 | 66% | Every 200-300 lots |
| Pump diaphragm kit | $30 | $10 | 67% | Every 500 hours |
| GPS antenna replacement | $45 | $18 | 60% | As needed (damage) |
| Battery pack (36V 10Ah) | $149 | $80 | 46% | Every 500-800 cycles |

**Paint cartridge economics:**
- A 50-space lot uses 4-5 gallons of traffic latex paint
- Bulk traffic paint costs $12-18/gallon
- Pre-filled snap-in cartridge: $45 retail ($20 COGS including cartridge + fill + shipping)
- Contractor alternative: buy 5-gallon bucket for $75-90, pour into reservoir, clean up
- Convenience premium is real: contractors will pay 2x for zero-mess snap-in cartridges
  the same way Keurig proved people will pay 4x for coffee pods

**Revenue assumptions (per active robot per year):**
- Paint cartridges: 200 lots/year x 4.5 cartridges x $45 = $40,500 gross
- Nozzle packs: 4x/year x $25 = $100
- Parts: ~$200/year average
- Total consumables per robot: ~$40,800 gross / ~$22,000 net

### 4. Robot-as-a-Service (RaaS)

| Plan | Price | Includes |
|------|-------|----------|
| Standard | $299/lot/year | 1 restriping/year, paint included, robot maintained by Strype |
| Premium | $499/lot/year | 2 restriping/year, paint included, priority scheduling, compliance reports |
| Enterprise | Custom | Unlimited restriping, dedicated robot, on-site storage |

**How RaaS works:**
- Strype owns the robot fleet
- Property management company subscribes per-lot
- Strype dispatches a technician + robot to the lot on schedule
- Technician sets up NTRIP, uploads mission, monitors the robot
- As automation improves, the technician manages multiple robots simultaneously
- Paint, maintenance, and insurance are Strype's cost

**RaaS unit economics (per lot, Standard plan):**
- Revenue: $299/year
- Paint cost: ~$75 (4-5 gallons bulk)
- Technician time: 1 hour at $35/hour (drive + setup + monitor)
- Robot depreciation: $5/lot (robot does 500+ lots over lifetime)
- Overhead (insurance, vehicle, scheduling): ~$30/lot
- Net margin per lot: ~$154 (52%)

**Scaling RaaS:**
- A single technician with 2 robots can do 4-6 lots per day
- 250 working days/year = 1,000-1,500 lots per tech-robot pair
- At $299/lot: $299K-$449K revenue per tech-robot pair
- Technician cost: ~$70K/year (salary + vehicle + benefits)
- Robot cost: ~$3K (2 robots, amortized)
- Paint + consumables: ~$100K/year
- Net per tech-robot pair: ~$125K-$275K/year

**Volume assumptions:**
- Year 2: 50 RaaS lots (pilot in 1 metro area)
- Year 3: 500 RaaS lots (3 metro areas)
- Year 4: 2,000 RaaS lots (10 metro areas)

### 5. Data Licensing (Future — Year 3+)

Every striping job generates structured data:
- Lot dimensions and layout (space count, angles, ADA spaces, fire lanes)
- GPS coordinates of every line
- Paint consumption and coverage rates
- Job duration and efficiency metrics
- Before/after condition (if camera system added in V2)

**Potential buyers:**
- Urban planning firms (parking utilization studies)
- Real estate analytics companies (property condition assessment)
- Insurance companies (compliance verification)
- Municipal governments (ADA compliance auditing)
- Mapping companies (parking lot geometry for autonomous vehicles)

**Revenue model:** Per-query API or annual data subscription. Pricing TBD
based on volume and data richness. Estimate: $50K-$200K/year once the
dataset reaches 10,000+ lots.

This is not a near-term revenue stream. It is a strategic option that
becomes valuable as the lot database grows.

---

## Pricing Strategy

### Hardware Pricing Rationale

| Reference Point | Price |
|-----------------|-------|
| Graco LineLazer 3400 (manual push stripper) | $1,200 |
| Graco LineLazer 5900 (manual ride-on) | $5,500 |
| Fleet Robot (autonomous, sports) | $19,000 |
| TinyMobileRobots Pro X (autonomous, sports) | $30,000+ |
| TurfTank (autonomous, sports, lease) | $61,000 + $6-16K/year |
| Strype (autonomous, parking lots) | $2,495 |

At $2,495, Strype is:
- 2x the price of a basic manual push stripper -- justified by autonomy
- Half the price of a professional manual ride-on -- and does not need an operator
- 8-12x cheaper than the cheapest autonomous competitor
- Payback period: 2-3 jobs (at $800-2,000/job revenue for the contractor)

### Platform Pricing Rationale

$99/month ($999/year) for Pro tier is positioned as:
- Less than 1 job's revenue per month
- Comparable to other trade SaaS tools (ServiceTitan is $150+/mo, Jobber is $70+/mo)
- Annual discount (16% off) incentivizes commitment and reduces churn
- Free tier drives adoption from DIY builders who may upgrade or evangelize

### Consumables Pricing Rationale

Paint cartridges at $45 (vs. $15-18/gallon bulk) carry a ~2.5x convenience
premium. This is justified by:
- Zero-mess snap-in system (no pouring, no cleanup, no measuring)
- Pre-mixed, pre-strained paint (eliminates clogged nozzles from unstrained paint)
- Guaranteed compatibility (right viscosity, right pigment load for the nozzle)
- Inventory simplification (order cartridges, not 5-gallon buckets)

The premium is in line with other consumable-lock-in models:
- Keurig K-Cups: ~4x bulk coffee price
- Printer ink cartridges: ~10x bulk ink price
- Nespresso pods: ~3x bulk espresso price
- Strype cartridges: ~2.5x bulk paint price (moderate, defensible)

### RaaS Pricing Rationale

$299/lot/year for Standard plan breaks down to:
- $0.82/day per lot -- less than a parking meter earns in an hour
- Compared to manual restriping at $800-2,000/job: 63-85% savings
- Property managers pay for predictability, not just the striping itself
- The subscription model converts a sporadic $1,500 expense into a predictable
  $25/month line item -- CFOs prefer this

---

## Unit Economics

### Hardware Sale (one-time)

```
Revenue:                   $2,495
COGS:
  Components (BOM)          $780
  Assembly labor (2 hrs)     $60
  Testing + calibration      $40
  Packaging + shipping       $80
  Warranty reserve (5%)     $125
                           ------
  Total COGS:              $1,085

Gross profit:              $1,410 (57%)
```

### Platform Subscriber (annual)

```
Revenue:                    $999/year
Costs:
  Cloud hosting (per user)   $60/year
  Support (0.5 hrs/mo)      $180/year
                            ------
  Total costs:               $240/year

Gross profit:               $759/year (76%)
```

### Consumables (per active robot, annual)

```
Revenue (paint cartridges):       $40,500
Revenue (nozzles + parts):           $300
Total revenue:                    $40,800

COGS (paint + cartridges):       $18,000
COGS (nozzles + parts):             $120
Shipping:                          $2,400
                                  ------
Total COGS:                       $20,520

Gross profit:                     $20,280 (50%)
```

Note: Consumables revenue per robot assumes a high-volume contractor doing
200 lots/year. A typical contractor doing 100 lots/year would generate about
half these numbers. Facility maintenance teams doing 10-20 lots/year generate
~$2,000-$4,000/year in consumables.

### RaaS Lot (annual)

```
Revenue:                        $299
Costs:
  Paint:                         $75
  Technician (1 hr):             $35
  Robot depreciation:             $5
  Overhead:                      $30
                                ------
  Total costs:                  $145

Gross profit:                   $154 (52%)
```

### Blended Customer Lifetime Value (3-year, contractor)

```
Year 0: Robot purchase           $1,410 gross profit
Year 1: Platform + consumables   $759 + $10,140 = $10,899
Year 2: Platform + consumables   $759 + $10,140 = $10,899
Year 3: Platform + consumables   $759 + $10,140 = $10,899
                                 ------
3-year gross profit:             $34,107

CAC assumption:                  $500 (trade show + content + sales time)
LTV:CAC ratio:                   68:1
```

This is extremely favorable. Even at 10x higher CAC ($5,000), the ratio
is still 7:1. Hardware-plus-consumables businesses have structurally
strong unit economics.

---

## Go-to-Market

### Phase 1: Open-Source Community (Months 0-6)

**Goal:** Build credibility and validate the product through community
adoption.

**Actions:**
- Publish the repo with complete build documentation (already done)
- Post build series on YouTube (time-lapse assembly, first paint test, lot job)
- Post to Reddit: r/robotics, r/ArduPilot, r/OpenSource, r/PropertyManagement,
  r/striping, r/ParkingLot
- Post to Hacker News (open-source hardware story angle)
- Submit to Hackaday.io as a project
- Engage with ArduPilot forums (contribute back any firmware improvements)
- Respond to every GitHub issue within 24 hours

**Metrics:**
- GitHub stars: target 500+ in 6 months
- DIY builders: target 10-20 confirmed builds
- YouTube views: target 50K+ across build series
- Email list signups for assembled robot waitlist: target 200+

**Cost:** ~$2,000 (video equipment, hosting, time)

### Phase 2: Hardware Sales to Contractors (Months 6-18)

**Goal:** Sell assembled robots to striping contractors who become
evangelists.

**Actions:**
- Launch Strype website with robot purchase and platform signup
- Attend 2-3 contractor trade shows per year:
  - SEALCOAT/National Pavement Expo (January, Nashville)
  - World of Asphalt (March, varies)
  - Sealcoating.com Contractor Roundtable (June)
- Run Facebook/Instagram ads targeting "parking lot striping" and
  "line striping contractor" interests
- Partner with 3-5 striping contractors for beta testing (free robot,
  feedback required, case study rights)
- Publish case studies: "Contractor X stripped 50 lots in first month
  with Strype"
- Create referral program: $250 credit per referred robot sale

**Metrics:**
- Robots sold: 50 in first 12 months
- Customer NPS: target 50+
- Reorder rate (consumables): target 80%+ of buyers ordering cartridges

**Cost:** ~$50K (trade shows, ads, beta robots, website)

### Phase 3: Platform SaaS Launch (Months 12-24)

**Goal:** Convert hardware buyers and DIY builders to recurring platform
subscribers.

**Actions:**
- Launch Strype Cloud with Free and Pro tiers
- All new robot purchases include 3-month Pro trial
- DIY builders get permanent Free tier access
- Add satellite imagery integration (Google Maps / Nearmap API)
- Add job scheduling and fleet tracking
- Add compliance reporting (before/after documentation)
- Publish integration guides for ServiceTitan, Jobber, and other
  contractor management platforms

**Metrics:**
- Platform MAU: target 200+ by month 24
- Paid conversion rate: target 30% of MAU
- Annual churn rate: target <15%

**Cost:** ~$100K (development, hosting, integrations)

### Phase 4: RaaS for Property Management (Months 18-36)

**Goal:** Launch Robot-as-a-Service in 1 metro area, prove the model,
then expand.

**Actions:**
- Select pilot metro (criteria: large number of parking lots, few striping
  contractors, mild climate for year-round operation -- candidates: Phoenix,
  Dallas, Atlanta, Orlando)
- Hire 1 technician, deploy 3 robots
- Sign 50-100 lots with 2-3 property management companies
- Build scheduling and dispatch infrastructure
- Prove unit economics at scale before expanding
- Expand to 2 additional metros in Year 3

**Metrics:**
- Lots under RaaS contract: 50 by month 24, 500 by month 36
- Customer retention: target 90%+ annual renewal
- Jobs per technician per day: target 4-6
- Net margin per lot: target 50%+

**Cost:** ~$150K (technician salary, vehicle, robots, insurance, working capital)

### Channel Strategy

| Channel | Customer Segment | Cost Per Acquisition |
|---------|-----------------|---------------------|
| Trade shows | Striping contractors | $200-500/lead |
| YouTube/content | DIY builders, early adopters | $10-50/lead |
| Reddit/HN/forums | Technical community | $0 (organic) |
| Facebook/Instagram ads | Striping contractors | $50-150/lead |
| Property management conferences | RaaS customers | $300-800/lead |
| Referral program | Existing customers | $250/sale (fixed) |
| ServiceTitan/Jobber marketplace | Contractors already using SaaS | $100-200/lead |

---

## Competitive Landscape

### Direct Competitors

| Company | Target | Price | Status | Threat Level |
|---------|--------|-------|--------|-------------|
| **10Lines** (Estonia) | Parking lots | Unknown | Pre-commercial, EUR 1.5M funded | Medium -- first mover in parking lots but EU-focused, pre-revenue |
| **CivDot** (USA) | Construction layout + striping | Quote-based | $12.5M funded, commercial | Low-Medium -- construction focus, not pure striping |

### Adjacent Competitors (Sports Fields)

| Company | Price | Annual Fee | Key Differentiator |
|---------|-------|------------|-------------------|
| **TurfTank Two** | ~$61,000 | $6-16K/year | Largest install base, brand recognition |
| **TinyMobileRobots Pro X** | ~$30-40K | Template fees | STIHL partnership, network RTK |
| **SWOZI auto** | Quote-based | RTK subscription | Fastest (7 km/h), any paint brand |
| **SWOZI Pico** | ~$11,000 | Included 1yr | Entry-level semi-auto |
| **FJD PaintMaster** | ~$160/wk rental | None | Dual GNSS, cheapest rental |
| **Fleet Robot** | ~$19,000 | ~$1,600/year | Cheapest full robot |

None of these target parking lots. All are focused on sports field marking.
Their technology is transferable to parking lots, but their go-to-market,
sales channels, and customer relationships are entirely in athletics.

### Manual Striping (the real competitor)

The primary competitor is not another robot -- it is the status quo: a
2-person crew with a push stripper.

| Factor | Manual Crew | Strype |
|--------|------------|--------|
| Cost per 50-space lot | $800-2,000 | $150-300 (consumables + technician time) |
| Time per lot | 3-4 hours | 30-60 minutes |
| Line straightness | Operator-dependent | GPS-guided, <1cm deviation |
| Availability | Seasonal labor shortage | Available 24/7, including overnight |
| Scheduling | 2-4 week lead time typical | Next-day with RaaS fleet |
| Documentation | Photos at best | GPS logs, before/after, compliance report |
| Scalability | Linear (more crew = more cost) | Sublinear (1 tech manages 2+ robots) |

The pitch to contractors is not "replace your crew" -- it is "do 3x the
jobs with the same crew." The pitch to property managers is "never chase a
striping contractor again."

### Strype Competitive Advantages

1. **10x cheaper than any autonomous competitor.** $2,495 vs $19K-$61K+.
2. **Open-source credibility.** Transparency builds trust with tradespeople.
3. **Parking lot focus.** Purpose-built for the underserved market segment.
4. **US-based.** 10Lines is in Estonia. CivDot targets construction. No US
   company sells an autonomous parking lot stripper.
5. **Network RTK eliminates base station.** The #1 customer complaint with
   competitors is base station setup. Strype uses NTRIP (network RTK) --
   no base station needed.
6. **RaaS model.** Property managers do not want to buy a robot. They want
   their lots striped. RaaS gives them what they actually want.

---

## Growth Flywheel

```
Open-source repo published
        |
        v
Community discovers project
(Reddit, HN, YouTube, Hackaday)
        |
        v
DIY builders clone repo, build robots
(free QA, free marketing, free validation)
        |
        v
Build videos + forum posts + GitHub activity
(social proof, SEO, credibility)
        |
        v
Contractors see validated product, buy assembled robots
(hardware revenue, 69% margin)
        |
        v
Contractors use Strype Cloud for lot design + fleet mgmt
(SaaS revenue, 76% margin, recurring)
        |
        v
Contractors reorder paint cartridges + nozzles
(consumables revenue, 50-68% margin, recurring)
        |
        v
Every job generates lot layout data
(dimensions, GPS coordinates, paint consumption)
        |
        v
Data improves platform (better templates, estimates, optimization)
        |
        v
Better platform attracts more users
        |
        v
More users generate more data
        |
        v
[FLYWHEEL ACCELERATES]
        |
        v
Property managers see contractors using Strype, want RaaS
        |
        v
Strype deploys owned fleet for RaaS
(highest-margin recurring revenue)
        |
        v
RaaS fleet generates massive data volume
        |
        v
Data licensing becomes viable
(urban planning, real estate, insurance, AV companies)
```

**Key insight:** The open-source repo is not the product. It is the top of
the funnel. Every layer above it adds margin, stickiness, and defensibility.

---

## Key Metrics

### North Star Metric
**Lots striped per month** (across all revenue streams -- hardware customers,
platform users, and RaaS fleet). This measures real-world adoption regardless
of how the customer pays.

### Hardware Metrics
| Metric | Target (Year 1) | Target (Year 3) |
|--------|-----------------|-----------------|
| Robots sold / month | 4 | 40 |
| Hardware gross margin | 57% | 60% (BOM cost reduction at volume) |
| Customer acquisition cost (CAC) | $500 | $300 |
| Robot MTBF (mean time between failures) | 200 hours | 500 hours |

### Platform Metrics
| Metric | Target (Year 1) | Target (Year 3) |
|--------|-----------------|-----------------|
| Monthly active users (MAU) | 50 | 500 |
| Paid subscribers | 30 | 400 |
| Lots created in platform | 500 | 10,000 |
| Missions exported / month | 200 | 5,000 |
| Annual churn rate | <20% | <10% |

### Consumables Metrics
| Metric | Target (Year 1) | Target (Year 3) |
|--------|-----------------|-----------------|
| Paint cartridge reorder rate | 70% of robot owners | 85% |
| Average cartridges per customer per month | 15 | 20 |
| Nozzle pack reorder rate | 60% | 80% |

### RaaS Metrics
| Metric | Target (Year 2) | Target (Year 3) |
|--------|-----------------|-----------------|
| Lots under contract | 50 | 500 |
| Annual renewal rate | 85% | 92% |
| Jobs per technician per day | 4 | 6 |
| Net margin per lot | 45% | 55% |

### Community Metrics
| Metric | Target (Year 1) | Target (Year 3) |
|--------|-----------------|-----------------|
| GitHub stars | 500 | 3,000 |
| Confirmed DIY builds | 20 | 200 |
| YouTube build video views | 50K | 500K |
| Community contributors | 5 | 30 |

---

## Risk Analysis

### Technical Risks

**1. GPS multipath near buildings (HIGH)**
Parking lots are next to buildings. Buildings reflect GPS signals, causing
multipath errors of 10-50cm -- enough to make lines visibly crooked.

*Mitigation:*
- UM980 triband (L1/L2/L5) provides better multipath rejection than
  dual-band (L1/L2) -- L5 signal is specifically designed for multipath
- ArduPilot's GSF heading filter fuses GPS with accelerometer to smooth
  position jumps
- Operational guidance: stripe rows furthest from buildings first (best
  sky view), work toward buildings last
- V2: add IMU dead-reckoning to bridge GPS gaps near tall structures
- V2: downward camera for line-following during restriping (existing lines
  as ground truth, immune to multipath)

**2. Paint system reliability (MEDIUM)**
Nozzle clogging, solenoid sticking, pump cavitation, paint drying in lines.

*Mitigation:*
- Pre-strained paint in cartridges eliminates #1 clog source
- 60-mesh inline strainer as backup filtration
- Flush system (water cartridge) for end-of-job cleanup
- Direct-acting solenoid (not pilot-operated) for reliable low-pressure operation
- Shurflo 8000 pump is proven in agricultural sprayers (millions deployed)
- See `docs/failure_modes.md` and `docs/troubleshooting.md` for complete
  failure mode analysis

**3. Hoverboard motor sourcing (MEDIUM)**
Compatible hoverboards (STM32F103R or GD32F103R chip, Gen1 single-board)
are becoming harder to find as the used market shifts to newer AT32-based
boards.

*Mitigation:*
- Build inventory: buy 50-100 compatible boards when found ($30 each = $1,500-$3,000)
- Develop relationships with e-waste recyclers who see volume
- V2: design custom motor driver PCB that eliminates hoverboard dependency
  (RP2040 + dual DRV8301 gate drivers, ~$40 BOM, but requires 3-6 months
  of development)
- V2 alternative: switch to RoboClaw 2x15A ($120) + generic BLDC motors ($60),
  which increases BOM by ~$150 but eliminates sourcing risk entirely

### Business Risks

**4. Liability for autonomous operation on private property (HIGH)**
A robot operating in a parking lot could hit a parked car, a person, or
cause property damage.

*Mitigation:*
- Geofencing: robot cannot leave the defined work area (ArduRover FENCE built-in)
- E-stop: hardware kill switch cuts motor power immediately
- Obstacle detection: HC-SR04 ultrasonic sensors trigger emergency stop
- Operational protocol: technician or operator must be present and monitoring
  (robot is not fully unattended -- it is a tool the operator supervises)
- Insurance: obtain robotics liability insurance (specialist brokers exist:
  Munich Re, Marsh, Berkley Technology)
- Terms of service: clear liability allocation for property damage
- RaaS model: Strype carries the insurance, not the customer

**5. Competitor with deeper pockets enters parking lots (MEDIUM)**
TurfTank ($90M+ revenue) or TinyMobileRobots (STIHL-backed) could pivot
from sports fields to parking lots.

*Mitigation:*
- First mover advantage in parking lot GTM (different channels, different
  customers, different pricing)
- Open-source community moat: goodwill and credibility that funded competitors
  cannot buy
- 10x cheaper price point: even if they enter, they cannot match $2,495
  with their cost structure ($30K+ robots)
- RaaS relationships: contracted lots are sticky (90%+ renewal target)
- Speed: move fast on consumables lock-in and data flywheel before they arrive

**6. Hardware margin pressure (MEDIUM)**
Component costs may increase, or competitors may force price reductions.

*Mitigation:*
- Hardware is the entry point, not the margin driver. Shift revenue mix
  toward SaaS and consumables over time.
- Target revenue mix by Year 3: 30% hardware, 25% platform, 30% consumables,
  15% RaaS
- Volume purchasing: BOM cost drops 10-15% at 100+ unit volume
  (connectors, wire, extrusion in bulk)
- Vertical integration: custom PCB for motor driver reduces BOM and
  eliminates hoverboard dependency

**7. Regulatory changes for autonomous vehicles on private property (LOW)**
Most US jurisdictions do not regulate autonomous operation on private
property (parking lots are private). This could change.

*Mitigation:*
- Strype operates on private property only (not public roads)
- Robot is low-speed (<2 m/s), low-mass (~50 kg), and supervised by
  an operator
- Proactively engage with insurance industry to establish standards
- Document safety record (incidents per 1,000 operating hours)

### Market Risks

**8. Contractors resist automation (MEDIUM)**
Some striping contractors may see the robot as a threat to their business
rather than a tool to grow it.

*Mitigation:*
- Position as "do 3x the jobs" not "replace your crew"
- Target contractors who are already capacity-constrained (backlogged jobs)
- Case studies showing revenue increase, not labor replacement
- Start with early adopters (tech-forward contractors), not laggards

**9. Property managers unwilling to pay RaaS premium over manual (LOW-MEDIUM)**
Property managers may prefer the devil they know (manual contractor) over
a new service model.

*Mitigation:*
- Lead with documentation and compliance (something manual contractors
  cannot easily provide)
- Emphasize scheduling reliability ("your lot is striped on May 15 at 3 AM,
  guaranteed" vs. "your contractor will get to it sometime next month")
- Offer first-lot-free trial to prove quality
- Start with property managers who manage 50+ lots (they feel the pain of
  vendor management most acutely)

---

## Financial Projections

### Year 1 (Conservative)

| Revenue Stream | Units | Revenue | Gross Profit |
|---------------|-------|---------|-------------|
| Hardware sales | 50 robots | $124,750 | $70,500 |
| Platform SaaS | 30 subscribers | $29,970 | $22,770 |
| Consumables | 30 active robots | $122,400 | $61,200 |
| RaaS | 0 lots | $0 | $0 |
| **Total** | | **$277,120** | **$154,470** |

*Operating expenses:*
- Engineering (2 FTE): $200K
- Sales/marketing: $50K
- Cloud infrastructure: $12K
- Trade shows (2): $15K
- Insurance/legal: $20K
- Total opex: $297K
- **Year 1 net: -$143K (pre-revenue investment period)**

### Year 2

| Revenue Stream | Units | Revenue | Gross Profit |
|---------------|-------|---------|-------------|
| Hardware sales | 200 robots | $499,000 | $282,000 |
| Platform SaaS | 150 subscribers | $149,850 | $113,850 |
| Consumables | 150 active robots | $612,000 | $306,000 |
| RaaS | 50 lots | $14,950 | $7,700 |
| **Total** | | **$1,275,800** | **$709,550** |

*Operating expenses:*
- Engineering (3 FTE): $300K
- Sales/marketing: $100K
- Cloud infrastructure: $36K
- Trade shows (3): $25K
- RaaS operations (1 tech, 3 robots): $80K
- Insurance/legal: $30K
- Total opex: $571K
- **Year 2 net: +$139K (break-even)**

### Year 3

| Revenue Stream | Units | Revenue | Gross Profit |
|---------------|-------|---------|-------------|
| Hardware sales | 500 robots | $1,247,500 | $705,000 |
| Platform SaaS | 400 subscribers | $399,600 | $303,696 |
| Consumables | 400 active robots | $1,632,000 | $816,000 |
| RaaS | 500 lots | $149,500 | $77,000 |
| **Total** | | **$3,428,600** | **$1,901,696** |

*Operating expenses:*
- Engineering (5 FTE): $500K
- Sales/marketing: $200K
- Cloud infrastructure: $80K
- Trade shows (4): $40K
- RaaS operations (3 techs, 10 robots): $250K
- Insurance/legal: $50K
- G&A: $80K
- Total opex: $1,200K
- **Year 3 net: +$702K**

### Revenue Mix Shift

| Year | Hardware | Platform | Consumables | RaaS |
|------|----------|----------|-------------|------|
| 1 | 45% | 11% | 44% | 0% |
| 2 | 39% | 12% | 48% | 1% |
| 3 | 36% | 12% | 48% | 4% |

Consumables become the dominant revenue stream by Year 1 and stay there.
This is the target: the robot is the razor, the cartridges are the blades.

---

## Technical Moat Details

### What the Assembled Robot Includes (vs. DIY)

| Aspect | DIY from Repo | Assembled Strype |
|--------|--------------|-----------------|
| Hoverboard sourcing | Find compatible board yourself (many are AT32, incompatible) | Pre-verified STM32F103R board, tested |
| FOC firmware flash | Install STM32CubeIDE, build from source, flash via ST-Link | Pre-flashed, configured for differential drive |
| Frame | Build from 2020 extrusion + plywood, cut/drill/assemble | Precision-cut aluminum frame, powder-coated, pre-drilled |
| Wiring | Follow wiring guide, solder, crimp, heat shrink | Pre-wired harness with labeled connectors |
| Pixhawk setup | Flash ArduRover, load params, configure serial ports | Pre-loaded firmware + params + Lua scripts |
| PID tuning | Iterative field testing (oscillation, overshoot, convergence) | Pre-tuned for standard frame geometry |
| GPS configuration | Configure UM980 baud rate, NMEA output, verify fix | Pre-configured, antenna pre-mounted with ground plane |
| Paint system | Source pump, solenoid, nozzle, tubing, fittings, assemble | Integrated paint module with snap-in cartridge port |
| Calibration | Accel, compass, RC, battery voltage -- each takes 10-30 min | Factory calibrated, verified with test mission |
| Documentation | Read docs, interpret, troubleshoot | Phone onboarding + video library + priority support |
| Total time | 20-25 hours over 2 weekends | Unbox, connect NTRIP, run first job (30 minutes) |

### Snap-In Paint Cartridge System (proprietary)

The paint cartridge system is the primary physical consumables lock-in:
- Standard 1-gallon HDPE cartridge with proprietary quick-connect fitting
- Pre-filled with traffic latex paint, pre-strained through 60-mesh filter
- Snap into the robot's paint bay -- no pouring, no measuring, no cleanup
- Color-coded caps: white, yellow, blue (handicap), red (fire lane)
- RFID tag (future) for automatic paint level tracking and reorder alerts

The quick-connect fitting is the lock-in mechanism. It is not a standard
NPT or barb fitting. Third-party refills are possible but messy and void
the paint system warranty. This is the printer-ink model applied to paint.

**Design consideration:** The cartridge system must be good enough that
contractors *want* to use it, not just locked into it. If refilling a
standard reservoir is easy and the cartridge is seen as a ripoff, contractors
will route around it. The cartridge must genuinely save time and mess.
Target: 30 seconds to swap a cartridge vs. 5 minutes to pour/clean a
reservoir. That time savings is worth $45 to a contractor billing $150/hour.

---

## Appendix: Reference Documents

All technical documentation is in the `docs/` directory:

| Document | Path | Description |
|----------|------|-------------|
| Bill of Materials | `docs/bom.md` | Three-tier BOM ($424/$780/$1,050) with sourcing links |
| Wiring Guide | `docs/wiring_guide.md` | Complete electrical wiring diagrams and pin assignments |
| Quick Start Guide | `docs/quick_start.md` | Step-by-step build and first-job instructions |
| Failure Modes | `docs/failure_modes.md` | FMEA analysis of all subsystems |
| Troubleshooting | `docs/troubleshooting.md` | Symptom-based troubleshooting guide |
| Maintenance | `docs/maintenance.md` | Preventive maintenance schedules and procedures |
| Research Report | `docs/research_report.md` | Competitive analysis and architecture recommendations |
| Overengineering Analysis | `docs/overengineering_analysis.md` | Why ROS2 was replaced with ArduRover |
| ArduRover Setup | `ardurover/README.md` | Pixhawk configuration, Lua scripts, calibration |

### Key Technical Parameters

- Robot COGS: $780 (Tier 2 BOM)
- GPS accuracy: 8mm RTK (UM980 triband L1/L2/L5)
- Drive system: hoverboard BLDC hub motors, 700W total, differential drive
- Paint system: Shurflo 8000 pump + direct-acting solenoid + TeeJet TP8004EVS nozzle
- Runtime: 45-70 minutes on 36V 10Ah e-bike battery
- Weight: ~50 kg with full paint
- Speed: 0.5 m/s painting, 1.0 m/s transit
- Firmware: ArduRover 4.5+ with ~30 lines custom Lua
- Path generation: striper_pathgen Python library (173 tests)
