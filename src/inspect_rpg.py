"""
Routines for reading information out of game data
"""

from util import py2
from rpg_const import *


# Description of each genVersion value
rpg_version_info = {
    0: "1998 Super-ancient format",
    1: "1998 ancient format",
    2: "1999-06-18",
    3: "1999-07-08",
    4: "2000-09-15",
    5: "2001-03-31",
    6: "2006-02-13 serendipity", # MIDI music, shop stuff
    7: "2008-11-21 ypsiliform", # wip added > 36 NPC defs (and many other features)
    8: "2009-09-23 ypsiliform", # wip added extended chaining data (and many other features)
    9: "2009-10-20 ypsiliform", # wip added text box sound effects
    10: "2009-12-11 ypsiliform", # wip added attack-based enemy transmogrification
    11: "2010-07-28 zenzizenzic", # wip added variable record size and record number .N## lumps
    12: "2010-10-20 zenzizenzic", # wip increased .N## record size
    13: "2010-12-30 zenzizenzic", # wip changed password format to PW4, older versions have broken genPassVersion handling
    14: "2011-01-05 zenzizenzic", # wip made .DT0 binsize-sized
    15: "2011-01-20 zenzizenzic", # wip made .DT1 binsize-sized, and added binsize.bin, fixbits.bit safeguards
    16: "2011-01-20 zenzizenzic", # wip made .ITM binsize-sized
    17: "2012-02-08 alectormancy", # wip increase global limit from 4095 to 16383
    18: "2012-12-06 beelzebufo", # turn-based support
    19: "2012-12-21 beelzebufo", # replaced .dt0 with heroes.reld
    19: "2012-12-21 beelzebufo", # replaced .DT0 with heroes.reld
    20: "2016-03-19 callipygous", # release. Added general.reld (including new version system) and maxScriptCmdID checking.
}

genLimits = (
    ("maps",           (genMaxMap,          1, "")),
    ("textboxes",      (genMaxTextbox,      1, "")),
    ("attacks",        (genMaxAttack,       1, "")),
    ("heroes",         (genMaxHero,         1, "")),
    ("enemies",        (genMaxEnemy,        1, "")),
    ("formations",     (genMaxFormation,    1, "")),
    ("palettes",       (genMaxPal,          1, "")),
    ("masterpals",     (genMaxMasterPal,    1, "master palettes")),
    ("scripts",        (genNumPlotscripts,  0, "")),
    ("vehicles",       (genMaxVehicle,      1, "")),
    ("numtags",        (genMaxTagname,      1, "tags")),   # Not to be confused with Game.tag,
    ("sfx",            (genMaxSFX,          1, "")),
    ("songs",          (genMaxSong,         1, "")),
    ("menus",          (genMaxMenu,         1, "")),
    ("items",          (genMaxItem,         1, "")),
    ("elements",       (genNumElements,     0, "")),

    ("herogfx",        (genMaxHeroPic,      1, "hero graphics")),
    ("smallenemygfx",  (genMaxEnemy1Pic,    1, "small enemy graphics")),
    ("mediumenemygfx", (genMaxEnemy2Pic,    1, "medium enemy graphics")),
    ("largeenemygfx",  (genMaxEnemy3Pic,    1, "large enemy graphics")),
    ("walkaboutgfx",   (genMaxNPCPic,       1, "walkabout graphics")),
    ("weapongfx",      (genMaxWeaponPic,    1, "weapon graphics")),
    ("attackgfx",      (genMaxAttackPic,    1, "attack graphics")),
    ("bordergfx",      (genMaxBoxBorder,    1, "border graphics")),
    ("portraitgfx",    (genMaxPortrait,     1, "portrait graphics")),
    ("backdrops",      (genNumBackdrops,    0, "")),
    ("tilesets",       (genMaxTile,         1, "")),
)

genLimitsDict = dict(genLimits)

def get_gen_info(game):
    """
    Return a string telling some information extracted from the .gen lump,
    given a gamedb.Game object.
    """
    gen = game.gen.as_array()

    battle_mode = ({0:"Active-battle", 1:"Turn-based"}
                   .get(gen[genBattleMode], "UNKNOWN! (%d)" % gen[genBattleMode]))
    version_info = rpg_version_info.get(gen[genVersion], "Unknown!")
    if gen[genVersion] + 1 in rpg_version_info:
        # Add the date of the next version
        version_info += ", until " + rpg_version_info[gen[genVersion] + 1].split()[0]

    info = [
        ".rpg version: %d (%s)" % (gen[genVersion], version_info),
        "Battle mode: " + battle_mode,
        "Resolution: %dx%d" % (gen[genResolutionX] or 320, gen[genResolutionY] or 200),
        "Frame rate: %.1fFPS" % (1000. / (gen[genMillisecPerFrame] or 55)),
    ]
    for key, (genidx, offset, name) in genLimits:
        info.append("Num %s: %d" % (name or key, gen[genidx] + offset))
    return "\n".join(info)
