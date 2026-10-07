// "In short" boxes: the plain-words summary at the top of each data page.
// All the text lives here, so it is edited in one place. site.js puts the box on the page.
//
//   text:   paragraphs. {id.key} inserts a live number from indicators.js, e.g. {air.vd} or {co2.now}.
//           The keys for each indicator are listed in indicators.js (the object each loader returns).
//   claims: answers on claims.html to link to, by their id (see CLAIMS below).
//
// Keep it short: two or three sentences that someone with no science background can follow.

window.CLAIMS = {
  'natural-cycles':   '"It\'s just natural cycles" or "it\'s the sun"',
  'always-changed':   '"The climate has always changed"',
  'trace-gas':        '"CO₂ is a trace gas, it can\'t matter"',
  'antarctic-ice':    '"Antarctic sea ice is growing"',
  'stopped-1998':     '"Warming stopped in 1998"',
  'sea-level':        '"Sea level rise is tiny"',
  'data-manipulated': '"The data is manipulated"',
  'saturated':        '"The CO₂ effect is saturated"',
  'volcano':          '"Mauna Loa is a volcano"',
  'plant-food':       '"CO₂ is plant food"',
  'arctic-recovered': '"Arctic sea ice has recovered"',
  'cooling':          '"It\'s freezing here" or "it\'s cooling"',
  'records-short':    '"The records are too short or patchy"',
  'urban-heat':       '"It\'s just cities (urban heat islands)"',
  'cold-deaths':      '"More people die of cold than heat"',
  'adapt':            '"Plants and animals will adapt"',
  'too-late':         '"It\'s too late, so nothing matters"',
  'weather-blame':    '"Every bit of weather gets blamed on climate change"',
};

window.IN_SHORT = {
  'air.html': {
    text: [
      'The average temperature of the air near the surface, across the whole planet. It is the warming people feel, and the measure the Paris Agreement limits of 1.5 °C and 2 °C refer to.',
      'Right now: {air.vd}, {air.now} compared with the 1991–2020 average for {air.date}. Over the last 12 months the planet was about {air.pre12} warmer than before industrialization (1850–1900).',
    ],
    claims: ['stopped-1998', 'cooling', 'weather-blame', 'natural-cycles', 'records-short', 'urban-heat', 'data-manipulated'],
  },
  'nino.html': {
    text: [
      'El Niño and La Niña are a natural cycle in the tropical Pacific. Every few years the ocean there turns unusually warm (El Niño) or cool (La Niña), which pushes global temperatures up or down for a year or so. This page tracks the key region, called Niño 3.4.',
      '{nino.vd}. The central Pacific is {nino.now} compared with the 1991–2020 average for {nino.date}. These swings come and go; the long-term warming continues through both phases.',
      'This is the traditional daily index. NOAA\'s official index averages three months and subtracts the warming of the whole tropics (the "relative" index), so it reads lower; both show the same event.',
    ],
    claims: ['natural-cycles', 'stopped-1998'],
  },
  'land-ice.html': {
    text: [
      'Greenland and Antarctica hold most of the world\'s fresh water as ice; mountain glaciers hold far less, but react quickly to warming. Since 2002 the GRACE satellites have weighed the two ice sheets every month; glaciers are measured on the ground and from space once a year. Unlike sea ice, ice that melts or slides off land adds water to the ocean and raises sea level.',
      'Latest ({land.date}): {land.vd}. Since 2002–03 Greenland has lost about {land.gl} and Antarctica about {land.an}, together adding {land.mm} to global sea level. The world\'s glaciers lost {land.glac} in the hydrological year {land.gh}.',
    ],
    claims: ['sea-level', 'antarctic-ice'],
  },
  'slow.html': {
    text: [
      'In {fossil.through} the world emitted {fossil.now} of CO₂ from fossil fuels and cement ({fossil.ch} on the year before). About a quarter of it ends up in the ocean, which is slowly becoming more acidic: near Hawaiʻi, surface water has {ph.hplus} more acidity than in {ph.since}.',
      'The Atlantic overturning circulation, which carries warmth north towards Europe, averaged {amoc.a12} over the 12 months to {amoc.through}. It varies a lot, and two decades of direct measurements are not yet enough to confirm a long-term weakening, though climate models expect one.',
      'The Red List Index of extinction risk fell from {rli.first} in {rli.y0} to {rli.now} in {rli.through} ({rli.pct}): on balance, species are moving closer to extinction.',
    ],
    claims: ['adapt'],
  },
  'pdo.html': {
    text: [
      'The Pacific Decadal Oscillation (PDO) is a slow, El Niño-like swing in the North Pacific. In its warm (positive) phase the water along North America runs warm; in its cool (negative) phase the reverse. Phases last years to decades and nudge global temperatures and weather around the Pacific.',
      'Latest ({pdo.date}): {pdo.now}. {pdo.vd}. The 12-month average is {pdo.a12}. Like El Niño, the PDO moves heat around; it does not add heat to the planet.',
    ],
    claims: ['natural-cycles'],
  },
  'sun.html': {
    text: [
      'The Sun\'s activity rises and falls over a cycle of about 11 years, tracked by counting sunspots since the 1700s. At solar maximum the Sun gives off about 0.1% more energy, worth roughly 0.1 °C of global temperature.',
      'Latest ({sun.date}): sunspot number {sun.now}. {sun.vd}. The Sun has not become more active since the 1950s while the planet warmed, so it cannot explain the warming.',
    ],
    claims: ['natural-cycles'],
  },
  'sst.html': {
    text: [
      'The average temperature of the ocean surface between 60°S and 60°N, measured by satellites, ships and buoys. Oceans cover 70% of the planet. Warmer seas feed heavier rain and stronger storms, and bleach coral reefs.',
      'Right now: {sst.vd}, {sst.now} compared with the 1991–2020 average for {sst.date}. This chart uses the satellite-era record, which starts in {sst.first}; measurements from ships go back to the 1850s.',
    ],
    claims: ['natural-cycles', 'weather-blame', 'urban-heat', 'records-short', 'data-manipulated'],
  },
  'ohc.html': {
    text: [
      'How much heat is stored in the upper 2000 metres of the ocean. About 90% of the extra heat trapped by greenhouse gases ends up here (IPCC), so this is the steadiest measure of global warming, with little year-to-year noise.',
      'Latest ({ohc.date}): {ohc.vd}. The ocean gained {ohc.d12} of heat in 12 months. One ZJ is 10²¹ joules; that gain is about {ohc.energyX} all the energy humanity uses in a year.',
      'Measured to 700 m since {ohc.first7}, and to 2000 m since {ohc.first2}, when thousands of Argo floats reached every ocean.',
    ],
    claims: ['natural-cycles', 'stopped-1998', 'records-short'],
  },
  'sea-level.html': {
    text: [
      'The average height of the world\'s oceans, measured by satellites since 1993. The sea rises because warming water expands and because ice on land melts into it.',
      'Latest ({sl.through}): {sl.vd}. The sea is {sl.rise} higher than in 1993, rising {sl.r10} per year over the last 10 years, compared with {sl.r0} per year in 1993–2002.',
    ],
    claims: ['sea-level', 'data-manipulated'],
  },
  'sea-ice.html': {
    text: [
      'How much of the ocean is covered by sea ice, in the Arctic and around Antarctica, measured by satellites since 1978. Bright ice reflects sunlight; open water absorbs it, so losing ice adds to warming.',
      'Arctic ({ice.date}): {ice.vd}, {ice.an} compared with 1981–2010. Antarctic ({ant.date}): {ant.vd}, {ant.an} compared with 1981–2010.',
      'The {ice.minN} lowest Arctic summer minimums on record have all come since {ice.minSince}.',
    ],
    claims: ['arctic-recovered', 'antarctic-ice'],
  },
  'co2.html': {
    text: [
      'The amount of carbon dioxide in the air, measured at Mauna Loa in Hawaii since 1958. CO₂ is the main driver of global warming, mostly from burning coal, oil and gas, and much of it stays in the air for centuries.',
      'Latest: {co2.now} (30-day average to {co2.date}), {co2.pct} more than before industrialization. {co2.vd}.',
    ],
    claims: ['trace-gas', 'volcano', 'plant-food', 'always-changed', 'too-late'],
  },
  'ch4.html': {
    text: [
      'Methane is the second biggest driver of warming after CO₂. It comes from oil, gas and coal production, farming (mainly cattle and rice), landfills and wetlands. It traps far more heat per molecule than CO₂ but breaks down within about a decade, so cutting it slows warming quickly.',
      'Latest ({ch4.date}): {ch4.now}, {ch4.vd}. It rose {ch4.rise} in {ch4.riseYear}.',
    ],
    claims: ['trace-gas', 'too-late'],
  },
  'eei.html': {
    text: [
      'The difference between the energy Earth receives from the sun and the energy it sends back to space, measured by NASA satellites since 2000. When more comes in than goes out, the planet has to heat up. This is the warming at its source.',
      'Latest: over the 12 months to {eei.date}, Earth gained {eei.l12} (watts per square metre, averaged over the whole planet). {eei.vd}.',
    ],
    claims: ['natural-cycles', 'saturated', 'trace-gas', 'too-late'],
  },
};
