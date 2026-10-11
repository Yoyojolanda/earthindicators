# Claims queue

Claims heard in the wild, waiting to be answered on claims.html. Built in batches of about 10 (or sooner on request).
Answers are written to apply generally: no local details (a state, a single glacier, a named person) unless the
claim can't be answered without them. Covered claims get extra search words (data-also) instead of a new answer.

## To build

- us-adjustments: "US raw thermometer readings show little or no warming; NOAA's adjustments create it." Seen 2026-10-11 as
  a heatmap of every 30+ year trend in USHCN daytime highs (raw vs fully adjusted); also "NOAA keeps closed stations alive
  with estimated temperatures". Extends data-manipulated, which covers global adjustments (they lower the trend) but not
  this US case, where they raise it. Points to make:
  - True as far as it goes: for US daytime highs the adjustments do add most of the warming. The question is whether
    they're right, and they can be tested.
  - Two documented biases, both making raw readings run cool over time: observers moving from afternoon to morning
    readings (time of observation), and the 1980s switch to electronic sensors that read highs lower (MMTS).
    Daytime highs are hit hardest by both; raw nighttime lows already show warming.
  - The test: the US Climate Reference Network (since 2005, pristine sites, triple sensors, never adjusted) agrees with
    the adjusted record and not the raw one (Hausfather et al. 2016, GRL).
  - The 1930s Dust Bowl peak in highs was partly real: dry soil heats up more. One country is ~2% of Earth's surface;
    worldwide, adjustments lower the warming.
  - Filled-in estimates for closed stations change the trend little (in the claim's own numbers 1.74 vs 1.64 °F per
    century), and NOAA's official US record has used nClimDiv instead of USHCN since 2014.
  - The heatmap itself shows the cherry-picking point: a trend depends on the start and end years you choose.
  - Keep it general: no named critic.

## Built

- 2026-10-08: ice-age-1970s (A), how-much-human (B), models-unreliable (C), little-ice-age (D), wildfires (E), co2-not-ours (F),
  emissions-falling (G), god-in-control (H), cows (I), no-consensus (J), predictions-fail (K), medieval-warm (L),
  fewer-affected (M), solar-heat (N); extended weather-blame (attribution) and sea-level (past floods); search words added
  to stopped-1998, always-changed, hoax, trace-gas, records-short, natural-cycles, weather-blame, sea-level.
- 2026-10-08 (2nd batch): geothermal-antarctica (O), hunga-tonga (P), two-degrees, dinosaurs, hurricanes, polar-bears,
  crop-records, coral-recovering, acidification-myth, adapt-dutch, china-india, only-one-percent, renewables-grid, ev-worse,
  solar-payback, turbines-birds (black blade), tech-later, individual-pointless, net-zero-bankrupt; "98% fewer climate deaths"
  folded into fewer-affected; last group renamed "Nothing can be done".
