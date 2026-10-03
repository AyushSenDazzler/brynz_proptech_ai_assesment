from brynz.damage import rules_and_scope
from brynz.geometry import measurement


def test_concealed_flags_retain_rule_and_surface():
    region = {
        "id": "damage-1",
        "class": "water_stain",
        "surface_id": "room-1:wall-1",
        "bottom_height_m": 0.2,
        "area": measurement(0.3, 0.15, "m2"),
    }
    flags, scope = rules_and_scope([region])
    assert flags[0]["rule"] == "stain_near_wall_base"
    assert flags[0]["surface_id"] == region["surface_id"]
    assert scope[0]["quantity"]["interval"] == [0.15, 0.45]
    assert scope[0]["status"] == "pending_review"


def test_no_damage_does_not_imply_hidden_damage():
    assert rules_and_scope([]) == ([], [])


def test_unknown_floor_does_not_trigger_base_rule():
    region = {
        "id": "damage-1",
        "class": "water_stain",
        "surface_id": "wall-1",
        "bottom_height_m": None,
        "area": measurement(0.3, 0.15, "m2"),
    }
    flags, _ = rules_and_scope([region])
    assert flags[0]["rule"] == "visible_stain_on_wall"
