# UK Steel Trade Measure from 1 July 2026 — Findings

Status: FOUND_FULL. The colleague's lost hyperlink is the GOV.UK notice below; Tables 3 and 4 were extracted completely and cross-verified against the live UK Integrated Online Tariff.

## Primary source
- **UK's steel trade measure from 1 July 2026** (Department for Business and Trade, "Decision"):
  https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026
  - First published 2 April 2026; last updated 2 July 2026 (matches the date of the colleague's note).
  - Contains Table 1 (Category 1 authorised-use global quota), Table 2 (authorised-use product list), **Table 3 (quota amounts by category/country, 72 rows)**, **Table 4 (order numbers, 72 rows)**.

## Supporting sources
- UK Integrated Online Tariff news story: https://www.trade-tariff.service.gov.uk/news/stories/uks-steel-trade-measure-from-1-july-2026--30-june-2026
- Live verification via quota API: https://www.trade-tariff.service.gov.uk/api/v2/quotas/search?order_number=058600
  returned an OPEN quota definition, validity 2026-07-01 to 2026-09-30, initial volume 93,750,000 kg (= 93,750 t, exactly Table 3's Category 1 / EU / Q1 figure), balance 90,248,498.8 kg at last allocation 2 July 2026.
- Outgoing regime (expired): Trade remedies notice 2026/15, safeguard TRQ on steel goods:
  https://www.gov.uk/government/publications/trade-remedies-notices-tariff-rate-quotas-on-steel-goods-expired/trade-remedies-notice-202615-safeguard-measure-tariff-rate-quota-on-steel-goods

## Structure of the new system
- Announced 19 March 2026; in effect **1 July 2026 to 30 June 2027** (quota year), implemented under the Taxation (Cross-Border Trade) Act 2018 (not the Trade Remedies/safeguard framework — the safeguard quotas and 25% additional duty ceased 30 June 2026).
- **Out-of-quota duty: 50% ad valorem** (calculated on the price before other import duties), vs 25% under the old safeguard.
- **Overall quota volumes reduced by 51%** vs the steel safeguard measure.
- **20 product categories** (1, 4, 5, 6, 7, 12A, 12B, 13, 14, 15, 16, 17, 19, 20, 21, 25A, 25B, 26, 27, 28), same category numbering scheme as the old safeguard.
- Quotas are **first-come-first-served via HMRC**, allocated **quarterly**: Q1 Jul–Sep, Q2 Oct–Dec, Q3 Jan–Mar, Q4 Apr–Jun. Unused quota **rolls over to the next quarter** but not into the next quota year.
- Country-specific allocations for the EU, India, South Korea, Vietnam, Japan, Turkey, USA, Switzerland, UAE (varies by category), plus a **Residual** quota per category for all other countries.
- **Order numbers 058600–058671** (72 quotas; Table 4). Same 6-digit 058xxx format as the old safeguard (which used 058001+); queryable at https://www.trade-tariff.service.gov.uk/quota_search?order_number=058600
- **Category 1 authorised use**: an ADDITIONAL global quota for hot-rolled sheet/strip imported for downstream processing under the authorised-use customs procedure (Table 1): global total 595,950 t in Q1, 595,950 t Q2, 582,993 t Q3, 589,468 t Q4, with a 40% per-country cap per quarter (238,380 / 238,380 / 233,197 / 235,787 t). Order number not stated in the notice ("as otherwise specified on the online tariff tool").
- **Transitional arrangement**: goods under contract before 14 March 2026 are fully exempt from the 50% out-of-quota duty between 1 July and 30 September 2026 (evidence required; see DBT "Implementation notifications on the transitional exemption", published 2 June 2026).
- **Ukraine excluded** from the measure; preferential UK–Ukraine arrangements continue.
- Sum of annual country/residual quotas across Table 3: 3,218,407 t (excluding the separate Category 1 authorised-use global quota).

## Files written (this directory)
- `uk_quotas_table3.csv` — Table 3 verbatim (72 rows: Category, Country or residual, Annual quota, Q1–Q4 tonnes).
- `uk_quotas_table4.csv` — Table 4 verbatim (72 rows: Category, Origin country/territory/residual, Order Number with leading zero).
- `uk_quotas.csv` — combined, sorted by order number: category_code, category_name, country, order_number, annual_quota_t, q1_jul_sep_t, q2_oct_dec_t, q3_jan_mar_t, q4_apr_jun_t (thousands separators removed).
- `uk_measure.html` / `uk_measure_text.txt` — raw page snapshot and extracted text (includes full commodity-code lists per category).

## Category names (from the notice)
1 non-alloy and other alloy hot-rolled sheets and strips (authorised-use measure also in place); 4 metallic coated sheets; 5 organic coated sheets; 6 tin mill products; 7 non-alloy and other alloy quarto plates; 12A alloy merchant bars and light sections; 12B non-alloy merchant bars and light sections; 13 rebars; 14 stainless bars and light sections; 15 stainless wire rod; 16 non-alloy and other alloy wire rod; 17 angles, shapes and sections of iron or non-alloy steel; 19 railway material; 20 gas pipes; 21 hollow sections; 25A large welded tubes (1); 25B large welded tubes (2); 26 other welded tubes; 27 non-alloy and other alloy cold finished bars; 28 non-alloy wire.
