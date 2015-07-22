from .SecretSpells import SecretSpells
import SaveIO
from requests import HTTPError


class SpellManager:
    def __init__(self):
        self.spellQueue = {}
        self.earnedSpells = {}
        self.c = None
        self.secret_spells = None
        self.secret_spells = SecretSpells()
        self.bot_user_id = -1
        self.secret_spells.init()

    def award(self, spell_id, user_id, queue):
        if user_id == self.bot_user_id:
            return False  # don't give the bot spells
        try:
            if queue:
                self.append_to_queue(user_id, spell_id)
            else:
                if spell_id >= len(self.secret_spells.spellList):
                    return "Index out of range."
                if user_id not in self.earnedSpells:
                    self.earnedSpells[user_id] = []
                if spell_id not in self.earnedSpells[user_id]:
                    self.earnedSpells[user_id].append(spell_id)
                    u = self.c.get_user(user_id)
                    n = u.name
                    n = "".join(n.split())
                    self.save()
                    return "Congratulations, @%s, you have earned a new spell: %s" % (n, self.secret_spells.spellList[spell_id])
                return "This spell was already awarded."
        except IndexError:
            return "Index out of range."
        except:
            return "Error"

    def remove(self, user_id, spell):
        if user_id in self.earnedSpells:
            if spell in self.earnedSpells[user_id]:
                self.earnedSpells[user_id].remove(spell)

    def save(self):
        SaveIO.save(self.earnedSpells, "shadowsden", "earnedSpells")

    def load(self):
        self.earnedSpells = SaveIO.load("shadowsden", "earnedSpells")

    def get_spell_by_index(self, i):
        return self.secret_spells.spellList[i]

    def view_spells(self, user_id):
        try:
            u = self.c.get_user(user_id)
        except HTTPError:
            return "Could not find that user."
        n = u.name
        if user_id not in self.earnedSpells:
            return "%s has not earned any spells yet." % n
        else:
            spell_names = map(self.get_spell_by_index, self.earnedSpells[user_id])
            spell_names_str = ", ".join(spell_names)
            return "%s has earned the following spells: %s" % (n, spell_names_str)

    def check_spells(self, event):
        for m in self.secret_spells.spellMethods:
            checked_spell = m(event)
            if checked_spell is not False:
                self.append_to_queue(checked_spell[0], checked_spell[1])

    def append_to_queue(self, user, spell):
        if user not in self.spellQueue:
            self.spellQueue[user] = {}
        self.spellQueue[user][spell] = True
        return "Spell added to queue."

    def empty_queue(self):
        ret = []
        to_be_popped = []
        for user in self.spellQueue.keys():
            for key, value in self.spellQueue[user].iteritems():
                if value is True:
                    ret.append(self.award(key, user, False))
                    to_be_popped.append((user, key))
        for popThis in to_be_popped:
            self.spellQueue[popThis[0]].pop(popThis[1], None)
        return ret
