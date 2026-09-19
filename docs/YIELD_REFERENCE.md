# Yield reference

This file explains the TANIM historical yield reference.

## What yield means

Yield shows how much crop was produced per hectare.

The unit is metric tons per hectare.

The formula is:

Yield = Production in metric tons divided by Harvested area in hectares.

TANIM uses PSA production volume and harvested area from matching crop records.

Crop joins use the same exact normalized crop label in the paired production and area tables.
Similar names are not merged by guesswork.

## Reference window

The reference window is 2021-2025.
Year 2026 is still partial, so it is not included.

A summary row needs all five Annual years inside the window.
The n_years field is 5 for every summary row.

The summary stores the arithmetic mean, lowest annual yield, and highest annual yield.
The average is the app reference. The lowest and highest values show historical spread.

The committed snapshot has 6313 Annual yield rows for 286 crops in 7 Luzon regions.

## Planning bridge

Start with planned area in hectares.

Expected production = Planned area in hectares times Average yield.

Example: 2 hectares of tomato times 13.95 is about 27.89 metric tons.
Example: 1.5 hectares of eggplant times 16.40 is about 24.61 metric tons.

If farm size is approximate, keep the area margin and show an estimated production range.

## Period detail

The detailed file has one row per crop, region, year, and available period.
Period can be Quarter1, Quarter2, Semester1, Quarter3, Quarter4, Semester2, or Annual.

Quarterly yield exists only when both quarterly production and quarterly harvested area exist.
Missing source values stay missing. TANIM does not fill them with invented values.

The summary uses Annual rows only.
It is not quarter specific.

## Geography

The source scope can include NCR, CAR, Region I, Region II, Region III, Region IV-A, MIMAROPA, and Region V.

Some source tables do not publish NCR crop rows.
The committed yield snapshot therefore contains only the Luzon regions that have matching production and area rows.

This version uses region rows only.

## Files

Detailed rows are in datasets/generated/yield_reference.csv.
Summary rows are in datasets/generated/yield_summary.csv.

The detailed file keeps production, area, yield, source table keys, source id, and data status.
The summary keeps the reference window, year count, average yield, minimum yield, maximum yield, unit, source id, and data status.

## Limits

Historical yield is a production reference. It is not market demand.
It does not prove that a glut or shortage will happen.

GRCI still needs a separate, clearly labelled comparison reference.
See docs/GRCI_SPEC.md for the allowed reference types and evidence rules.

PSA source tables can be revised.
Run the live audit before replacing the committed snapshot.
