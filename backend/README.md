Visual Construct Configuration
==============================

The `visual_configs.json` file in this folder defines how the Scene Director lays out, styles, and animates every lyric phrase. Update the JSON to experiment with new visual futures without touching the timing or audio pipeline.

File structure
--------------

Each top-level key is the construct name that appears in the UI. Every construct contains:

- `label`: Friendly name shown in the dropdown.
- `description`: Short blurb that helps future-you remember the vibe.
- `phrase_layout_sequence`: Ordered list of layout directives that the director cycles through as phrases progress.
- `word_style`: Styling instructions for the text clips inside each phrase.

Phrase layouts
--------------

A single layout entry accepts these keys (they are all optional, defaults kick in if you omit them):

- `layout`: `center_stack`, `diagonal_wave`, `split_columns`, or `center_overlay`.
- `anchor`: Where the composed block sits in frame (`center`, `top_left`, `top_center`, `top_right`, `center_left`, `center_right`, `bottom_left`, `bottom_center`, `bottom_right`).
- `line_gap` / `column_gap`: Vertical or lateral spacing, depending on layout.
- `diagonal_step`: Object with `x`/`y` offsets between words for `diagonal_wave`.
- `overlay_offset`: Object with `x`/`y` offsets for `center_overlay`.
- `enter_fx`: `fade`, `slide_left`, `slide_up`, or `scale_in`.
- `exit_fx`: `fade`, `shrink`, or `lift`.
- `motion`: Object describing continuous movement.
- `background`: Light-weight panel behind the text block.

Motion settings
---------------

Set `motion.type` to shape how the block moves while visible:

- `static`: (default) stays anchored.
- `drift` / `float`: Sine-wave wobble. Use `axis` (`x`, `y`, `xy`), `amplitude`, and `speed`.
- `orbit`: Circular orbit around the anchor. Use `radius`, `axis`, and `speed`.
- `pan`: Linear motion. Combine with `direction` (`left`, `right`, `up`, `down`), `distance`, and `speed`.

Background panels
-----------------

Provide `background` to set `type: "panel"`, `color` (hex or `[r, g, b]`), `opacity`, `padding`, and `corner_radius` (stored but currently rendered as a rectangle).

Word styling rules
------------------

`word_style.base` establishes defaults (`font`, `fontsize`, `color`, `stroke_color`, `stroke_width`, `kerning`).

Add selectors in `word_style.rules` to override the base style when a rule hits. Every rule looks like:

```
{"match": {...conditions...}, "style": {...overrides...}}
```

Available match conditions:

- `pos`: List of spaCy POS tags (`NOUN`, `VERB`, `ADJ`, `PROPN`, etc.).
- `min_length` / `max_length`: Word length guardrails.
- `contains`: Case-insensitive substring (string or list of strings).
- `index`: `first`, `last`, `even`, `odd`, integer (zero-based), or list of integers.

Supported style overrides:

- `font`, `fontsize`, `color`
- `stroke_color`, `stroke_width` (or `outline` with `{ "color": ..., "width": ... }`)
- `case`: `upper`, `lower`, `title`
- `rotation`, `scale`, `opacity`, `kerning`

Add your own constructs
-----------------------

1. Duplicate an existing construct block inside `visual_configs.json`.
2. Rename the top-level key and tweak the label/description.
3. Adjust the layout sequence, motion, and styling rules.
4. Refresh the web UIâ€”constructs are reloaded automatically when a job starts.

If the JSON becomes invalid, the director silently falls back to the embedded default and prints a warning in the server log.
