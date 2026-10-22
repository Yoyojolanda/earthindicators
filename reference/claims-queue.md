# Claims queue

Claims heard in the wild, waiting to be answered on claims.html. Built in batches of about 10 (or sooner on request).
Answers are written to apply generally: no local details (a state, a single glacier, a named person) unless the
claim can't be answered without them. Covered claims get extra search words (data-also) instead of a new answer.

## To build

- scenarios-fantasy: "Physicists can't invent nonexistent technology to prove a hypothesis, yet climate scientists project
  scenarios with fantasy tech (unicorns mining gold under rainbows)." Heard on X, 2026-10-20, in reply to a post on overshoot
  and accumulating damage. Points: scenarios are if-then explorations, not proofs or predictions (normal in physics and
  engineering too); overshoot pathways do rely on large future CO2 removal that barely exists today (link tech-later);
  scientists themselves flag that, and overshoot research is the warning against counting on it. Cross-link models.html.
  Sources for the build: IPCC AR6 WGIII SPM C.3.5 (1.5 °C no/limited overshoot: cumulative 2020-2100 BECCS 30-780 GtCO2,
  DACCS 0-310, AFOLU 20-400; net negative 20-660) and B.6.4 (return after overshoot: about -380 [-860 to -200] GtCO2 net
  negative in the second half of the century); Dyke, technosphere.earth 2026-10-20 (the overshoot-integral author himself
  calls removal of hundreds of billions of tons highly speculative; default should be temperatures staying up for centuries).
- heatwaves-always: "Heat waves have always happened." Heard 2026-10-21, prompted by Reuters' "The Age of Heat Storms"
  (2026-10-20). Points: yes, but measured against each place's own 1961-1990 normal (90th percentile, 5+ days, ERA5), the
  average share of the planet in a heat wave is up more than 12-fold since the 1960s while CO2 rose 30%+; the largest ones
  (>= 1% of the globe, Reuters' "heat storms") went from ~5 a year in the 1960s to ~102 a year this decade; at least one has
  been active every day since 6 July 2008; largest 1960s event ~6% of the globe for 46 days vs 85% for 367 days (2023-24).
  Why so much: a small shift in the average makes the hot tail grow enormously (link two-degrees; also extreme-picks).
  Label as Reuters' analysis: measured (ERA5 reanalysis, sparser observations in the 1960s), but counts depend on their
  thresholds (they call the 1% cutoff somewhat arbitrary). Paraphrase, don't quote. Don't copy their "Area of the Earth
  5,100,720 km2" (typo, two zeros missing).
  Cold side (Part 1 article): cold snaps/cold storms, same method (<= 10th percentile), have dwindled: area in a cold snap on
  an average winter day shrank by almost 80% from the 1960s to this decade (answers "but it was cold here last winter").
  Also Part 1: heat storms' share of a spot's top-10% hot days rose from ~3% (1960s) to ~43% (2020s); ordinary heat waves
  more than doubled in number; peak record now Raimundo 2026 (33.8% of the globe), previously Vera (31.3%, 5 Jan 2024).
  Chart option: Reuters published the heat-storm table (github.com/palewire/reuters-temperature-storms, MIT,
  data/all_storms.parquet, 2,527 warm storms 1960 to 2026-09-25; no cold storms in it). Counting by start year gives
  5.1/yr (1960s), 4.0, 16.5, 29.7, 47.7, 83.6, 94.4 (2020s to Sept); Reuters' 102 likely counts storms active in a year,
  check before publishing. Store only a small yearly summary in the repo, not the parquet.
  Sources: reuters.com/investigates/special-report/climate-heatstorms-takeaways/, .../climate-heatstorms-methodology/,
  .../climate-heatstorms-science/ (Part 1)

## Built

- 2026-10-08: ice-age-1970s (A), how-much-human (B), models-unreliable (C), little-ice-age (D), wildfires (E), co2-not-ours (F),
  emissions-falling (G), god-in-control (H), cows (I), no-consensus (J), predictions-fail (K), medieval-warm (L),
  fewer-affected (M), solar-heat (N); extended weather-blame (attribution) and sea-level (past floods); search words added
  to stopped-1998, always-changed, hoax, trace-gas, records-short, natural-cycles, weather-blame, sea-level.
- 2026-10-08 (2nd batch): geothermal-antarctica (O), hunga-tonga (P), two-degrees, dinosaurs, hurricanes, polar-bears,
  crop-records, coral-recovering, acidification-myth, adapt-dutch, china-india, only-one-percent, renewables-grid, ev-worse,
  solar-payback, turbines-birds (black blade), tech-later, individual-pointless, net-zero-bankrupt; "98% fewer climate deaths"
  folded into fewer-affected; last group renamed "Nothing can be done".
- 2026-10-11: us-adjustments (raw vs adjusted US highs, time of observation, sensors, reference network test,
  grouped-by-reading-time charts, filled-in stations); linked from data-manipulated and the air page.
- 2026-10-12: existential, tornadoes, extreme-picks (new); HITRAN added to no-experiment; global burned area (savanna,
  reconstruction, extreme forest fires) added to wildfires; deaths chart ending 2021 and 2022 European heat added to
  fewer-affected. Stratospheric cooling was already covered (no-experiment, natural-cycles, how-much-human).
- 2026-10-19: era5-model, already-15 (the "1.5 already passed in Feb 2026" claim; fits recomputed through Sep 2026:
  linear 1970 -> 2033, quadratic 1970 -> 2028, quadratic 1980 -> spring 2026, 2.0 °C in 2037; chance of no year below
  1.5 in 2027-2126 about 46-48% under the 1980 curve), climate-optimum (new); fire weather season (Jolly et al. 2015)
  added to wildfires; marine heatwaves added to extreme-picks; aerosol estimate, CERES albedo and "can no longer be
  avoided" wording added to too-late.
