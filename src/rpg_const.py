"""
This file is translated from part of const.bi from the OHRRPGCE source code.
It is a list of constants for the .gen (general game data) lump.
"""

genMaxMap = 0             #max map ID
genTitle = 1              #title screen backdrop
genTitleMus = 2           #title music
genVictMus  = 3           #victory music
genBatMus = 4             #default battle music
genPassVersion = 5        #passcode format number
genPW3Rot = 6             #old (third style) passcode rotator
#7-25: first style or third style encoded passcode
genMaxHeroPic = 26        #max hero graphic number in .PT0
genMaxEnemy1Pic = 27      #max small enemy graphic number in .PT1
genMaxEnemy2Pic = 28      #max medium enemy graphic number in .PT2
genMaxEnemy3Pic = 29      #max large enemy graphic number in .PT3
genMaxNPCPic = 30         #max npc graphic number in .PT4
genMaxWeaponPic = 31      #max weapon graphic number in .PT5
genMaxAttackPic = 32      #max attack graphic number in .PT6
genMaxTile = 33           #max tileset number in .TIL
genMaxAttack = 34         #max attack definition number in .DT6
genMaxHero = 35           #max hero definition number in .DT0
genMaxEnemy = 36          #max enemy definition number in .DT1
genMaxFormation = 37      #max formation number in .FOR
genMaxPal = 38            #max palette number in .PAL
genMaxTextbox = 39        #max text box number in .SAY
genNumPlotscripts = 40    #number of scripts of any kind (number of records in PLOTSCR.LST)
genNewGameScript = 41     #id of new-game plotscript
genGameoverScript = 42    #id of game-over plotscript
genMaxRegularScript = 43  #id of highest numbered non-autonumbered plotscript
genSuspendBits = 44       #suspend stuff bits (suspend* constants)
genCameraMode = 45        #camera mode: see the (*cam constants, e.g. herocam)
genCameraArg1 = 46        #
genCameraArg2 = 47        #
genCameraArg3 = 48        #
genCameraArg4 = 49        #
genScrBackdrop = 50       #currently displaying script backdrop in .MXS + 1, 0 for none
genDays = 51              #days of play
genHours = 52             #hours of play
genMinutes = 53           #minutes of play
genSeconds = 54           #seconds of play
genMaxVehicle = 55        #max vehicle type number in .VEH
genMaxTagname = 56        #last named tag
genLoadGameScript = 57    #load-game script
genTextboxBackdrop = 58   #currently displaying text box backdrop in .MXS + 1, 0 for none
genEnemyDissolve = 59     #Default dissolve animation for dying enemies
genJoy = 60               #whether the joystick is enabled (not respected in many places, especially waitforanykey)
genPoisonChar = 61        #poison status indicator char
genStunChar = 62          #Stun status indicator char
genDamageCap = 63         #Damage cap
genMuteChar = 64          #Mute status indicator char
genStatCap = 65           #Stat caps (genStatCap + stat) (65-76)
genMaxSFX = 77            #last song number
genMasterPal = 78         #master palette number
genMaxMasterPal = 79      #max master palette number
genMaxMenu = 80           #max menu def in MENUS.BIN
genMaxMenuItem = 81       #max menu item def in MENUITEM.BIN
genMaxItem = 82           #max item in .ITM
genMaxBoxBorder = 83      #max box border number in .PT7
genMaxPortrait = 84       #max portrait graphic number in .PT8
genMaxInventory = 85      #max available inventory slot (0 means use inventoryMax)
genErrorLevel = 86        #value to set err_suppress_lvl to, if nonzero (NO LONGER USED)
genLevelCap = 87          #Default maximum level (0 to genMaxLevel) (not to be confused with genMaxLevel)
genEquipMergeFormula = 88 #Formula to use to calculate effective hero elemental resists
genNumElements = 89       #Number of elements used
genUnlockedReserveXP = 90 #% experience gained by unlocked reserve heroes
genLockedReserveXP = 91   #% experience gained by locked reserve heroes
genPW4Hash = 92           #new (4th style) password hash
genPW2Offset = 93         #old-old password offset
genPW2Length = 94         #old-old password length
genVersion = 95           #RPG file format version (see CURRENT_RPG_VERSION above for latest)
genStartMoney = 96        #starting money
genMaxShop = 97           #last shop in .SHO
genPW1Offset = 98         #old-old-old password offset
genPW1Length = 99         #old-old-old password length
genNumBackdrops = 100     #number of screens in .MXS
genBits = 101             #general bitsets
genStartX = 102           #starting X
genStartY = 103           #starting Y
genStartMap = 104         #starting Map
genOneTimeNPC = 105       #one-time-NPC indexer
genOneTimeNPCBits = 106   #one-time-NPC bits start here, OBSOLETE!
genDefaultDeathSFX = 171  #default enemy death sound effect
genMaxSong = 172          #last song number
genAcceptSFX = 173        #menu interface (+1)
genCancelSFX = 174        # "       "
genCursorSFX = 175        # "       "
genTextboxLine = 176      #Text box #click#  (+1)
genBits2 = 177            #More general bitsets
genBits3 = 178            #More general bitsets
genItemLearnSFX = 179     #learn spell oob item (+1)
genCantLearnSFX = 180     #hero couldn#t learn spell from item (+1)
genBuySFX = 181           #buy item from shop (+1)
genHireSFX = 182          #hire from shop (+1)
genSellSFX = 183          #sell item to shop (+1)
genCantBuySFX = 184       #can#t afford item/hire (+1)
genCantSellSFX = 185      #unsellable item (+1)
genDamageDisplayTicks = 186 #number of ticks that battle damage displays
genDamageDisplayRise = 187 #number of pixels that damage display rises
genHeroWeakHP = 188       #%HP for heroes to use Weak state
genEnemyWeakHP = 189      #%HP for enemies to use Desperation AI
genAutosortScheme = 190   #Method used to autosort inventory
genMaxLevel = 191         #Maximum level (not to be confused with changeable genLevelCap)
genBattleMode = 192       #Battle mode 0=Active-time, 1=Turn-based
genItemStackSize = 193    #Default item stack size
genResolutionX = 194      #Screen resolution (unzoomed). 0 for default
genResolutionY = 195      # "
genEscMenuScript = 196     #id of plotscript called instead of the default menu
genSaveSlotCount = 197    #The number of available save slots, 1 to 32. If 0, the default of 4 will be used
genMillisecPerFrame = 198 #Milliseconds per frame; upgrade() ensures not 0.
genStealSuccessSFX = 199  #Sound effect numbers for steal attacks in addition to normal sfx (+1)
genStealFailSFX = 200     # "
genStealNoItemSFX = 201   # "
genRegenChar = 202        # Regen status icon character
genDefaultScale = 203     # Unused.
genDebugMode = 204        # 0=Release mode, 1=Debug mode. Author choice for script error display. This is the one that should be edited by the game author
genCurrentDebugMode = 205 # 0=Release mode, 1=Debug mode. Current choice for script error display. This is the one that should be checked in-game
genStartHero = 206        # ID of initial hero
genStartTextbox = 207     # ID of initial textbox, or 0 = none
genWindowSize = 208       # Window size about X% of screen, in multiples of 10%. 10 means maximize
genLivePreviewWindowSize = 209 # Test-Game window size about X% of screen, in multiples of 10%. 10 means maximize
genFullscreen = 210       # Whether to start in fullscreen by default
#Everything else up to 499 unused.
#When adding more data to gen() consider whether it should be saved in .rsav.
#Also, gen() is reloaded by resetgame() when starting a new/loaded game,
#if that#s not OK the data should probably be stored elsewhere.
