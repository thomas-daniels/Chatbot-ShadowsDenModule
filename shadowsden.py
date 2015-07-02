import pickle
import re
from ChatExchange.chatexchange.messages import Message
from ChatExchange.chatexchange.events import MessagePosted
from SpellManager import SpellManager
import os
import time
import random
from GetAssociatedWord import get_associated_word
import thread
from Module import Command
from HTMLParser import HTMLParser


class Data:
    links = []
    waiting_time = -1
    latest_word_id = -1
    current_word_to_reply_to = ""
    latest_words = []
    spell_manager = SpellManager()
    link_explanations = []
    msg_id_no_reply_found = -1


def scheduled_empty_queue(bot):
    while bot.running:
        time.sleep(15 * 60)
        awarded = Data.spell_manager.empty_queue()
        for s in awarded:
            if bot.room is not None and s != "This spell was already awarded."\
                    and s is not False:
                bot.room.send_message(s)
            else:
                print s


def reply_word(bot, message, wait, orig_word):
    if orig_word in Data.latest_words:
        message.reply("That word is already said in the latest 10 words. "
                      "Please use another. (In case I'm mistaken, "
                      "run `>>rmword %s` and then `>>reply %s`)"
                      % (orig_word, message.id))
        return
    Data.current_word_to_reply_to = orig_word
    if wait and Data.waiting_time > 0:
        time.sleep(Data.waiting_time)
    if Data.current_word_to_reply_to != orig_word:
        return
    word_tuple = find_associated_word(orig_word)
    word = word_tuple[0]
    word_found = word_tuple[1]
    if word is None and not word_found:
        bot.room.send_message("No associated word found for %s." % orig_word)
        Data.msg_id_no_reply_found = message.id
    elif word is None and word_found:
        bot.room.send_message("Associated words found for %s, but all of them have been posted in the latest 10 messages." % orig_word)
        Data.msg_id_no_reply_found = -1
    else:
        Data.msg_id_no_reply_found = -1
        message.reply(word)


def find_associated_word(word):
        latest_words_no_save = Data.latest_words[:]
        latest_words_no_save.append(word.lower())
        # Create a temp list. Adding the word to the list of the class
        # should only happen if an associated word is found.
        get_word = get_associated_word(word, latest_words_no_save)
        word_to_reply = get_word[0]
        word_found = get_word[1]
        if word_to_reply is None:
            found_links = find_links(word)
            valid_found_links = []
            if len(found_links) > 0:
                word_found = True
            for link in found_links:
                if link not in Data.latest_words:
                    valid_found_links.append(link)
            if len(valid_found_links) > 0:
                word_to_reply = random.choice(valid_found_links)
        if word_to_reply is not None:
            add_word_to_latest_words(word)
            add_word_to_latest_words(word_to_reply)
        return word_to_reply, word_found


def add_word_to_latest_words(word):
    Data.latest_words.insert(0, word.lower())
    if len(Data.latest_words) > 10:
        Data.latest_words.pop()


def command_time(cmd, bot, args, msg, event):
    if len(args) > 0:
        try:
            new_time = int(args[0])
            if new_time > 600:
                return "Waiting time cannot be greater than 10 minutes (= 600 seconds)."
            if new_time > -1:
                Data.waiting_time = new_time
                f = open("config.txt", "w")
                f.write(str(Data.waiting_time))
                f.close()
                return "Waiting time set to %s %s." % (args[0], ("seconds" if new_time != 1 else "second"))
            else:
                return "Given argument has to be a positive integer."
        except ValueError:
            return "Given argument is not a valid integer."
    else:
        return "Command does not have enough arguments."


def command_viewspells(cmd, bot, args, msg, event):
    if len(args) < 1:
        return "Not enough arguments."
    try:
        user_id = int(args[0])
    except ValueError:
        return "Invalid arguments."
    spells = Data.spell_manager.view_spells(user_id)
    return spells


def command_latestword(cmd, bot, args, msg, event):
    lwi = Data.latest_word_id
    if lwi != -1:
        return "http://chat.meta.stackexchange.com/transcript/message/%s#%s" % (lwi, lwi)
    else:
        return "I don't know."


def command_setlatestword(cmd, bot, args, msg, event):
    if len(args) != 1:
        return "1 argument expected, %i given" % (len(args),)
    try:
        new_lwi = int(args[0])
        Data.latest_word_id = new_lwi
        return "Latest word set."
    except ValueError:
        return "Given argument is not an integer."


def command_showlatest10(cmd, bot, args, msg, event):
    l = len(Data.latest_words)
    return "Latest %s %s: %s" % (l, "words" if l != 1 else "word",
                                    ", ".join(Data.latest_words))


def command_rmword(cmd, bot, args, msg, event):
    if len(args) != 1:
        return "1 argument expected, %i given" % (len(args),)
    word = args[0]
    if word in Data.latest_words:
        Data.latest_words = filter(lambda l: l != word, Data.latest_words)
        return "Word removed from latest words."
    else:
        return "Word not in the list of latest words."


def command_showtime(cmd, bot, args, msg, event):
    return "Waiting time: %i seconds." % Data.waiting_time


def command_link(cmd, bot, args, msg, event):
    if len(args) != 2:
        return "2 arguments expected, %i given." % len(args)
    if links_contain((args[0].replace("_", " "), args[1].replace("_", " "))):
        return "Link is already added."
    Data.links.append((args[0].replace("_", " "), args[1].replace("_", " ")))
    with open("linkedWords.txt", "w") as f:
        pickle.dump(Data.links, f)
    return "Link added."


def command_islink(cmd, bot, args, msg, event):
    if len(args) != 2:
        return "2 arguments expected, %i given" % len(args)
    if links_contain((args[0].replace("_", " "), args[1].replace("_", " "))):
        return "Yes, that's a manually added link."
    else:
        return "No, that's not a link."


def removelinkexplanation(link):
    to_remove = []
    ret = False
    for exp in Data.link_explanations:
        l = exp[0]
        if (l[0] == link[0] and l[1] == link[1]) or (l[0] == link[1] and l[1] == link[0]):
            to_remove.append(exp)
            ret = True
    for r in to_remove:
        Data.link_explanations.remove(r)
    with open("linkExplanations.txt", "w") as f:
        pickle.dump(Data.link_explanations, f)
    return ret


def command_addlinkexplanation(cmd, bot, args, msg, event):
    if len(args) != 3:
        return "3 arguments expected, %i given" % len(args)
    w1 = args[0].replace("_", " ").lower()
    w2 = args[1].replace("_", " ").lower()
    removelinkexplanation((w1, w2))  # remove any older explanations
    if not links_contain((w1, w2)):
        return "That link does not exist."
    if re.compile(r"[^a-zA-Z0-9_%*/:.#()\[\]?&=-]").search(args[2]):
        return "Sorry, your explanation can only contain the chars `a-zA-Z_*%/:.#()[]-`."
    Data.link_explanations.append(((w1, w2), args[2]))
    with open("linkExplanations.txt", "w") as f:
        pickle.dump(Data.link_explanations, f)
    return "Explanation added."


def command_explainlink(cmd, bot, args, msg, event):
    if len(args) != 2:
        return "2 arguments expected, %i given" % len(args)
    w1 = args[0].replace("_", " ").lower()
    w2 = args[1].replace("_", " ").lower()
    if not links_contain((w1, w2)):
        return "Words not linked."
    for exp in Data.link_explanations:
        link = exp[0]
        explanation = exp[1]
        if (link[0] == w1 and link[1] == w2) or (link[1] == w1 and link[0] == w2):
            return explanation
    return "No explanation found."


def command_removelinkexplanation(cmd, bot, args, msg, event):
    if len(args) != 2:
        return "2 argumens expected, %i given" % len(args)
    w1 = args[0].replace("_", " ").lower()
    w2 = args[1].replace("_", " ").lower()
    if removelinkexplanation((w1, w2)):
        return "Explanation removed."
    else:
        return "No explanation found to remove."


def command_reply(cmd, bot, args, msg, event):
    if len(args) < 1:
        return "Not enough arguments."
    try:
        msg_id_to_reply_to = int(args[0])
    except ValueError:
        if args[0] == "recent":
            msg_id_to_reply_to = Data.msg_id_no_reply_found
        else:
            return "Invalid arguments."
        if msg_id_to_reply_to == -1:
            return "'recent' has a value of -1, which is not a valid message ID. Please provide an explicit ID."
    msg_to_reply_to = Message(msg_id_to_reply_to, bot.client)
    content = msg_to_reply_to.content_source
    content = re.sub(r"([:;][-']?[)/(DPdpoO\[\]\\|])", "", content)  # strip smilies
    content = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", content)
    content = re.sub(r"\(.+?\)", "", content)
    content = re.sub(r"\s+", " ", content)
    content = content.strip()
    parts = content.split(" ")
    msg_does_not_qualify = "Message does not qualify as a message that belongs to the word association game."
    if len(parts) != 2:
        return msg_does_not_qualify
    if not re.compile("^:([0-9]+)$").search(parts[0]):
        return msg_does_not_qualify
    if re.compile("[^a-zA-Z0-9-]").search(parts[1]):
        return "Word contains invalid characters."
    reply_word(bot, msg_to_reply_to, False, parts[1])
    return None


def command_continue(cmd, bot, args, msg, event):
    if len(args) != 2:
        return "2 arguments expected, %i given." % (len(args),)
    command_link(cmd, bot, args, None, None)
    return command_reply(None, bot, ["recent"], None, None)


def command_retry(cmd, bot, args, msg, event):
    return command_reply(None, bot, ["recent"], None, None)


def command_removelink(cmd, bot, args, msg, event):
    if len(args) < 2:
        return "Not enough arguments."
    w1 = args[0].replace("_", " ").lower()
    w2 = args[1].replace("_", " ").lower()
    removelinkexplanation((w1, w2))
    return remove_link(args[0].replace("_", " "), args[1].replace("_", " "))


def links_contain(item):
    for link in Data.links:
        lowercase_link = (link[0].lower(), link[1].lower())
        if item[0].lower() in lowercase_link and item[1].lower() in lowercase_link:
            return True
    return False


def find_links(item):
    results = []
    for link in Data.links:
        lowercase_link = (link[0].lower(), link[1].lower())
        lowercase_item = item.lower()
        if lowercase_item in lowercase_link:
            i = lowercase_link.index(lowercase_item)
            associated_index = 0 if i == 1 else 1
            results.append(link[associated_index])
    return results


def remove_link(item0, item1):
    for i, link in enumerate(Data.links):
        lowercase_link = (link[0].lower(), link[1].lower())
        if item0.lower() in lowercase_link and item1.lower() in lowercase_link:
            Data.links.pop(i)
            with open("linkedWords.txt", "w") as f:
                pickle.dump(Data.links, f)
            return "Link removed."
    return "No link found."


def command_award(cmd, bot, args, msg, event):
    if len(args) < 3:
        return "Not enough arguments."
    try:
        spell_id = int(args[0])
        user_id = int(args[1])
    except ValueError:
        return "Not a valid id."
    if args[2] == "-n":
        add_to_queue = False
    elif args[2] == "-q":
        add_to_queue = True
    else:
        return "Invalid arguments."
    return Data.spell_manager.award(spell_id, user_id, add_to_queue)


def command_removespell(cmd, bot, args, msg, event):
    Data.spell_manager.remove(int(args[1]), int(args[0]))
    return "Spell removed (un-awarded)."


def command_emptyqueue(self, args, msg, event):
    awarded = self.spell_manager.empty_queue()
    for s in awarded:
        if self.room is not None:
            self.room.send_message(s)
        else:
            print s


def on_bot_load(bot):
    if os.path.isfile("config.txt"):  # config.txt is for values that can change at runtime, Config.py is for static data
        f = open("config.txt", "r")
        Data.waiting_time = int(f.read())
        f.close()
    else:
        f = open("config.txt", "w")
        f.write("20")
        f.close()
    if os.path.isfile("linkedWords.txt"):
        with open("linkedWords.txt", "r") as f:
            Data.links = pickle.load(f)
    Data.spell_manager.c = bot.client
    thread.start_new_thread(scheduled_empty_queue, (bot,))


def on_event(event, client, bot):
    if not isinstance(event, MessagePosted) or not bot.enabled:
        return
    message = event.message
    h = HTMLParser()
    content = h.unescape(message.content_source)
    content = re.sub(r"([:;][-']?[)/(DPdpoO\[\]\\|])", "", content)  # strip smilies
    content = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", content)
    content = re.sub(r"\(.+?\)", "", content)
    content = re.sub(r"\s+", " ", content)
    content = content.strip()
    if not re.compile("^:\d+ [a-zA-Z0-9-]+$").search(content):
        return
    if event.user.id == bot.client.get_me().id:
        Data.current_word_to_reply_to = content.split(" ")[1]
        Data.latest_word_id = message.id
        return
    parts = content.split(" ")
    c = parts[1]
    Data.latest_word_id = message.id
    thread.start_new_thread(reply_word, (bot, message, True, c))

commands = [
    Command('time', command_time, "", False, False),
    Command('showtime', command_showtime, "", False, False),
    Command('link', command_link, "", False, False),
    Command('islink', command_islink, "", False, False),
    Command('removelink', command_removelink, "", False, False),
    Command('addlinkexplanation', command_addlinkexplanation, "", False, False, False),
    Command('explainlink', command_explainlink, "", False, False),
    Command('removelinkexplanation', command_removelinkexplanation, "", False, False),
    Command('viewspells', command_viewspells, "", False, False),
    Command('showlatest10', command_showlatest10, "", False, False),
    Command('latestword', command_latestword, "", False, False),
    Command('lastword', command_latestword, "", False, False),
    Command('setlatestword', command_setlatestword, "", False, False),
    Command('rmword', command_rmword, "", False, False),
    Command('reply', command_reply, "", False, False),
    Command('retry', command_retry, "", False, False),
    Command('continue', command_continue, "", False, False),
    Command('award', command_award, "", False, True),
    Command('emptyqueue', command_award, "", False, True),
    Command('removespell', command_removespell, "", False, True)
]
