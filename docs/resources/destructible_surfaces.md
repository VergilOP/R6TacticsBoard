# Destructible Surfaces

This document records the map asset schema for soft walls and hatch surfaces.

## Scope

Map resources define static destructible surfaces.
Tactic projects store the tactical state applied on top of those surfaces.

- Map resource: where the surface exists
- Tactic project: whether that surface is reinforced or opened

## Map JSON

Recommended structure:

```json
{
  "layers": {
    "surfaces": [
      {
        "id": "soft-1",
        "kind": "soft_wall",
        "floor_key": "1f",
        "start": { "x": 1200, "y": 640 },
        "end": { "x": 1480, "y": 640 },
        "label": "",
        "note": ""
      },
      {
        "id": "hatch-1",
        "kind": "hatch",
        "floor_key": "2f",
        "start": { "x": 840, "y": 900 },
        "end": { "x": 980, "y": 1040 },
        "label": "",
        "note": ""
      }
    ],
    "soft_walls": [],
    "hatch_surfaces": []
  }
}
```

## Fields

- `id`: unique surface id inside the map
- `kind`: `soft_wall` or `hatch`
- `floor_key`: owning floor
- `start` / `end`: line endpoints for soft walls, diagonal corners for hatches
- `label`: optional short display name
- `note`: optional editor note

## Notes

- `layers.surfaces` is the canonical field.
- `layers.soft_walls` and `layers.hatch_surfaces` are redundant typed indexes written alongside it.
- Soft walls are rendered as line segments in the tactical editor.
- Hatches are rendered as filled areas in the tactical editor.

## Tactical State

Project files store tactical state separately from map resources.

```json
{
  "surface_id": "soft-1",
  "reinforced": false,
  "opening_type": "passage",
  "foot_hole": false,
  "gun_hole": false
}
```

Rules:

- Reinforced surfaces cannot have any openings or holes.
- `passage`, `crouch_passage`, and `vault` are mutually exclusive.
- If one of those three openings is set, `foot_hole` and `gun_hole` must both be false.
- `foot_hole` and `gun_hole` may coexist.
- Reinforcement count is capped at `10` per tactic project.
