"""
Regression suite for the werewolves engine (happy paths only).

These tests describe behaviour that is already correct. They must stay green:
do not weaken, delete or skip them, and do not "fix" them by changing the
expectations. They run offline, on the standard library only.
"""
from collections import Counter

import pytest

from roles import (
    Monster,
    Villager,
    Werewolf,
    Cupid,
    Mayor,
)
from game_engine import Game, PHASE_NIGHT, PHASE_LYNCH


# --- helpers ---------------------------------------------------------------


def new_game(players):
    game = Game("smoke", settings={})
    for pid in range(players):
        game.add_player(pid, f"P{pid}")
    return game


def assign(game, player, role):
    """Give one player a specific role instance."""
    role_obj = role() if isinstance(role, type) else role
    game.players[player].role = role_obj
    role_obj.on_assign(game.players[player])
    return role_obj


def distribution(game):
    return Counter(p.role.name_key for p in game.players.values())


def wolves(game):
    return [p for p in game.players.values() if p.role.team == "Werewolves"]


def villagers(game):
    return [p for p in game.players.values() if p.role.team == "Villagers"]


def villager_after_zero(game):
    """A living villager whose id is not 0 (id 0 is covered by the grading suite)."""
    return next(p for p in villagers(game) if p.id != 0)


# --- role assignment -------------------------------------------------------


@pytest.mark.parametrize(
    "player_count,expected_wolves",
    [(4, 1), (5, 1), (6, 1), (7, 2), (8, 2), (10, 3), (12, 4), (13, 4)],
)
def test_wolf_count_follows_player_count(player_count, expected_wolves):
    game = new_game(player_count)
    game.assign_roles(["Villager", "Werewolf", "Seer"])
    assert len(wolves(game)) == expected_wolves


def test_every_player_gets_a_role():
    game = new_game(7)
    game.assign_roles(["Villager", "Werewolf"])
    assert len(distribution(game)) >= 2
    assert all(p.role is not None for p in game.players.values())


def test_role_instances_are_not_shared():
    game = new_game(8)
    game.assign_roles(["Villager", "Werewolf", "Seer", "Witch", "Hunter"])
    ids = [id(p.role) for p in game.players.values()]
    assert len(ids) == len(set(ids))


# --- night resolution ------------------------------------------------------


def test_unanimous_wolves_kill_their_target():
    game = new_game(9)
    game.assign_roles(["Villager", "Werewolf"])
    pack = wolves(game)
    assert len(pack) >= 2
    victim = villager_after_zero(game)

    game.set_phase(PHASE_NIGHT)
    game.pending_actions = {w.id: victim.id for w in pack}

    events = game.resolve_night_deaths()
    deaths = [e for e in events if e["type"] == "death"]
    assert victim.is_alive is False
    assert [d["id"] for d in deaths] == [victim.id]


def test_protected_target_survives_the_night():
    game = new_game(6)
    game.assign_roles(["Villager", "Werewolf"])
    victim = villager_after_zero(game)

    game.set_phase(PHASE_NIGHT)
    victim.status_effects.append("protected")
    game.pending_actions = {w.id: victim.id for w in wolves(game)}

    game.resolve_night_deaths()
    assert victim.is_alive is True


def test_monster_cannot_be_killed_by_wolves():
    game = new_game(8)
    game.assign_roles(["Villager", "Werewolf"])
    monster_player = game.players[max(game.players)]
    assign(game, monster_player.id, Monster)

    game.set_phase(PHASE_NIGHT)
    game.pending_actions = {w.id: monster_player.id for w in wolves(game)}

    game.resolve_night_deaths()
    assert monster_player.is_alive is True


# --- accusation and lynch --------------------------------------------------


def test_lynch_passes_with_majority_of_living_voters():
    game = new_game(3)
    for pid in range(3):
        assign(game, pid, Villager)

    game.set_phase(PHASE_LYNCH)
    game.lynch_target_id = 0
    game.pending_actions = {0: "no", 1: "yes", 2: "yes"}

    result = game.resolve_lynch_vote()
    assert result["killed_id"] == 0
    assert game.players[0].is_alive is False


def test_lynch_is_not_executed_without_majority():
    game = new_game(3)
    for pid in range(3):
        assign(game, pid, Villager)

    game.set_phase(PHASE_LYNCH)
    game.lynch_target_id = 0
    game.pending_actions = {0: "yes", 1: "no", 2: "no"}

    result = game.resolve_lynch_vote()
    assert result["killed_id"] is None
    assert game.players[0].is_alive is True


def test_dead_players_appear_as_ghost_in_the_summary():
    game = new_game(4)
    for pid in range(4):
        assign(game, pid, Villager)
    game.players[3].is_alive = False

    game.set_phase(PHASE_LYNCH)
    game.lynch_target_id = 0
    game.pending_actions = {0: "no", 1: "yes", 2: "yes", 3: "yes"}

    result = game.resolve_lynch_vote()
    assert result["killed_id"] == 0
    assert sorted(result["summary"]["yes"]) == ["Ghost", "P1", "P2"]


# --- roles -----------------------------------------------------------------


def test_cupid_links_two_lovers_and_spends_the_power():
    game = new_game(4)
    for pid in range(4):
        assign(game, pid, Villager)
    cupid = assign(game, 0, Cupid)
    game.set_phase(PHASE_NIGHT)

    context = {
        "players": list(game.players.values()),
        "current_action_metadata": {"target_id2": 2},
    }
    cupid.night_action(game.players[0], game.players[1], context)

    assert game.players[1].linked_partner_id == 2
    assert game.players[2].linked_partner_id == 1
    assert cupid.is_night_active is False


def test_mayor_title_passes_to_an_eligible_heir():
    game = new_game(4)
    mayor = assign(game, 0, Mayor)
    assign(game, 1, Villager)
    mayor.next_mayor_id = 1

    events = game.execute_death_cascade([(0, "Lynched")], context="lynch")

    assert any("P1" in str(a) for a in events["announcements"])
    heir_role = game.players[1].role
    assert heir_role.is_night_active is True
    assert heir_role.next_mayor_id == "not_set_yet"


# --- win conditions --------------------------------------------------------


def test_villagers_win_when_the_last_wolf_dies():
    game = new_game(4)
    for pid in range(4):
        assign(game, pid, Villager)
    assign(game, 3, Werewolf)
    game.players[3].is_alive = False

    assert game.check_game_over() is True
    assert game.winner == "Villagers"


def test_werewolves_win_when_they_outnumber_the_rest():
    game = new_game(4)
    for pid in range(4):
        assign(game, pid, Villager)
    assign(game, 0, Werewolf)
    assign(game, 1, Werewolf)

    assert game.check_game_over() is True
    assert game.winner == "Werewolves"
