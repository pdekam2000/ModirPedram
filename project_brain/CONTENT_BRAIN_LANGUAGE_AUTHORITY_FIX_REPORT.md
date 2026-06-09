# Phase A — Language Authority Fix

## Module
`content_brain/execution/content_brain_language_authority.py`

## Rule
Input language controls all downstream outputs (SEO, story, beats, prompts, hashtags, trends).

## Metric
`language_authority_score` (0–1) with drift labels per field.

## Root cause fixed
Spanish false-positive: substring `"con"` matched inside English word `"can"`. Language detection now uses whole-token matching only.

## Validation
`can you master perfume in one day?` → English only, score ≥ 0.89.
