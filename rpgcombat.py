import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button
import random
import os
import json
import uuid
import importlib
from rpgai import resolve_ai

from globals import GUILD_ID, COMBATS_FILE, ENEMIES_FILE, RPG_ITEMS_FILE
from rpgutils import rpg_load_data, rpg_save_data, add_to_graveyard, apply_damage_modifiers
from rpgparties import load_parties
import rpgskills
import asyncio

# In-memory storage for combat scenes keyed by unique combat ID
combat_scenes = {}

class CombatScene:
    def __init__(self, data=None):
        if data:
            self.friendly_frontline = data.get('friendly_frontline', [])
            self.friendly_backline = data.get('friendly_backline', [])
            self.enemy_frontline = data.get('enemy_frontline', [])
            self.enemy_backline = data.get('enemy_backline', [])
            self.initiative_order = data.get('initiative_order', {})
            self.turn_order = data.get('turn_order', [])
            self.current_turn_index = data.get('current_turn_index', 0)
            self.actions_used = data.get('actions_used', {})
            self.enemies_data = data.get('enemies_data', {})
            self.hp_map = data.get('hp_map', {})
            self.hp_range_map = data.get('hp_range_map', {})
            self.xp_range_map = data.get('xp_range_map', {})
            self.graveyard_friendly = data.get('graveyard_friendly', [])
            self.graveyard_enemy = data.get('graveyard_enemy', [])
            self.cooldowns = data.get('cooldowns', {})
            self.conditions = data.get('conditions', {})
            self.log = data.get('log', []) if data else []

        else:
            self.friendly_frontline = []
            self.friendly_backline = []
            self.enemy_frontline = []
            self.enemy_backline = []
            self.initiative_order = {}
            self.turn_order = []
            self.current_turn_index = 0
            self.actions_used = {}
            self.enemies_data = {}
            self.hp_map = {}
            self.hp_range_map = {}
            self.xp_range_map = {}
            self.graveyard_friendly = []
            self.graveyard_enemy = []
            self.cooldowns = {}  # key: uid, value: dict {skill: turns left}
            self.conditions = {}  # key: uid, value: dict {condition: turns left

    def to_dict(self):
        return {
            'friendly_frontline': self.friendly_frontline,
            'friendly_backline': self.friendly_backline,
            'enemy_frontline': self.enemy_frontline,
            'enemy_backline': self.enemy_backline,
            'initiative_order': self.initiative_order,
            'turn_order': self.turn_order,
            'current_turn_index': self.current_turn_index,
            'actions_used': self.actions_used,
            'enemies_data': self.enemies_data,
            'hp_map': self.hp_map,
            'hp_range_map': self.hp_range_map,
            'xp_range_map': self.xp_range_map,
            'graveyard_friendly': self.graveyard_friendly,
            'graveyard_enemy': self.graveyard_enemy,
            'cooldowns': self.cooldowns,
            'conditions': self.conditions,
            'log': self.log,
        }

# Persistence helpers

def load_combats():
    try:
        with open(COMBATS_FILE, 'r') as f:
            data = json.load(f)
        return {cid: CombatScene(cd) for cid, cd in data.items()}
    except:
        return {}


def save_combats():
    with open(COMBATS_FILE, 'w') as f:
        json.dump({cid: scene.to_dict() for cid, scene in combat_scenes.items()}, f, indent=2)

combat_scenes = load_combats()

# Death and cleanup

def check_deaths(scene: CombatScene) -> str | None:
    # Move any dead tokens into the proper graveyard
    for lst, grave, is_player in [
        (scene.friendly_frontline, scene.graveyard_friendly, True),
        (scene.friendly_backline,  scene.graveyard_friendly, True),
        (scene.enemy_frontline,    scene.graveyard_enemy,    False),
        (scene.enemy_backline,     scene.graveyard_enemy,    False),
    ]:
        for uid in lst.copy():
            if scene.hp_map.get(uid, 1) <= 0:
                lst.remove(uid)
                grave.append(uid)

                # If it’s a player, log+backup+remove via add_to_graveyard
                if is_player:
                    # use the last attacker as killer if stored, or "Unknown"
                    killer = getattr(scene, '_last_attacker', None) or "Unknown"
                    add_to_graveyard(uid, killer)

    # Purge dead from initiative & turn order
    dead = set(scene.graveyard_friendly + scene.graveyard_enemy)
    scene.turn_order = [u for u in scene.turn_order if u not in dead]
    for u in dead:
        scene.initiative_order.pop(u, None)
        scene.actions_used.pop(u, None)

    # Check for a full wipe
    players_alive = bool(scene.friendly_frontline or scene.friendly_backline)
    enemies_alive = bool(scene.enemy_frontline    or scene.enemy_backline)
    if not enemies_alive:
        return 'players'
    if not players_alive:
        return 'enemies'
    return None


def tick_effects(scene, send_fn):
    for uid, conds in list(scene.conditions.items()):
        new_conds = {}

        for name, turns in conds.items():
            cond_fn = getattr(rpgskills, name, None)
            if cond_fn:
                try:
                    result = cond_fn(scene, uid)
                    if result:
                        send_fn(result)
                except Exception as e:
                    send_fn(f"⚠️ Error applying condition `{name}` to {uid}: {e}")
            else:
                send_fn(f"⚠️ Condition `{name}` not found.")

            if turns > 1:
                new_conds[name] = turns - 1

        if new_conds:
            scene.conditions[uid] = new_conds
        else:
            del scene.conditions[uid]
        # --- Tick Cooldowns ---
    for uid, cds in list(scene.cooldowns.items()):
        new_cds = {}
        for skill, turns in cds.items():
            if turns > 1:
                new_cds[skill] = turns - 1
        if new_cds:
            scene.cooldowns[uid] = new_cds
        else:
            del scene.cooldowns[uid]


# UI Elements
class CombatView(View):
    def __init__(self, combat_id: str):
        super().__init__(timeout=None)
        self.combat_id      = combat_id
        self.pending_action = None
        self.pending_side   = None
        self.pending_target = None
        self.pending_side_target = None


        # instantiate components
        self.main_action   = MainActionSelect()
        self.side_action   = SideActionSelect()
        self.target_select = TargetSelect(combat_id)
        self.side_target_select = SideTargetSelect(combat_id)
        self.end_button    = EndTurnButton()

        # ADD them to the view first (this sets Select.view)
        self.add_item(self.main_action)
        self.add_item(self.side_action)
        self.add_item(self.target_select)
        self.add_item(self.side_target_select)
        self.add_item(self.end_button)

        # now that .view is bound, populate options
        self.main_action.refresh_options()
        self.side_action.refresh_options()

    async def resolve_side_action(self, interaction: discord.Interaction) -> str:
        scene = combat_scenes[self.combat_id]
        uid = scene.turn_order[scene.current_turn_index]
        skill = self.pending_side
        target = self.pending_side_target
        cooldowns = scene.cooldowns.get(uid, {})
        if skill in cooldowns:
            return f"{skill.title()} is on cooldown for {cooldowns[skill]} more turns."


        if not skill or skill == "none":
            return "Skipped side action."

        if not target:
            return "No target selected for side action."

        fn = getattr(rpgskills, skill, None)
        if not fn:
            return f"Side action `{skill}` is not implemented."

        result = fn(scene, uid, target)
        scene.actions_used.setdefault(uid, {'action': False, 'side_action': False})['side_action'] = True
        save_combats()
        return result or "Side action executed."

    async def _auto_enemy_turns(self, message: discord.Message):
        """Run all consecutive enemy turns before returning control to the player."""

        scene = combat_scenes[self.combat_id]

        # Run enemy turns in sequence
        while scene.turn_order and scene.turn_order[scene.current_turn_index].startswith("enemy_"):
            uid = scene.turn_order[scene.current_turn_index]
            tick_effects(scene, lambda msg: scene.log.append(msg))
            await message.edit(embed=build_embed(scene), view=self)

            outcome = resolve_ai(scene, uid)
            if not outcome:
                break

            result, _ = outcome
            save_combats()
            scene.log.append(result)
            await message.edit(embed=build_embed(scene), view=self)

            # death check
            wiped = check_deaths(scene)
            if wiped:
                await self._end_combat_from_message(message, wiped == "players")
                return

            # advance to next turn
            scene.current_turn_index = (scene.current_turn_index + 1) % len(scene.turn_order)
            scene.actions_used.setdefault(
                scene.turn_order[scene.current_turn_index],
                {"action": False, "side_action": False}
            )
            save_combats()
            await message.edit(embed=build_embed(scene), view=self)


        # ——— PATCH: Refresh controls for player after enemies finish ———
        if scene.turn_order:
            current_uid = scene.turn_order[scene.current_turn_index]
            if not current_uid.startswith("enemy_"):
                self.main_action.refresh_options()
                self.side_action.refresh_options()
                await message.edit(embed=build_embed(scene), view=self)
        # once you break out, it is now a player’s turn

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        scene = combat_scenes.get(self.combat_id)
        if not scene or not scene.turn_order:
            await interaction.response.send_message('No active combat.', ephemeral=True)
            return False
        current = scene.turn_order[scene.current_turn_index]
        if not current.startswith('enemy_') and str(interaction.user.id) != current:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True
    # Handlers attached to CombatView
    async def on_move(self, interaction: discord.Interaction):
        cid = self.combat_id
        scene = combat_scenes[cid]
        uid = scene.turn_order[scene.current_turn_index]
        if uid in scene.friendly_frontline:
            scene.friendly_frontline.remove(uid)
            scene.friendly_backline.append(uid)
        else:
            scene.friendly_backline.remove(uid)
            scene.friendly_frontline.append(uid)
        scene.actions_used.setdefault(uid, {'action': False, 'side_action': False})['action'] = True
        save_combats()
        embed = build_embed(scene)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_end(self, interaction: discord.Interaction):
        cid    = self.combat_id
        scene  = combat_scenes[cid]
        uid    = scene.turn_order[scene.current_turn_index]
        action = self.pending_action
        tgt    = self.pending_target

        # ——— PLAYER ACTION ———
        if action == 'move':
            # Handle move action
            moved = False
            if uid in scene.friendly_frontline:
                scene.friendly_frontline.remove(uid)
                scene.friendly_backline.append(uid)
                moved = True
                new_position = "backline"
            elif uid in scene.friendly_backline:
                scene.friendly_backline.remove(uid)
                scene.friendly_frontline.append(uid)
                moved = True
                new_position = "frontline"

            if moved:
                result = f"<@{uid}> moved to the {new_position}."
                scene.actions_used[uid]['action'] = True
            else:
                result = "Move action failed. You were not found in either line."
            await interaction.response.send_message(result, ephemeral=True)
        elif action == 'attack' and tgt:
            # 1) Recalc stats with equipment bonuses
            from rpgutils import update_equipment_bonuses_for_user
            update_equipment_bonuses_for_user(uid)

            # 2) Reload character and weapon
            chars   = rpg_load_data()
            char    = chars.get(uid, {})
            raw_wp  = char.get('equipment', {}).get('mainhand', '')
            # normalize key for your JSON structure
            wp_key  = raw_wp.lower().replace(' ', '_')
            items   = json.load(open(RPG_ITEMS_FILE))
            weapon  = items.get('weapons', {}).get(wp_key, {})

            # 3) Compute to-hit bonus
            raw_stat   = weapon.get('stat', 'strength')
            stat_key   = raw_stat.capitalize()
            stat_value = char.get('stats', {}).get(stat_key, 0)
            bonus      = stat_value // 2
            if 'dazed' in scene.conditions.get(uid, {}):
                bonus -= 2
            # 4) Roll attack
            roll  = random.randint(1, 10)
            total = roll + bonus
            armor = scene.enemies_data.get(tgt, {}).get('armor', 10)
            attacker = char.get('name', f'<@{uid}>')
            target   = scene.enemies_data.get(tgt, {}).get('name', tgt)
            res = f"{attacker} attacks {target} ({roll}+{bonus}={total} vs AC {armor}). "

            # 5) Apply damage if hit
            if total >= armor:
                dmg_min = weapon.get('damage', {}).get('min', 1)
                dmg_max = weapon.get('damage', {}).get('max', 1)
                dmg     = random.randint(dmg_min, dmg_max)
                dmg_type = weapon.get('type', 'bludgeoning')  # Default to bludgeoning if unspecified
                final_dmg = apply_damage_modifiers(scene, tgt, dmg, dmg_type)
                scene.hp_map[tgt] -= final_dmg
                scene.hp_map[tgt] = max(scene.hp_map[tgt], 0)
                res += f"Hit! {final_dmg} {dmg_type} damage."
            else:
                res += "Miss!"

            await interaction.response.send_message(res)

            # 6) Check for deaths immediately
            wiped = check_deaths(scene)
            if wiped:
                # handle end-of-combat
                chars = rpg_load_data()
                for uid in scene.friendly_frontline + scene.friendly_backline:
                    if uid in chars:
                        chars[uid]['current_hp'] = scene.hp_map.get(uid, chars[uid].get('current_hp', 0))
                rpg_save_data(chars)  # ← Persist HP

                players_alive = (wiped == 'players')
                # award XP if players won
                if players_alive:
                    players   = [u for u in scene.initiative_order if not u.startswith('enemy_')]
                    total_xp  = sum(random.randint(*scene.xp_range_map[e]) for e in scene.graveyard_enemy)
                    xp_each   = total_xp // len(players) if players else 0
                    chars     = rpg_load_data()
                    for p in players:
                        chars[p]['experience'] = chars[p].get('experience', 0) + xp_each
                    rpg_save_data(chars)
                # final embed + message
                await interaction.message.edit(embed=build_embed(scene), view=None)
                msg = f"Combat ended! +{xp_each} XP" if players_alive else "Your party has fallen…"
                scene.log.append(result)
                await interaction.message.edit(embed=build_embed(scene), view=self)
                # cleanup
                del combat_scenes[cid]
                save_combats()
                return

            # check deaths after side actions too
            wiped = check_deaths(scene)
            if wiped:
                players_alive = (wiped == 'players')
                if players_alive:
                    players   = [u for u in scene.initiative_order if not u.startswith('enemy_')]
                    total_xp  = sum(random.randint(*scene.xp_range_map[e]) for e in scene.graveyard_enemy)
                    xp_each   = total_xp // len(players) if players else 0
                    chars     = rpg_load_data()
                    for p in players:
                        chars[p]['experience'] = chars[p].get('experience', 0) + xp_each
                    rpg_save_data(chars)
                await interaction.message.edit(embed=build_embed(scene), view=None)
                msg = f"Combat ended! +{xp_each} XP" if players_alive else "Your party has fallen…"
                scene.log.append(side_result)
                await interaction.message.edit(embed=build_embed(scene), view=self)
                del combat_scenes[cid]
                save_combats()
                return
        # ——— SIDE ACTION (auto-execute before advancing) ———
        if self.pending_side and not scene.actions_used.get(uid, {}).get('side_action', False):
            if not self.pending_side_target:
                await interaction.channel.send("No side-action target selected.")
            else:
                side_result = await self.resolve_side_action(interaction)
                await interaction.channel.send(side_result)

        # ——— ADVANCE TURN ———
        scene.actions_used[uid] = {'action': False, 'side_action': False}

        # Tick conditions and cooldowns
        tick_effects(scene, lambda msg: scene.log.append(msg))
        await interaction.message.edit(embed=build_embed(scene), view=self)

        # Advance to next turn
        scene.current_turn_index = (scene.current_turn_index + 1) % len(scene.turn_order)

        # Set/reset action flags
        scene.actions_used.setdefault(
            scene.turn_order[scene.current_turn_index],
            {'action': False, 'side_action': False}
        )

        # Refresh options
        current_uid = scene.turn_order[scene.current_turn_index]
        self.main_action.refresh_options()
        self.side_action.refresh_options()
        save_combats()
        await interaction.message.edit(embed=build_embed(scene), view=self)


        # ─── AUTOMATED ENEMY TURNS via centralized AI ───
        while True:
            next_uid = scene.turn_order[scene.current_turn_index]
            if not next_uid.startswith("enemy_"):
                break

            outcome = resolve_ai(scene, next_uid)
            if not outcome:
                break

            result, target = outcome
            save_combats()
            scene.log.append(result)
            await interaction.message.edit(embed=build_embed(scene), view=self)

            # Check for deaths right after each enemy
            wiped = check_deaths(scene)
            if wiped:
                # reuse your existing end-combat cleanup
                await self._end_combat(interaction, xp_win=(wiped=="players"))
                return

            # Advance to next in turn order
            scene.current_turn_index = (scene.current_turn_index + 1) % len(scene.turn_order)
            scene.actions_used.setdefault(
                scene.turn_order[scene.current_turn_index],
                {"action": False, "side_action": False}
            )
            save_combats()
            await interaction.message.edit(embed=build_embed(scene), view=self)

        # ——— RESET FOR NEXT PLAYER ———
        # ─── Persist remaining HP for all surviving PCs ───
        chars = rpg_load_data()
        for uid in scene.friendly_frontline + scene.friendly_backline:
            if uid in chars:
                chars[uid]['current_hp'] = scene.hp_map.get(uid, chars[uid].get('current_hp', 0))
        rpg_save_data(chars)

        # ─── RESET FOR NEXT PLAYER ───
        self.pending_action = None
        self.pending_side   = None
        self.pending_target = None
        self.pending_side_target = None


    async def _end_combat(self, interaction, xp_win: bool):
        cid = self.combat_id
        scene = combat_scenes[cid]

        # give XP only if players won
        if xp_win:
            players   = [u for u in scene.initiative_order if not u.startswith('enemy_')]
            total_xp  = sum(random.randint(*scene.xp_range_map[e]) 
                            for e in scene.graveyard_enemy)
            xp_each   = total_xp // len(players) if players else 0
            chars     = rpg_load_data()
            for p in players:
                chars[p]['xp'] = chars[p].get('xp', 0) + xp_each
            rpg_save_data(chars)

        # final embed (no more view)
        await interaction.message.edit(embed=build_embed(scene), view=None)

        # outcome message
        if xp_win:
            await interaction.channel.send(f"Combat ended! +{xp_each} XP")
        else:
            await interaction.channel.send("Your party has fallen…")

        # cleanup
        del combat_scenes[cid]
        save_combats()
    
    async def _end_combat_from_message(self, message: discord.Message, xp_win: bool):
        """Same as _end_combat but starts from a Message instead of an Interaction."""
        cid = self.combat_id
        scene = combat_scenes[cid]

        # award XP if win
        if xp_win:
            players   = [u for u in scene.initiative_order if not u.startswith("enemy_")]
            total_xp  = sum(random.randint(*scene.xp_range_map[e]) for e in scene.graveyard_enemy)
            xp_each   = total_xp // len(players) if players else 0
            chars     = rpg_load_data()
            for p in players:
                chars[p]["xp"] = chars[p].get("xp", 0) + xp_each
            rpg_save_data(chars)

        # persist PC HPs
        chars = rpg_load_data()
        for uid in scene.friendly_frontline + scene.friendly_backline:
            if uid in chars:
                chars[uid]["current_hp"] = scene.hp_map.get(uid, chars[uid].get("current_hp", 0))
        rpg_save_data(chars)

        # final embed
        await message.edit(embed=build_embed(scene), view=None)
        # final text
        if xp_win:
            await message.channel.send(f"Combat ended! +{xp_each} XP")
        else:
            await message.channel.send("Your party has fallen…")

        # cleanup
        del combat_scenes[cid]
        save_combats()



class MainActionSelect(Select):
    def __init__(self):
        super().__init__(placeholder='Main Action', min_values=1, max_values=1, options=[])

    def refresh_options(self):
        self.options.clear()

        scene = combat_scenes[self.view.combat_id]
        current = scene.turn_order[scene.current_turn_index]

        self.disabled = False
        self.options.append(discord.SelectOption(label='Attack', value='attack'))
        self.options.append(discord.SelectOption(label='Move', value='move'))

        char = rpg_load_data().get(current, {})
        for sk in char.get('action_skills', []):
            func_name = sk.lower().replace(' ', '_')
            label = sk.title()
            self.options.append(discord.SelectOption(label=label, value=func_name))


    async def callback(self, interaction: discord.Interaction):
        self.refresh_options()

        choice = self.values[0]
        scene = combat_scenes[self.view.combat_id]
        current = scene.turn_order[scene.current_turn_index]

        if choice in ['attack', 'move', 'none']:
            self.view.pending_action = choice
            await interaction.response.defer()
            return

        # Check cooldown
        cooldowns = scene.cooldowns.get(current, {})
        if choice in cooldowns:
            await interaction.response.send_message(
                f"⚠️ `{choice.title()}` is on cooldown for {cooldowns[choice]} more turns.",
                ephemeral=True
            )
            return

        self.view.pending_action = choice
        await interaction.response.defer()




class SideActionSelect(Select):
    def __init__(self):
        super().__init__(placeholder='Side Action', min_values=1, max_values=1, options=[])
        self.disabled = False

    def refresh_options(self):
        self.options.clear()
        scene = combat_scenes[self.view.combat_id]
        current = scene.turn_order[scene.current_turn_index]

        self.disabled = False
        self.options.append(discord.SelectOption(
            label="— No Action —",
            value="none",
            description="Skip side action this turn"
        ))

        char = rpg_load_data().get(current, {})
        for sk in char.get('sideaction_skills', []):
            func_name = sk.lower().replace(' ', '_')
            label = sk.title()
            self.options.append(discord.SelectOption(label=label, value=func_name))


    async def callback(self, interaction: discord.Interaction):
        self.refresh_options()

        choice = self.values[0]
        scene = combat_scenes[self.view.combat_id]
        current = scene.turn_order[scene.current_turn_index]

        if choice == 'none':
            self.view.pending_side = None
        else:
            cooldowns = scene.cooldowns.get(current, {})
            if choice in cooldowns:
                await interaction.response.send_message(
                    f"⚠️ `{choice.title()}` is on cooldown for {cooldowns[choice]} more turns.",
                    ephemeral=True
                )
                return

            self.view.pending_side = choice

        await interaction.response.defer()


class TargetSelect(Select):
    def __init__(self, combat_id: str):
        super().__init__(placeholder='Target', min_values=1, max_values=1, options=[])
        self.combat_id = combat_id
        self.refresh_options()

    def refresh_options(self):
        self.options.clear()
        scene = combat_scenes[self.combat_id]
        chars = rpg_load_data()

        # Friendly targets
        for uid in scene.friendly_frontline + scene.friendly_backline:
            name = chars.get(uid, {}).get('name', f'<@{uid}>')
            self.options.append(
                discord.SelectOption(label=name, value=uid)
            )

        # Enemy targets
        for idx, tid in enumerate(scene.enemy_frontline + scene.enemy_backline, start=1):
            ed = scene.enemies_data.get(tid, {})
            # fallback if no 'name' key
            enemy_name = ed.get('name', tid.replace('enemy_', '').replace('_', ' ').title())
            label = f"{enemy_name} #{idx}"
            self.options.append(
                discord.SelectOption(label=label, value=tid)
            )

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_target = self.values[0]
        await interaction.response.defer()


class SideTargetSelect(Select):
    def __init__(self, combat_id: str):
        super().__init__(placeholder='Side Action Target', min_values=1, max_values=1, options=[])
        self.combat_id = combat_id
        self.refresh_options()

    def refresh_options(self):
        self.options.clear()
        scene = combat_scenes[self.combat_id]
        chars = rpg_load_data()

        # Friendly targets
        for uid in scene.friendly_frontline + scene.friendly_backline:
            name = chars.get(uid, {}).get('name', f'<@{uid}>')
            self.options.append(
                discord.SelectOption(label=f"{name}", value=uid)
            )

        # Enemy targets
        for idx, tid in enumerate(scene.enemy_frontline + scene.enemy_backline, start=1):
            ed = scene.enemies_data.get(tid, {})
            enemy_name = ed.get('name', tid.replace('enemy_', '').replace('_', ' ').title())
            label = f"{enemy_name} #{idx}"
            self.options.append(
                discord.SelectOption(label=label, value=tid)
            )

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        self.view.pending_side_target = target
        await interaction.response.defer()


class EndTurnButton(Button):
    def __init__(self):
        super().__init__(label='End Turn', style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await self.view.on_end(interaction)

# Embed builder
def build_embed(scene):
    """
    scene: your CombatScene instance
    """
    from rpgutils import rpg_load_data
    import discord

    chars = rpg_load_data()

    def fmt_line(uids):
        if not uids:
            return "None"
        lines = []
        for uid in uids:
            # Player?
            if isinstance(uid, str) and uid in chars:
                name = chars[uid].get("name", f"<@{uid}>")
            else:
                # Enemy
                ed = scene.enemies_data.get(uid, {})
                name = ed.get("name", uid)
            hp = scene.hp_map.get(uid, 0)
            lines.append(f"{name} (HP: {hp})")
        return "\n".join(lines)

    embed = discord.Embed(
        title="Combat",
        color=discord.Color.dark_red()
    )

    # Friendly / Enemy frontlines & backlines
    embed.add_field(
        name="Friendly Frontline",
        value=fmt_line(scene.friendly_frontline),
        inline=True
    )
    embed.add_field(
        name="Friendly Backline",
        value=fmt_line(scene.friendly_backline),
        inline=True
    )
    embed.add_field(
        name="Enemy Frontline",
        value=fmt_line(scene.enemy_frontline),
        inline=True
    )
    embed.add_field(
        name="Enemy Backline",
        value=fmt_line(scene.enemy_backline),
        inline=True
    )

    # Turn order with initiative and action flags
    order_lines = []
    for uid in scene.turn_order:
        # Skip if dead
        if scene.hp_map.get(uid, 0) <= 0:
            continue

        if isinstance(uid, str) and uid in chars:
            display = chars[uid].get("name", f"<@{uid}>")
        else:
            ed = scene.enemies_data.get(uid, {})
            display = ed.get("name", uid)

        init_val = scene.initiative_order.get(uid, 0)
        used = scene.actions_used.get(uid, {})
        a_flag = "A✓" if used.get("action") else "A "
        s_flag = "S✓" if used.get("side_action") else "S "
        order_lines.append(f"{display} ({init_val}) [{a_flag}/{s_flag}]")

    embed.add_field(
        name="Turn Order",
        value="\n".join(order_lines) if order_lines else "None",
        inline=False
    )
    if scene.log:
        log_text = "\n".join(scene.log[-10:])  # Show last 5 lines
        embed.add_field(name="Recent Actions", value=log_text, inline=False)
    return embed


class CombatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name='combat', description='Start a new combat encounter.')
    async def combat(self, interaction: discord.Interaction):
        # 1) Create a new combat ID and scene
        cid = str(uuid.uuid4())
        scene = CombatScene()
        combat_scenes[cid] = scene

        # 2) Add party members as friendlies
        uid = str(interaction.user.id)
        parties = load_parties()
        leader = next((pid for pid, p in parties.items() if p.get('leader') == uid), None)
        members = parties[leader]['members'] if leader else [uid]
        data = rpg_load_data()
        for u in members:
            ch = data.get(u)
            if not ch:
                continue
            scene.friendly_frontline.append(u)
            scene.hp_map[u] = ch.get('current_hp', ch.get('hp', 0))
            scene.initiative_order[u] = random.randint(1, 10) + ch.get('speed', 0)

        # 3) Load any file‐based enemies (if you still have a list under "enemies" key)
        if os.path.exists(ENEMIES_FILE):
            raw = json.load(open(ENEMIES_FILE))
            file_enemies = raw.get('enemies', None)
            if isinstance(file_enemies, list):
                for idx, e in enumerate(file_enemies):
                    eid = f'enemy_{idx}'
                    scene.enemies_data[eid] = e
                    hp = random.randint(e.get('hp_min', 0), e.get('hp_max', e.get('hp', 0)))
                    scene.hp_map[eid] = hp
                    scene.hp_range_map[eid] = (e.get('hp_min', 0), e.get('hp_max', e.get('hp', 0)))
                    scene.xp_range_map[eid] = (e.get('xp_min', 0), e.get('xp_max', 0))
                    scene.enemy_frontline.append(eid)
                    scene.initiative_order[eid] = random.randint(1, 10) + e.get('speed', 0)

        # 4) Spawn Goblin from enemies.json top‐level "goblin" key
        # ─── Spawn Goblin from enemies.json top‐level "goblin" key ───
        if os.path.exists(ENEMIES_FILE):
            all_cfg   = json.load(open(ENEMIES_FILE))
            goblin_cfg = all_cfg.get('goblin')
            if goblin_cfg:
                # **ensure a name is present**
                goblin_cfg['name'] = goblin_cfg.get('name', 'Goblin')

                eid = 'enemy_goblin'
                scene.enemies_data[eid] = goblin_cfg

                # HP
                hp_min, hp_max = goblin_cfg['hp_min'], goblin_cfg['hp_max']
                scene.hp_map[eid] = random.randint(hp_min, hp_max)
                scene.hp_range_map[eid] = (hp_min, hp_max)

                # XP
                xp_min, xp_max = goblin_cfg.get('xp_min', 0), goblin_cfg.get('xp_max', 0)
                scene.xp_range_map[eid] = (xp_min, xp_max)

                # placement
                if goblin_cfg.get('formation', 'front').lower().startswith('front'):
                    scene.enemy_frontline.append(eid)
                else:
                    scene.enemy_backline.append(eid)

                # initiative
                scene.initiative_order[eid] = random.randint(1, 10) + goblin_cfg.get('speed', 0)


        # 5) Build turn order (highest initiative first) and init action flags
        scene.turn_order = sorted(
            scene.initiative_order.keys(),
            key=lambda u: scene.initiative_order[u],
            reverse=True
        )
        for u in scene.turn_order:
            scene.actions_used[u] = {'action': False, 'side_action': False}

        # 6) Persist, then send embed + view
        save_combats()
        embed = build_embed(scene)
        view  = CombatView(cid)

        # 1) Send the embed + view
        await interaction.response.send_message(f'Combat ID: {cid}', embed=embed, view=view)
        # 2) Grab the sent Message
        msg = await interaction.original_response()

        # If the first actor is an enemy, auto‐run their turns
        first = scene.turn_order[0] if scene.turn_order else None
        if first and first.startswith('enemy_'):
            await asyncio.sleep(0.5)
            await view._auto_enemy_turns(msg)




    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name='formation', description='Set your default combat formation (frontline/backline).')
    @app_commands.describe(position='Choose frontline or backline placement.')
    async def formation(self, interaction: discord.Interaction, position: str):
        pos = position.lower()
        if pos not in ['frontline', 'backline']:
            return await interaction.response.send_message("Invalid position, choose 'frontline' or 'backline'.", ephemeral=True)
        uid = str(interaction.user.id)
        chars = rpg_load_data()
        char = chars.get(uid)
        if not char:
            return await interaction.response.send_message("You don't have a character. Use /create_character first.", ephemeral=True)
        char['formation'] = pos
        rpg_save_data(chars)
        await interaction.response.send_message(f"Default formation set to **{pos}**.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CombatCog(bot))

