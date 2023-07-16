"""
Routines for reading  various data from an .rpg file/.rpgdir, extending
what rpgbatch provides.
"""

import numpy as np
from ohrk.rpg_const import *

try:
    from nohrio.ohrrpgce import *
    from rpgbatch.rpgbatch import RPGIterator
    import PIL.Image
except ImportError as e:
    print("Running without nohrio+rpgbatch; .rpg inspection not supported: ", e)



def readbit(bytearray, bitnum):
    """Read a single bit from a np.uint8 array"""
    return (bytearray[bitnum // 8] >> (bitnum % 8)) & 1

###########################################################################
#                                   GEN
###########################################################################

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
    gen = game.gen
    #gen = np.frombuffer(game.gen, np.int16)

    battle_mode = ({0:"Active-battle", 1:"Turn-based"}
                   .get(gen[genBattleMode], "UNKNOWN! (%d)" % gen[genBattleMode]))
    version_info = rpg_version_info.get(gen[genVersion], "Unknown!")
    if gen[genVersion] + 1 in rpg_version_info:
        # Add the date of the next version
        version_info += ", until " + rpg_version_info[gen[genVersion] + 1].split()[0]

    ms_per_frame = gen[genMillisecPerFrame] or 55
    if ms_per_frame == 16:
        fps = 60
    elif ms_per_frame == 33:
        fps = 30
    else:
        fps = 1000. / ms_per_frame
    info = [
        ".rpg version: %d (%s)" % (gen[genVersion], version_info),
        "Battle mode: " + battle_mode,
        "Resolution: %dx%d" % (gen[genResolutionX] or 320, gen[genResolutionY] or 200),
        "Frame rate: %.1fFPS" % fps,
    ]
    for key, (genidx, offset, name) in genLimits:
        info.append("Num %s: %d" % (name or key, gen[genidx] + offset))
    return "\n".join(info)


###########################################################################
#                               Titlescreens
###########################################################################


def read_master_palette(rpg, palnum = None):
    "Return a master palette (defaulting to the default) as a list of (r,g,b) triples"
    if rpg.has_lump('palettes.bin'):
        if palnum is None:
            gen = rpg.data('gen')
            palnum = gen['masterpal']

        masterpalette = rpg.data('palettes.bin', offset = 4)[palnum][0]['color']
        colours = [tuple(col.tolist()) for col in masterpalette]
    else:
        # Most .mas files seem to be 1550 bytes in length, with a lot of
        # garbage at the end
        masterpalette = rpg.data('mas', shape = 1)[0]['color']
        def scale(x):
            # magnus.rpg has garbage in MAS
            return max(0, min(255, x * 4 + x // 16))
        colours = []
        for col in masterpalette:
            colours.append((scale(col['r']), scale(col['g']), scale(col['b'])))
    return colours

def read_mxs(rpg, lumpname, index):
    """Returns a 200*320 numpy array with pixel data.
    lumpname should be 'mxs' for backdrops or 'til' for tilesets."""
    mxs = rpg.data(lumpname)
    if index < 0 or index >= len(mxs):
        print(".msx index %d out of range, only %d backdrops" % (index, len(mxs)))
        return None
    record = mxs[index]['planes'].reshape((4,200,80))
    ret = np.empty((200,320), dtype = np.uint8)
    for plane in range(4):
        ret[:, plane::4] = record[plane]
    return ret

def save_paletted_image(pixels, palette, filename):
    """Write an image file.
    pixels: a h*w array of palette indices
    palette: a list of 256 (r,g,b) triples
    """
    im = PIL.Image.fromarray(pixels, 'P')
    im.putpalette(sum(palette, ()))
    im.save(filename)

def save_titlescreen(rpg, filename):
    """Save a title screen to a file and return True, or False if "Skip title screen" is on."""
    try:
        gen = rpg.data('gen')
        if readbit(gen['bitsets'][0], 11):  # Skip titlescreen
            print("No titlescreen")
            return False
        else:
            title = read_mxs(rpg, 'mxs', gen['title'])
            if title is None:
                return False
            pal = read_master_palette(rpg)
            save_paletted_image(title, pal, filename)
            return True
    except IOError as e:
        print("! save_titlescreen failed:", e)
        return False


###########################################################################
#                                Similarity
###########################################################################
