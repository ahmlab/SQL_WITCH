# Fatigue and Focus

A tired witch reads fewer rows (plan §4.5). This page explains how to change how fast the
protagonist tires and what being tired does. Every number lives in `data/fatigue.json`; the code
is `magic/fatigue.py` (rules) and the battle screen (`engine/scenes.py`, `engine/grimoire.py`).

## The meter

One number from 0 (rested) to 1 (spent), kept in the save (`fatigue`, and `focus` for the
streak). It **rises** by the amounts in `rise`: every battle round (`round`), every cast
(`cast`), every region walked (`region`), every defeat (`defeat`), every wrong puzzle answer
(`wrong_answer`) and when the party leaves the Hearth without sleeping (`skipped_sleep`). It
**falls** at the Hearth by the amounts in `fall`: `sleep` (1.0 is a full night), `meal`, `letter`.

## The bands

`bands` is read from the top: the first band whose `below` is above the meter applies.

| field | what it does |
|---|---|
| `rows` | how many rows the Grimoire's right page shows (the Rule of the Page) |
| `blur` | 0 = sharp; above 0 the result is drawn with a ghost copy, and cells jitter a pixel (still when screen shake is off) |
| `yawn` | the Grimoire yawns when the protagonist enters this band in battle |
| `faint` | the protagonist faints when the battle ends, whatever the outcome, and wakes at the Hearth |

The panel shows the meter as a candle that burns down, and the band's name with its rows.

## Focus

`focus.streak` efficient casts in a row (spells landed, nothing overflowed, nothing fizzled)
charge Focus: the next `focus.lasts_casts` casts read `focus.bonus_rows` more rows, and the page
edge glows gold. Any sloppy cast (an overflow, a fizzle, a miscast) spends the charge and starts
the streak again. Free looks and pure writes neither build nor break the streak. A letter from
home gives `letter_charges` charges for the next fight. Nothing about Focus depends on speed.
