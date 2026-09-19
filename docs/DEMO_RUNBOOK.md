# TANIM demo runbook

This runbook gives the exact live demo path for Tomato and Eggplant, plus the backup plan when something fails on stage.

The demo uses only committed local files. It does not call PSA services. You can unplug the network after setup and the demo still works.

Files used:

- datasets/demo_farm_plans.csv: 40 ha tomato and 8 ha eggplant, zero margin
- datasets/demo_coordination_baseline.csv: 375 MT tomato and 180 MT eggplant
- scripts/grci.py: the independent calculation engine
- tests/test_mvp_e2e.py: the automated end-to-end checks

## Before the demo

1. Open a terminal in the repo root.
2. Run all checks: py tests/test_datasets.py, then py tests/test_crop_registry.py, then py tests/test_yield_reference.py, then py tests/test_grci.py, then py tests/test_mvp_e2e.py.
3. All five must print OK. If any fails, stop and use the backup plan below.
4. Disconnect the network if you want to prove the offline claim.

## Tomato live path

1. Open the plan entry screen.
2. Select crop: tomato.
3. Select location: Tanauan, Batangas.
4. Select harvest period: 2026-12.
5. Enter four farm plans of 10.0 ha each with margin 0.0 ha.
6. The app sends reference yield 15.0 with source DEMO-2026 synthetic yield, and reference amount 375 with type demo_coordination_baseline.
7. Press calculate.
8. Expect planned area 40.0 to 40.0 ha.
9. Expect expected production 600.0 to 600.0 MT.
10. Expect comparison 1.6 to 1.6.
11. Expect risk state high.
12. Expect the label Demo coordination baseline (not market demand).
13. Read the explanation line aloud. It states area, yield, production, comparison, and risk in plain sentences.

## Eggplant live path

1. Keep location Tanauan, Batangas and harvest period 2026-12.
2. Select crop: eggplant.
3. Enter two farm plans of 4.0 ha each with margin 0.0 ha.
4. The app sends reference yield 12.0 with source DEMO-2026 synthetic yield, and reference amount 180 with type demo_coordination_baseline.
5. Press calculate.
6. Expect planned area 8.0 to 8.0 ha.
7. Expect expected production 96.0 to 96.0 MT.
8. Expect comparison about 0.53 to 0.53.
9. Expect risk state low.
10. Expect the label Demo coordination baseline (not market demand).

## Margin moment (optional, one minute)

1. Change one tomato plan to 2.0 ha with margin 0.2 ha.
2. Expect the area line to read Estimated range: 1.8 ha to 2.2 ha.
3. At yield 15, expect Estimated range: 27 MT to 33 MT.
4. Say aloud: the margin is estimated by the farmer, so the result is a range, not a single exact number.

## Failure lines to say on stage

- Missing yield: the screen shows incomplete and says the reference yield is missing. No production number is shown.
- Unknown crop: the screen shows unsupported and says the crop has no safe production and area join. No supply number is guessed.
- Bad input: the screen shows invalid and keeps the raw input visible for correction.

## Backup plan

1. If the UI fails, run the engine directly: py tests/test_mvp_e2e.py. The 23 end-to-end checks print the same tomato and eggplant numbers.
2. If the laptop fails, read the numbers from this file. The fixed demo values never change: tomato 40 ha, 600 MT, 1.6, high; eggplant 8 ha, 96 MT, 0.53, low.
3. If a judge asks about demand, answer: the demo reference is a synthetic coordination baseline, not observed market demand. The labels on screen say so.
4. If a judge asks about Luzon coverage, answer: the yield reference files are committed locally, and the engine never invents a missing region.
