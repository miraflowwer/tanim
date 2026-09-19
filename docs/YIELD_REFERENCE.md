# Yield reference

This file explains the TANIM yield reference in plain language.

## What is yield

Yield shows how much crop you get from one hectare of land.

The unit is metric tons per hectare.

The formula is simple:

Yield = Production in metric tons divided by Harvested area in hectares.

We use two official PSA measurements that TANIM already keeps:
production volume and harvested area.

We only join crops with the same exact name in both sources.
We never guess that similar names mean the same crop.

## Why five years

One year can be too high or too low.
Rain, pests, or price shifts can change one harvest.

So we use five full years, not one year.
Our reference period is 2021-2025.
Year 2026 is not complete yet, so we do not use it.

For each crop and Luzon region, the summary requires all five Annual values from 2021 to 2025.
If any Annual year is missing, that crop-region pair stays out of the summary.
We report the average, the lowest year, and the highest year.

The average is the main reference for the app.
The lowest and highest years show the range.

TANIM now has 6313 yearly Annual yields for 286 crops in 7 Luzon regions.

## How to use it in the app

Start with the farmer area in hectares.

Multiply the area by the average yield.

Expected production = Area in hectares times Average yield.

Example: 2 hectares of tomato times 13.95 is about 27.89 metric tons.
Example: 1.5 hectares of eggplant times 16.40 is about 24.61 metric tons.

Show these same words and numbers in the UI so farmers can check the math.

## Year and quarter

The detailed file has one row per crop, region, year, and period.
Period can be Quarter1, Quarter2, Semester1, Quarter3, Quarter4, Semester2, or Annual.

For palay and corn, quarterly area exists, so quarterly yield exists.
For many vegetables and fruits, quarterly area is missing in the source,
so quarterly yield is missing too. We keep it missing. We do not invent it.

The summary file uses Annual yields only.
It is stable across quarters.
You can use it for any harvest quarter, but note it is not quarter specific.

## Geography

Luzon means NCR, CAR, Region I, Region II, Region III, Region IV-A, MIMAROPA, and Region V.

Some crop tables have no NCR row. We keep every Luzon row that exists.
We never invent a missing region.

This first version uses region rows only.
Province rows are next. The file format already allows them.

## Files

Detailed yearly yields are in datasets/generated/yield_reference.csv.
Five year summary is in datasets/generated/yield_summary.csv.

Detailed columns keep production, area, yield, source tables, and source id.
Summary columns keep ref period, year count, average yield, min yield, and max yield.

## Limits

Yield is a production baseline. It is not market demand.
Do not present it as verified demand.

A production baseline helps planning. It does not prove a glut or a shortage.
Use it with the GRCI reference rules in docs/GRCI_SPEC.md.

Source tables can be revised. Rebuild the reference before a new release.
