# How a slope/landslide problem is reported, routed and dispatched in Nepal
### Verified evidence base, 2026-09-30

Scope: whether a new software output would fit the real workflow, or be ignored.
Method: primary documents fetched and read (JICA final report, DRRM Act 2074 English, BIPAD
role handbooks, OPML assessments, Practical Action threshold report), plus first-hand probing of
BIPAD's public API and GeoServer. Every claim is tagged **VERIFIED** (I fetched it and saw it),
**REPORTED** (a source claims it) or **UNVERIFIED / COULD NOT CONFIRM**.

---

## 1. THE REAL CHAIN, end to end

```text
  LANDSLIDE / CRACK / SUBSIDENCE OBSERVED ON OR NEAR A ROAD
                    |
        (a) citizen / ward / passer-by notices
                    |
                    v
  +---------------------------------------------------------------+
  | NEPAL POLICE  = FIRST RESPONDER  and the ONLY routine          |
  | creator of an incident record                                  |
  |   "Incident forms are filled by Nepal Police as the first       |
  |    responders to any incidents."                               |
  |   Police hold "Authority to fill the 'Incident Reporting Form'" |
  |   and "Authority to add, edit and delete the loss data"         |
  +---------------------------------------------------------------+
                    |  BIPAD incident created
                    |  fields: title, wards[], point(lat/lon), incidentOn,
                    |  reportedOn, source, hazard(17=Landslide), verified,
                    |  approved, loss, dataSource
                    v
  +---------------------------------------------------------------+
  | BIPAD VERIFIER role  (separate group from the inputters)        |
  |   "can verify the incident in case no discrepancies are found"  |
  +---------------------------------------------------------------+
                    |
                    v
  +---------------------------------------------------------------+
  | MUNICIPALITY / RURAL MUNICIPALITY  --- READ + COMMENT ONLY      |
  |   "Municipalities have access to view the incident reporting     |
  |    form and can add a comment to notify the stakeholders if the  |
  |    data is incomplete or needs to be re-checked."               |
  |   Permission C1 = Comment: "Can comment / verify."              |
  |   May also: maintain the local disaster database, the DMC        |
  |   contact list (local/ward/community), inventory, relief funds   |
  +---------------------------------------------------------------+
                    |
                    v   *** THE ROAD BRANCH: the actual repair path ***
  +---------------------------------------------------------------+
  | DoR DIVISION ROAD OFFICE (DRO)  -- performs EMERGENCY MAINTENANCE|
  |   "DROs perform emergency maintenance when a road blockage       |
  |    occurs due to a road geohazard. They are responsible for      |
  |    submitting a ROAD BLOCKAGE REPORT to the central office of    |
  |    DOR. Based on this report, the DOR Maintenance Office updates |
  |    the database regarding sites (highway names, distance         |
  |    markers), geohazard types, and road closure times."           |
  |   Physical work: DOR permanent staff + Mechanical Branch heavy   |
  |   equipment, or outsourced. Removal of debris, warning signs,    |
  |   diversion roads, covering cracks, river-erosion protection.    |
  +---------------------------------------------------------------+
                    |
        +-----------+-----------+
        | DRO can handle it?    |
        |                       |
   YES  |                       |  NO  --> request to GESU for
        v                       v          investigation + design
   work done                +--------------------------------------+
   (recorded in              | GESU (Geo-Environmental & Social Unit)|
   BIPAD road-blockage       | "orders survey and design work at the |
   register; see §6)         |  request of DRO"                     |
                             +--------------------------------------+
                                        |
                              difficulty scale (JICA Table 5-1):
                              Easy     = DRO can do it with advice
                              Moderate = GESU support required
                              Difficult= needs Japan/international support
                                        |
                                        v
                             FUNDING: Road Board Nepal (RBN, est. 2002)
                             financed by fuel tax + vehicle registration
                             tax + road user fees; allocates to DoR (NHs)
                             and local roads, inside the Integrated Annual
                             Road Maintenance Plan (IARMP / ARMP)
```

**Who pays — VERIFIED (JICA final report, ch. 3):**
- Road Board Nepal allocates the maintenance budget. FY2022/23 allocated **NRs 63.3 billion against a demand of NRs 93.0 billion — a ~32% gap.**
- When RBN under-allocates, DoR cuts **Recurrent, Periodic, Specific/Preventive and Rehabilitation** works. **Routine and Emergency maintenance are protected** (fixed staff/equipment cost).
- This is the crux: *Specific/preventive maintenance is the budget line that actually builds slope protection, and it is the first thing cut.*
- 40% of 216 surveyed collapse sites had any engineering measures at all.

**Who is the lead agency — VERIFIED (JICA):** "The agency with central responsibility for landslide management is **NDRRMA**. The implementing agencies for landslide management projects are **DWRI** and **DOFSC**, and **DoR for road landslides**."

**Staffing reality — VERIFIED (JICA):** NDRRMA HQ = 39 staff. DHM Flood Forecasting Division = **4 staff**. DWRI Landslide Management Section = **3 staff**. DOFSC Landslide Hazard Management Section = 5 staff. DMG Landslide Research Section = **2 staff**, and it has not produced provincial landslide risk maps for lack of a ~NRs 10 million budget.

**The recording instrument — VERIFIED (BIPAD API, first-hand):** the incident is recorded in BIPAD (see §5). Nepal Police-sourced records carry `source: nepal_police` / `dataSource: drr_api`.

**The road-specific dispatch record — VERIFIED (BIPAD API, first-hand):** BIPAD now carries a
`highway` road-blockage register — 398 records, of which **307 (77%) list `closureReason:
"Landslide"`**, each carrying the DoR `division`, `chainage`, `repairEta`, `actualRepairTime`,
`contactPerson` and `effortsBeingMade`. See §6 — this is the closest thing to a work order that exists publicly.

---

## 2. DoR / GESU: the "slope site inspection" app

**Status: the app EXISTS, and is DORMANT. It has never held a single record.**

Source: JICA *Data Collection Survey on Road Disaster Prevention in Nepal*, Final Report,
`https://openjicareport.jica.go.jp/pdf/12384491_01.pdf` (288 pp.; §3.2.10 p.68–69 and §14.1.2/§14.2.4 p.213+).

VERIFIED quotations:
- "**DOR's GESU developed an input application for smartphones and computers**, the following
  site-specific inspection format used by DRO, specified in DOR's road geohazard risk management
  guideline, 'Roadside Geotechnical Problems: A Practical Guide to Their Solution, June 2007.'
  **The app was developed using the DOR budget and outsourced to a Nepalese information system company.**"
- Purpose: "to inspect sites with landslide problems and determine whether they can be dealt with
  simple non-structural and structural measures and whether it is necessary to plan full-scale structural measures."
- Forms implemented: **A1 Site Definition, A2 Slope Problems, A3 Erosion Problems** (each a Data
  Sheet + Decisions [+ Actions]). **A4 Pavement Problems and A5 Structural Problems** are "planned to be developed in the future."
- Workflow: "**DRO staff inspect landslide risk sites by the format and the superior engineer approves the inspection result.**"
- **Operational status, as of February 2024:** "the app is currently dealing with minor issues, and
  **no data has been entered, and no paper-based data has been collected.**"
- "**The format has not been used since the Guide was published in 2007.**"
- "As of February 2024, DOR cannot start using the app because **there is no personnel to perform
  inspections or data input, and there is no budget**, so it is necessary to train the person of DOR mainly DRO.
  DOR has a department in charge of staff training, but **there is no budget for road landslide inspection training**, so DOR is hoping for support from JICA."
- Limitation: "The app **cannot digitize sketches recorded on paper**."
- Usability: "the current system... **carries too many data items, which requires a long time for data entry**.
  For the sustainable utilization of the system, **simplification of the system may also be necessary.**"
- Context: "since the guide was established in 2007, it has not been used in practice, and **most DRO staff members are unaware of its existence.**"

**What I could NOT verify:**
- **The app's name.** The JICA report never names it. No product name is given anywhere in the document.
- **The vendor.** "a Nepalese information system company" — unnamed. (Note: adjacent DoR systems are
  hosted by `softavi.com` — BMS bridge register and EIS — and `softwel.com.np` — BSM. Suggestive, not evidence.)
- **Current operational status.** The last verified statement is February 2024 — **~2.5 years stale** as of
  this writing. DoR may have progressed. I found **no** public documentation, release note, or
  procurement record for this app.
- **Whether it accepts external inputs.** No evidence. It is designed for authenticated DRO staff, and given zero records exist, the question is moot.

**Consequence for the project's risk register:** the risk "DoR's GESU may already have a smartphone
slope-inspection app" resolves to **the app exists but has processed zero records in ~2.5 years.**
The claim "no *operational* prioritised inspection workflow exists" is defensible. The claim
"no app exists" would be **false and must never be made.**

---

## 3. Municipality / ward legal responsibility and the escalation ladder

**DRRM Act 2074 (2017)** — VERIFIED from the official English text/regulation booklet
(`https://faolex.fao.org/docs/pdf/NEP228597.pdf`):

| Body | Section | Chair | Notes |
|---|---|---|---|
| National Council for DRR&M | s.3 | **Prime Minister** | members incl. all Chief Ministers, Chief Secretary, CoAS |
| Executive Committee | s.6 | — | |
| **NDRRMA** (the Authority) | s.10–11 | — | s.11(c) study/research on **landslide**; s.11(k) "**Collect, analyze, store and disseminate information and data on disaster management**" |
| Provincial Disaster Management Committee | s.14 | Interior Minister (per 1st amendment) | s.14(2)(r) **recommends to Government of Nepal** that a disaster-threatening situation be declared |
| **District Disaster Management Committee (DDMC)** | s.16 | **Chief District Officer (CDO)** | members include chairs/chiefs of *all* local levels in the district, security agency chiefs, Red Cross, NGO Federation, journalists, chamber of commerce |
| **Local Disaster Management Committee (LDMC)** | s.17 | **Mayor / Chairperson of the municipality or rural municipality** | max 15 members; "Every local level shall establish" |

**LDMC statutory functions — VERIFIED (s.17(2)), the ones that matter here:**
- (f) "**Constitute a disaster preparedness and response committee at the communities or ward levels** to raise awareness on disasters, formulate disaster related plans and programs, and mobilize for an immediate response after disasters"
- (j) "**Develop or cause to develop an information system on disaster management and early-warning system at local level, and make them operational**"
- (k) "Establish and run Emergency Operations Centers at local level"
- (m) "Identify the number of affected households by a disaster, determine the level of loss and damage, and issue the identity cards"

**KEY POINT:** the **ward** has no independent statutory disaster body. The ward-level committee is
*constituted by the municipal LDMC* under s.17(2)(f). A tool that addresses "the ward" is addressing
a body that exists only if the municipality created it.

**Escalation ladder — VERIFIED:**
```text
WARD / COMMUNITY committee   (constituted by municipal LDMC, DRRM Act s.17(2)(f))
      |                          -- not a statutory body in its own right
      v
MUNICIPALITY / RURAL MUNICIPALITY  -- Local Disaster Management Committee
      |   chaired by Mayor/Chairperson  (DRRM Act s.17)
      v
DISTRICT  -- District Disaster Management Committee
      |   chaired by the Chief District Officer  (DRRM Act s.16)
      v
PROVINCE  -- Provincial Disaster Management Committee
      |   chaired by the Interior Minister  (DRRM Act s.14)
      v
FEDERAL  -- National Council (PM, s.3) + NDRRMA (s.10-11)
             DECLARATION of a "Disaster Threatening Area" is made ONLY by
             the Government of Nepal by Gazette notification  (DRRM Act
             s.32) -- typically on provincial recommendation (s.14(2)(r)).
             s.32(3): the notice "shall be published and broadcasted by the
             national mass media."
```

**LGOA 2074 (2017)** — the Local Government Operation Act. **OPML's tabulation** of the LGOA duties
(VERIFIED as OPML's text; *not* the statute verbatim) assigns local government:
- "Local level disaster preparedness and response plan, **early warning systems**, search and rescue,
  pre-stocking of relief materials, coordination and distribution of relief materials"
- "**Flood and landslide risk mitigation, flood plain management and land use management**"
- "Assessment and mapping of risk and vulnerability"
- "Local level disaster related data collection, research and innovation"
- "Local level emergency operation"

**COULD NOT VERIFY: the verbatim LGOA 2074 schedule / s.11–s.12 duty lists.** I could not retrieve a
working copy of the Act (lawcommission.gov.np returned HTML; municipal mirrors 404'd or connection-failed).
What I have is OPML's summary table, not the statutory text. **Do not quote LGOA item numbers until the statute is obtained.**

**Documented institutional weakness — VERIFIED (OPML, *Delineation of DRRM Roles and
Responsibilities*, p.34):** "**over 90% of Palikas have formed local DRRM committees, whereas 60% of
local governments have ward-level DRRM committees. However, the overall capacity of these committees
**remains inadequate, and there is no strategy to strengthen their capacity**." Also: "local government
themselves do not have an HR roster for DRRM"; "There are limited human resources to undertake
immediate needs assessments after hazard strikes, such as the IRA and MIRA."

---

## 4. Warning issuance and how a warning physically reaches a ward chair

**Who issues — VERIFIED:** DHM (Department of Hydrology and Meteorology) is the authorised
agency for hydrology/meteorology; DHM and DWRI are the relevant departments for water and
**landslides** under MoEWRI (JICA). DHM's Forecasting Division is very small — **4 staff**.

**The thresholds — VERIFIED (Practical Action / DPNet report,**
`https://www.dpnet.org.np/uploads/files/Final_report_of_Helambu_and_panchpokhari_thangpal0502%202026-01-20%2007-48-55.pdf`):
- Practical Action Nepal, with DHM and DMG support, developed **rainfall intensity–duration
  thresholds for landslides in Helambu and Panchpokhari Thangpal Rural Municipalities,
  Sindhupalchok district**, from historical rainfall and mapped landslide inventories.
- The stated purpose is explicitly to be integrated: "**Integrating these limits into the DHM's
  forecasting system will allow for the prompt and effective transmission of landslide warnings.**"
- The work engaged the real local bodies: "**Ward Disaster Management Committees (WDMCs), ward
  chairpersons, Community Disaster Management Committees (CDMCs)**, and community members" — this is the
  field-verified confirmation that ward-level committees and ward chairs are the last-mile actors.
- The report's own output (d) is "generate evidence for LEWS policy advocacy" — i.e. **advocacy, not a live service.**
- It calls for "**LEWS generated from DHM with clear and concise roles and responsibilities**" — an
  implicit admission that the roles are not currently clear.

**THE ACTUAL DISSEMINATION MECHANISM — VERIFIED (JICA final report, §3.3.1):**
> "Supported the establishment of a **geohazard early warning unit under the National Emergency
> Operation Center of NDRRMA**. The **Geohazard early warning unit disseminates landslide warning
> information via social media such as SMS, TV, etc.**"

This is the operational answer, and it is decisive for the design brief:

- The issuing/dispatching body for **landslide** warnings is the **Geohazard Early Warning Unit
  under the NEOC at NDRRMA** — *not DHM directly*.
- The channel is **broadcast (SMS / TV / social media)**, i.e. **one-to-many and unaddressed**.
  There is **no evidence of a targeted, named-recipient dispatch** to a specific ward chair or a
  specific road engineer.

**Documented weakness — VERIFIED (OPML, BIPAD Realtime module critique):**
> "The real-time module should include features to overlay information on hazard maps to aid in early
> warning systems. For example, **the Rain Watch information from DHM could be used along with the
> landslide susceptibility data to inform about possible rainfall-induced landslides.**"

Written in December 2020, this is *precisely* the function a detection→dispatch tool would perform.
I found **no evidence it has been implemented** — but I also **could not verify that it has not been**.

**COULD NOT VERIFY (be blunt with the user about this):**
- DHM's or NEOC's **actual recipient list** — nothing public shows whether ward chairs or DRO
  engineers are on it.
- The **SMS gateway / aggregator** and whether it is a government or telecom-operated system.
- Whether **CAP (Common Alerting Protocol)** is implemented.
- Whether the Practical Action thresholds are **loaded in DHM's operational system as of Sep 2026**.
  The report describes the integration as the *next* step; I could not confirm it happened.
- A **reported but unverified** claim: the NCDRR 2025 proceedings snippet states "**The DASTA system,
  using IVR, proved more effective, as calls were more likely to be answered than messages read.**"
  I could **not** fetch that document (server returned a 300-byte block), so treat it as a lead only.
  If true, it is a strong argument for **voice/IVR over SMS** in the last mile.

---

## 5. BIPAD portal: what it is, who enters, and what can be integrated

**What it is — VERIFIED (OPML, Dec 2020):** BIPAD = **Building Information Platform Against
Disaster**, the Disaster Information Management System (DIMS) portal, launched by the **Ministry of
Home Affairs + NDRRMA**, developed by **Youth Innovation Labs**. Endpoints: `bipad.gov.np`,
`bipadportal.gov.np`. OPML's summary judgement: "In its current state, the BIPAD portal **does not
support data processing for risk analysis but is limited to compiling multiple disaster datasets and
supporting visualizing risk information.**"

**Who enters what — VERIFIED (role handbooks published via `https://bipadportal.gov.np/api/v1/manual/`):**
there is a separate *Technical Handbook* per role: Super Admin, National Ministries, Provincial
Ministries, Districts, **Municipalities/Rural Municipalities**, and **Nepal Police**.
- **Nepal Police:** "As the first responders to incidents, Nepal Police holds a huge responsibility to
  collect and maintain credible database of the incidents." Permissions: "**Authority to fill the
  'Incident Reporting Form'**", "Authority to add, edit and delete the loss data", "Authority to assign sub-logins".
  User groups: "**Nepal Police (main task is to input incidents), Verifier (verify the incidents)**".
  "Only the officials who are assigned to input the data in the incident reporting form will have
  access to add, edit and delete the incident form data. Officials assigned to verify... can verify
  the incident in case no discrepancies are found."
  Incident form fields include: `Source` (default Nepal Police), `Incident On`, `Reported On*`, `Phone number`, `Verified`, `Verification Message`.
- **Municipality/Rural Municipality:** "have the responsibility to maintain a **credible disaster
  database**"; authority to add/edit/delete *documents, DMC contact information at local, ward and
  community level, inventory, relief funds, DRR project data*; and "**Authority to comment on the
  incident reporting form if the data are incomplete or incorrect**" (permission code **C1 = Comment**,
  "Can comment / verify"). **They do not create incident records.**
- **Ward level:** no separate BIPAD role handbook exists. Wards appear as data (`wards: [id]`,
  `ward` FK) and in the DMC contact list maintained by the municipality.

**APIs and exports — VERIFIED FIRST-HAND (this is the key finding for tooling):**

A **fully open, unauthenticated REST API** exists at `https://bipadportal.gov.np/api/v1/` — a DRF
API root listing **~150 endpoint families**. Confirmed live (HTTP 200 + JSON) include:

| Endpoint | What it is |
|---|---|
| `incident/` | the incident register; filterable, e.g. `?hazard=17` (Landslide), `?hazard=29` (Soil Erosion) |
| **`highway/`** | **the road-blockage / dispatch register — see §6** |
| **`citizen-report/`** | **public citizen intake (POST-able)** |
| `loss/`, `loss-people/`, `loss-infrastructure/`, `loss-family/`, `loss-livestock/`, `loss-agriculture/` | damage & loss |
| `hazard/` | hazard taxonomy (id 17 = **Landslide / पहिरो**, type "natural") |
| `ward/`, `municipality/`, `district/`, `province/`, `ward-information/` | administrative units |
| `layer/`, `layer-group/`, `geoserver-filter/` | hazard/risk GIS layer catalogue |
| `manual/`, `document/`, `situation-report/`, `bipad-bulletin/`, `alert/` | publications & bulletins |
| `rain/`, `river-stations/`, `weather/`, `flood-station/`, `earthquake/` | real-time feeds |
| `citizen-report/`, `incident-feedback/`, `feedback/`, `priority-action/` | intake & follow-up |

**Hazard/risk-info layer — VERIFIED FIRST-HAND, and this is a genuine integration surface:**
- `https://bipadportal.gov.np/geoserver/wms?service=WMS&request=GetCapabilities` returns **2.1 MB XML advertising 2,610 layers.**
- The `Bipad` workspace has its own capabilities endpoint. A **WFS `GetFeature` request succeeded**,
  returning GeoJSON from `Bipad:durham_landslide_hazard_risk_ward` with per-ward attributes
  (`district`, `municipality`, ward number, area, centroid) — i.e. **ward-level landslide hazard AND
  risk can be pulled as data, not just viewed as a picture.**
- The catalogue exposes **274 public layers** (all `public: true`), 256 of them category `hazard`.
  Landslide-relevant layers include:
  - `durham_susceptibility` — **"National Landslide Susceptibility"** (raster)
  - `durham_landslide_hazard_risk_ward` / `_municipality` / `_district` — **ward / municipality / district landslide hazard** (vector)
  - `durham_landslide_hazard_risk_*` under category `risk` — **ward-level Landslide Risk**
  - `Meteor_susceptibility_rainfall` (rainfall-triggered), `Meteor_susceptibility_seismic`
  - **`panchpokhari_durham_landslide_susceptibility`**, `Melamchi_landslide_hazard_zonation`,
    `barhabise_durham_susceptibility`, `bhotekoshi_durham_susceptibility`, `jugal_...`
  - per-year landslide **density + polygons 2014–2020**, far-western inventory 2003–2017,
    `ERAKV_EQ_Induced_SlopeFaliure_susceptability` (Kathmandu Valley, earthquake-induced)

  This is the Kincey et al. 2023 national rainfall-triggered susceptibility dataset, served
  operationally through BIPAD. **A third-party tool can join a slope coordinate → ward → hazard/risk class
  → named municipality, over a public OGC interface, today, with no agreement.**

**Is the citizen intake open-write? — VERIFIED:** an unauthenticated `POST` to `citizen-report/` with
an empty body returned **HTTP 400 with field-validation errors** (`{"hazard":["This field is required."],"ward":["This field is required."]}`),
**not 401/403**. DRF evaluates permissions before validation, so this indicates the intake is
**world-writable**. I sent only an empty body and **created no record** (verified: first id still 2).

**MY OWN DATA-QUALITY AUDIT OF BIPAD (Sep 2026) — this is the most damaging finding:**
- The `citizen-report` table holds **at least 7,081 rows** (I paginated to 7,082; the API's `count`
  field is **broken** — it returns `9223372036854775807`, int64 max — so no total can be trusted).
- Of those 7,081 rows: **0 are `verified: true`. Only 6 are linked to an incident** (`incident` FK).
- **323 rows are unmistakable SQL-injection probe strings** — e.g.
  `-1 OR 3+886-886-1=0+0+0+1 --`, `1*if(now()=syscall(),sleep(15),0)`,
  `10'XOR(1*if(now()=syscall(),sleep(15),0))XOR'Z` — **3,293 of them concentrated on a single ward (3302)**.
  An automated scanner hit the intake and **the payloads were persisted and never cleaned up.**
- **3,939 rows have an empty `description`.** 803 distinct descriptions across ~6,758 non-scanner rows.
- Genuine content exists and is mass-duplicated: e.g. **`सडकमा क्षति` ("damage to the road") repeated 46 times**;
  "Landslide occurred due to heavy rainfall in Ward No. 1 of Sidingwa Rural Municipality" repeated ~157 times;
  "Landslide Apihimal-1 Bhattar" ×72. `createdOn` spans 2023-03-29 → 2026-09-28.
- **Plain reading: BIPAD already has a citizen landslide-reporting intake and it is an unmanaged
  black hole — thousands of reports, zero verified, six ever linked to an incident, plus two years of
  unremoved attack traffic.**

**OPML's documented BIPAD deficiencies — VERIFIED (Dec 2020):**
- "**does not support data processing for risk analysis**"; "limited to compiling... and visualizing"
- "**There is data gap in the loss and damage database**"; "missing information from some districts and VDCs";
  damage and loss values "need to be geo-referenced and standardized terminologies are required...
  **There is also a need for clear national guidelines on recording loss and damage data and financial estimates.**"
- economic loss figures "appear in round figures **as if the estimated amounts were put on an ad-hoc manner**"
- **no incident↔loss linkage**: "there is no feature to check which incident caused the damage"
- **"Activity logs are required in the BIPAD portal for disaster monitoring, post-event analysis and
  future response planning"** — i.e. **there is no record of who acted on a report.**
- **"Multi-lingual support is necessary"** — a Nepali-language interface was still a *recommendation*.
- Recommendation #1: "**The DRM legislation must clearly define the chain of command, roles,
  responsibilities of stakeholders, and the sequential priority actions, through the SOP and DRM plans
  at the local level.**" → as of 2020, **the chain of command was not clearly defined.**
- Needs customisation for "**753 municipal governments, 77 districts, and seven provincial governments**."

---

## 6. What a work order looks like

**There is no public, named "work order" template for a road slope repair in Nepal.** State that plainly.

But the real structured artefacts do exist, and one of them is now machine-readable:

**(a) BIPAD `highway` road-blockage register — VERIFIED FIRST-HAND. This is the closest thing to a
dispatch/action record, and it is public.** 398 records, `dateCreated` 2025-06-06 → 2026-09-28. Fields:

| Field | Example / meaning |
|---|---|
| `title`, `roadRefno`, `linkCode` | "Existing East-West Highway", `NH01`, `NH01-067` |
| **`division`** | **DoR division: Bharatpur (91), Khalanga (45), Baglung (42), Palpa (34), Nuwakot (24)...** |
| `chainage`, `endChainage` | `127+500` — location along the road |
| `location`, `point`, `ward`, `municipality`, `district`, `province` | full administrative geocoding |
| **`status`** | **OPEN 311, PARTIAL_OPEN 73, CLOSED 14** |
| **`closureReason`** | **Landslide 307, Heavy Rainfall 25, Debris from uphill 6, Rockfall 2...** |
| `dateRoadblockStart`, `dateRoadblockEndEstimated`, **`dateRoadblockEnd`**, **`actualRepairTime`** | timing; 385/398 have an actual repair time |
| **`repairEta`** | "1 hours", "2 hours", "1 days"... |
| **`effortsBeingMade`** | 332/398 populated — free text on what is being done |
| **`contactPerson`** | 374/398 populated |
| `images` | only 103/398 |
| `remarks`, `roadDataId`, `affectedDemography` | |

**This module is NEW (~June 2025 onward) and it is the natural target for a detection→dispatch tool.**
It already encodes *division, chainage, hazard reason, status, ETA, actual repair time, responsible
contact and narrative of effort*. Note also that it contains live test data — records with
`remarks: "test"` and `contactPerson: "Test"` — so the module is young and lightly governed.

**(b) The DRO road blockage report — VERIFIED (JICA):** "DROs... are responsible for submitting a
**road blockage report** to the central office of DOR. Based on this report, the DOR Maintenance
Office updates the database regarding sites (highway names, distance markers), geohazard types, and
road closure times." This is the per-event authorisation/notification instrument. Format not public.

**(c) The GESU/DoR 2007 inspection forms — VERIFIED (JICA + the guide itself):** annexes **A1 Site
Definition, A2 Slope Problems, A3 Erosion Problems, A4 Pavement Problems, A5 Structural Problems**,
each as *Data Sheet → Decisions → Actions*. **Approval chain: DRO staff inspect by the format; "the
superior engineer approves the inspection result."** This is the only documented slope-inspection
form-and-approval chain in the country — and it has not been used since 2007.
Guide: `https://dor.gov.np/uploads/publication/publication_1472792371.pdf`

**(d) The funding/authorisation instrument — VERIFIED (JICA):** the **IARMP/ARMP** (Integrated
Annual Road Maintenance Plan), built from **HMIS** data, compiled per road section, determines which
works are authorised in a year. It is a plan, not a per-request work order.

**Approval chain, end to end:** DRO inspection → superior engineer approval → (if beyond DRO) GESU
survey & design → funded through RBN allocation → executed via IARMP/ARMP as recurrent/periodic/
specific-preventive (outsourced) or emergency (in-house) maintenance.

---

## 7. Where information actually gets lost

All points below are VERIFIED from the cited sources unless tagged otherwise.

1. **The intake is world-writable and unmanaged.** 7,081 `citizen-report` rows; **0 verified; 6 linked
   to an incident**; 323 SQLi probe strings persisting ~21 months; 3,939 empty descriptions; mass
   duplication (46 identical "सडकमा क्षति" road-damage reports). *BIPAD already received road-damage
   citizen reports and did nothing with them.*
2. **Only Nepal Police can create an incident.** A ward chair, a citizen, or a road engineer **cannot**
   enter an incident record; the municipality can only comment. Any report not seen by police
   essentially does not become an incident.
3. **No activity log.** OPML: activity logs *must be added* — so today there is no auditable record of
   who was notified, who acted, or how long it took. Reports cannot be chased.
4. **No incident↔loss↔action linkage.** OPML: "there is no feature to check which incident caused the damage."
5. **The inspection function is unfunded and unstaffed.** The GESU app has **zero records** since
   ~2022; **no budget** for inspection training; **no personnel** to inspect or key data; **most DRO
   staff unaware the 2007 guide exists**.
6. **The money for slope protection is the money that gets cut.** RBN allocated 68% of demand
   (32% gap); the cut falls on Specific/Preventive maintenance — the exact budget head that builds
   slope protection. Only 40% of surveyed collapse sites had any measures.
7. **Warning is broadcast, not addressed.** Slide warnings go out from the NEOC geohazard unit via
   "SMS, TV, etc." — no verified named-recipient dispatch to a ward chair or a DRO engineer.
8. **The integration OPML asked for in 2020 is still a recommendation.** Overlaying DHM Rain Watch with
   landslide susceptibility for rainfall-induced landslide warning. (Unverified whether since built.)
9. **Local capacity is the binding constraint.** Only **60%** of local governments have ward-level DRRM
   committees; "capacity remains inadequate and there is no strategy to strengthen"; no DRRM HR roster;
   limited staff for post-event needs assessment (IRA/MIRA).
10. **Data quality is contested from inside.** JICA: DoR publishes damage history only after
    2021-04-14; records incomplete; risk assessment had to be reconstructed from DRO interviews and
    satellite traces; climate-change intensification not accounted for.

---

## 8. What a new tool could realistically plug into — with the interface

| # | Target | Interface | Realistic? |
|---|---|---|---|
| 1 | **BIPAD `highway/` road-blockage register** | HTTPS JSON REST (write needs a BIPAD login, DoR division level) | **BEST TARGET.** It already carries division, chainage, closureReason, ETA, repair time, contact. A slope inspection request maps onto it almost field-for-field. |
| 2 | **BIPAD GeoServer WMS/WFS** | OGC WMS / WFS, GeoJSON out; **public, no auth, verified working** | **DO THIS.** Ward-level landslide hazard *and* risk layers let a tool resolve coordinate → ward → hazard/risk class → named authority today. |
| 3 | **BIPAD `citizen-report/` POST** | HTTPS JSON, unauthenticated, `{description, image, point, hazard=17, ward}` | **DANGEROUS ALONE.** Writing here reproduces a 7,081-row black hole with zero verification and no triage owner. Only viable **with** a named verifying authority. |
| 4 | **SMS to named officials** | SMS text; needs gateway/NDRRMA agreement | The only documented last-mile channel. Recipient list not public. **A reported (unverified) claim favours IVR/voice over SMS** — "calls were more likely to be answered than messages read" (NCDRR 2025, unfetched). |
| 5 | **BIPAD Profile > Contacts (DMC contacts at local, ward, community level)** | listed as `municipality-contact/` in the API | This is the real routing registry, and it is the correct key for an authority-routing ontology. Content not yet verified. |
| 6 | **DoR DRO / GESU as a document** | email or printed Nepali advisory; the existing pattern is documents, letters, meetings and the A1–A5 forms | **VIABLE and probably the only thing that works short-term.** A Prio-ranked inspection request addressed to a named DRO Divisional Engineer / GESU, in Nepali, formatted like the A2 Slope Problem sheet, fits existing practice. |
| 7 | CSV / paper hand-off to a municipality | CSV + printed form | Realistic but slow; aligns with the municipality's statutory duty to maintain the local disaster database. |

**Text diagram of the realistic insertion point:**

```text
   detection (satellite / model)          <-- solved, open, publishable
              |
              v
   +----------------------------------+
   |  JOIN against BIPAD GeoServer     |   <-- PUBLIC, WORKS TODAY
   |  ward-level landslide hazard/risk |
   +----------------------------------+
              |
              v
   +----------------------------------+
   |  Resolve AUTHORITY:               |
   |   national highway -> DoR DRO     |   <-- the parent's "ontology" artefact
   |   provincial road  -> Province    |
   |   local road       -> Municipality|
   |   + ward DMC contact from BIPAD   |
   +----------------------------------+
              |
              v
   +----------------------------------+
   |  Emit an INSPECTION REQUEST       |   <-- the real deliverable
   |  Nepali, addressed, priority-      |
   |  ranked, data-gap stated honestly  |
   +----------------------------------+
              |
     +--------+---------+
     v                  v
  BIPAD highway/      Email/print to named DRO
  road-blockage       Divisional Engineer / GESU
  register            (A1-A5 form idiom)
```

---

## 9. Blunt assessment: what makes a software-only intervention unrealistic

1. **The blocker is not detection, and it is not messaging. It is that nobody is funded to inspect.**
   The GESU app has existed for years with **zero records**, no inspection personnel, and no training
   budget. A better inspection *request* does not create an inspector.
2. **The authority that can create an incident is Nepal Police — not the ward, not the municipality.**
   A tool that routes only to ward chairs is routed to an actor with view-and-comment rights and no
   record-creating power.
3. **Slope protection sits in the budget line that is cut first.** RBN funds 68% of demand; the shortfall
   lands on Specific/Preventive maintenance. An unfunded recommendation is not dispatch.
4. **The ward is a contingent body.** It exists only if the municipality constituted it (DRRM Act
   s.17(2)(f)); only 60% of local governments have ward-level DRRM committees.
5. **A write-only integration is worse than none.** Adding rows to `citizen-report` without a named
   verifying authority reproduces the existing failure exactly: thousands of reports, zero verified,
   six linked to incidents.
6. **Therefore any credible deployment must name (i) a funded actor, (ii) a budget head (RBN
   specific/preventive maintenance, or a donor project such as SRCTIP/GRID), and (iii) the receiving
   desk inside DoR (DRO Divisional Engineer / GESU) — not just the ward.**

**What is genuinely open and defensible to build:** the parent's artefacts A (authority-routing
ontology), B (measured Nepali advisory quality) and C (calibrated data-gap honesty) are **not**
pre-empted. BIPAD's own Geoserver and the `highway` register give A a real, public data backbone;
OPML's 2020 recommendation shows the need was recognised and never met; and the GESU app's zero
records prove the inspection layer is dormant rather than occupied.

---

## 10. What I could NOT verify (explicit)

1. **The GESU/DoR inspection app's name, vendor, and current (post-Feb-2024) operational status.**
   JICA never names it; no public documentation exists. **Do not assert its name or that it is dead — only that as of Feb 2024 it held zero records.**
2. **The verbatim LGOA 2074 Schedule / s.11–s.12 duty lists.** I have OPML's tabulation only. Every
   attempt to retrieve the statute text failed (lawcommission.gov.np HTML, municipal mirrors 404 /
   connection refused). **Do not cite LGOA item numbers.**
3. **The World Bank "Geo-Hazard Risk Management and Road Asset Management in Nepal" document.**
   I did not locate that exact title. I retrieved a different World Bank CPGA crisis-preparedness
   report (68 pp.) and relied on JICA plus OPML instead.
4. **DHM/NEOC's actual warning recipient list, SMS gateway/aggregator, and whether CAP is implemented.**
   Nothing public. The one mechanism I verified is the NEOC geohazard unit broadcasting via
   "SMS, TV, etc."
5. **Whether the Practical Action thresholds are operationally loaded in DHM's system as of Sep 2026.**
   The report frames integration as the next step.
6. **Whether OPML's 2020 recommendation (Rain Watch × landslide susceptibility) was ever built.**
7. **The NCDRR/DASTA-IVR claim** — the PDF server returned a 300-byte block; snippet only, treat as a lead.
8. **BIPAD total record counts** — the API `count` field is broken (`9223372036854775807`). My 7,081
   citizen-report figure is a floor, not a total. Same caveat for `highway` (398) and all other collections.
9. **Any public "work order" template** for slope repair. I found the instruments in §6, not that artefact.
10. **Whether the `highway` register's write path requires authentication** — I did not attempt a write.
    (The `citizen-report` write path, by contrast, I did test safely: 400, not 401 → open.)

---

## Appendix: primary sources fetched and read

- JICA, *Data Collection Survey on Road Disaster Prevention in Nepal*, Final Report (288 pp.)
  https://openjicareport.jica.go.jp/pdf/12384491_01.pdf
- DoR/GESU, *Road-side Geotechnical Problems: A Practical Guide to Their Solution* (2007)
  https://dor.gov.np/uploads/publication/publication_1472792371.pdf
- *Disaster Risk Reduction and Management Act, 2074 (2017)*, English
  https://faolex.fao.org/docs/pdf/NEP228597.pdf
- Oxford Policy Management, *Strengthening the Government of Nepal's portal for data on disaster and
  disaster risks* (Dec 2020) https://opml.com/files/Publications/a1594-strengthening-the-disaster-risk-response-in-nepal/strengthening-the-bipad-portal-for-data-on-disaster.pdf
- Oxford Policy Management, *Delineation of DRRM Roles and Responsibilities between Federal,
  Provincial and Local Level in Nepal* https://opml.com/files/Publications/a1594-strengthening-the-disaster-risk-response-in-nepal/delineation-of-responsibility-for-disaster-management-full-report-english.pdf
- Practical Action / DPNet, *Developing thresholds for landslides triggered by rainfall in
  Sindhupalchok Region* https://www.dpnet.org.np/uploads/files/Final_report_of_Helambu_and_panchpokhari_thangpal0502%202026-01-20%2007-48-55.pdf
- BIPAD role handbooks (Nepal Police, Municipalities/Rural Municipalities, Districts, Super Admin,
  User Handbook) via https://bipadportal.gov.np/api/v1/manual/
- BIPAD API root https://bipadportal.gov.np/api/v1/
- BIPAD GeoServer https://bipadportal.gov.np/geoserver/wms?service=WMS&request=GetCapabilities
- Practical Action news item on the Sindhupalchok thresholds
  https://practicalaction.org/news-stories/local-news/new-report-sets-rainfall-thresholds-to-predict-landslides-in-sindhupalchok-nepal/
