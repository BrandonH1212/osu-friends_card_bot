import gspread, requests, random, random, glob, discord
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from osuapi import OsuApi, ReqConnector
from PIL import Image, ImageFont, ImageDraw
from datetime import datetime, timezone
from discord.ext import commands, tasks
import credentials

claim_reset_time = 1615139154
TestKey = credentials.TestKey
liveKey = credentials.liveKey



# osu api key
osuapi = OsuApi(credentials.osu, connector=ReqConnector())

# Google api scope
scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

# Google api credentials
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

# Google sheets client
client = gspread.authorize(creds)


# Get the different sheets
spreadsheet = client.open("OsuTowerDB")
p_sheet = spreadsheet.get_worksheet(0)
c_sheet = spreadsheet.get_worksheet(1)
map_sheet = spreadsheet.get_worksheet(2)
state_sheet = spreadsheet.get_worksheet(3)

# Get the different sheet rows
player_rows = p_sheet.batch_get(['A2:H100'])[0]
map_rows = map_sheet.batch_get(['A2:c2000'])[0]
card_rows = c_sheet.batch_get(['A2:H2000'])[0]
state_rows = map_sheet.batch_get(['A2:b2000'])[0]


# Saved list for discrete users only applies at runtime Saves the discord ID, message ID
cashed_messages = []

# Local version of player sheet each key is a player discord ID, indexes are a little different
player_reference_list = {}

# Local version of the map sheet
map_list = {}

# Every map ID in the set does not contain duplicates
map_set_ids = []

# Simplified list of maps only contains [star rating, Difficulty ID] Used for quickly getting a star range
sorted_star_list = []

# Local version of card sheet updated every time cards are added
card_reference_list = {}


# Create card reference list from real sheet
for i, cards in enumerate(card_rows):
    card_reference_list[str(cards[0])] = [str(i+1), cards[1], cards[2], cards[3], cards[4], cards[5], cards[6], cards[7]]
                        # id index difficulty id	score	accuracy	rank	mods	initially obtained Combo


# Create sorted star list and map_list and sorted_star_list from real sheet
for i, map in enumerate(map_rows):
    map_list[map[0]] = [i+1, map[1]]
    sorted_star_list.append([map[2], map[0]])

    if map[1] not in map_set_ids:
        map_set_ids.append(map[1])

sorted_star_list.sort()

################################################################################################
# TIME STUF
################################################################################################
def get_utc_timestep(): # Returns UTC float
    dt = datetime.now()
    utc_time = dt.replace(tzinfo=timezone.utc)
    utc_timestamp = utc_time.timestamp()
    return utc_timestamp

################################################################################################
#Function dump
################################################################################################

# Adds to the player reference list
def add_reference_entry(discord_id, entry_index, osu_id, osu_name,state, points, cards, BB, last_claim):
    player_reference_list[str(discord_id)] = [entry_index, osu_id, osu_name, state, points, cards, BB, last_claim] #key=discord_id 0=row_index 1=osu_id 2=osu_name 3=state 4=points 5=cards 6=BB 7=last_claim

# Create the initial reference sheet on start
for i, player in enumerate(player_rows):
    add_reference_entry(player[0], i+2, player[1], player[2], player[4], player[5], player[3],player[6], player[7])

# Adds a value to the cell using negative values to remove
async def add_to_cell(row, col, val):
    old = p_sheet.cell(row, col)
    try:
        new_val = int(old.value) + int(val)
    except:
        new_val = val
    p_sheet.update_cell(row, col, new_val)
    return new_val

# Returns string of player state if not found return 0
async def get_player_state(discord_id):
    try:
        return player_reference_list.get(str(discord_id))[3]
    except:
        return '0'

# Returns a sub_state From a divider if not return list with four indexes
# Example player state is inv|1|2|3 And you call get_player_sub_state(discord_id, |)
# It will return [inv,1,2,3]
async def get_player_sub_state(discord_id, divider):
    try:
        substate = await get_player_state(discord_id)
        split = substate.split(divider)
        return split
    except:
        return [0,0,0,0]

# Updates the player state to a new value updates the local and Google sheet
async def update_player_state(discord_id, new_state):
    p_sheet.update_cell(get_player_row_index(str(discord_id)), 5, str(new_state))
    player_reference_list.get(str(discord_id))[3] = str(new_state)

# Gets the players osu_name they registered with if they're not registered return null
def get_osu_name(discord_id):
    if is_registered(str(discord_id)):
        return player_reference_list.get(str(discord_id))[2]
    else:
        return "null"

# Gets the players osu_id they registered with if they're not registered return null
def get_osu_id(discord_id):
    if is_registered(discord_id):
        return int(player_reference_list.get(str(discord_id))[1])
    else:
        return "null"

# Checks if a player is registered
def is_registered(discord_id):
    if str(discord_id) in player_reference_list:
        return True
    else:
        return False

# Gets the player row index In the Google sheet players tab
def get_player_row_index(discord_id):
    return player_reference_list.get(str(discord_id))[0]

# Registers the player in the database with the osu name given If the name is not found does not register them
def register_player(discord_id, osu_name):
    if is_registered(discord_id):
        print("Player found")
        return f"User already registered"
    else:
        try:
            osu_id = osuapi.get_user(osu_name)[0].user_id
        except:
            return "User not found on osu?"

        add_reference_entry(str(discord_id), len(player_reference_list) + 2, osu_id, osu_name, "Initial", '10', '', '0', '0')
        p_sheet.insert_row([str(discord_id), osu_id, osu_name, "", "0", '10', '' , '0' ], len(player_reference_list) + 1)

        return f"Account linked to {osu_name} on osu"

# Gives player daily tokens adds to local database and sheet Does nothing if ID is a registered
# use negative numbers to remove tokens
async def give_tokens(discord_id, amount=1):
    if is_registered(discord_id):
        new_val = await add_to_cell(player_reference_list[str(discord_id)][0], 6, amount)
        pprint(new_val)
        player_reference_list[str(discord_id)][4] = new_val
        pprint(player_reference_list[str(discord_id)][4])
                #key=discord_id 0=row_index 1=osu_id 2=osu_name 3=state 4=points 5=cards 6=BB 7=last_claim

# Gives player BB adds to local database and sheet Does nothing if ID is a registered
# use negative numbers to remove BB
async def give_BB(discord_id, amount=1): # Use negative number to remove
    if is_registered(discord_id):
        new_val = await add_to_cell(player_reference_list[str(discord_id)][0], 7, amount)
        pprint(new_val)
        player_reference_list[str(discord_id)][6] = new_val
        pprint(player_reference_list[str(discord_id)][6])

# Get the number of points a player has
# returns a string so convert if you need to do math
async def get_tokens(discord_id):
    return player_reference_list.get(str(discord_id))[4]

# Get the number of BB a player has
# returns a string so convert if you need to do math
async def get_BB(discord_id):
    return player_reference_list.get(str(discord_id))[6]

# Gets all the card ids in the players inventory if they don't have any returns an empty list
#   [213,435,76,44] These will be strings by default
async def get_all_cards(discord_id):
    try:
        return player_reference_list.get(str(discord_id))[5].split("|")
    except:
        return []


# Gives an existing card to a player card must already be created and in the database
async def give_card(discord_id, card_id):
    cards = await get_all_cards(str(discord_id))
    cards.append(card_id)
    card_str = ""
    for card in cards:
        card_str += f"|{card}"
    player_reference_list[str(discord_id)][5] = card_str[1:]
    p_sheet.update_cell(player_reference_list.get(str(discord_id))[0], 4, card_str[1:])
    return


# Removes a card from the players inventory if the card is not in the inventory does nothing
async def remove_card(discord_id, card_id):
    cards = await get_all_cards(str(discord_id))
    try:
        cards.remove(card_id)
    except:
        return
    card_str = ""
    for card in cards:
        card_str += f"|{card}"
    p_sheet.update_cell(player_reference_list.get(str(discord_id))[0], 4, card_str[1:])
    player_reference_list[str(discord_id)][5] = card_str[1:]
    return


# Returns the most recent matching Score as a osu_api recent_score object
async def get_matching_score(discord_id, map_id):
    osu_id = get_osu_id(str(discord_id))
    recent_scores = osuapi.get_user_recent(osu_id, limit=5)
    
    for score in recent_scores:
        if str(score.beatmap_id) == str(map_id):
            return score
    return None


# Creates a card from an osu_api recent_score returns the ID
async def create_card(discord_id, score):
    score = score
    id = len(card_reference_list)+1
    c_sheet.append_row([id, score.beatmap_id, score.score, get_acc(score), score.rank, str(score.enabled_mods), get_osu_name(discord_id), score.maxcombo])
    card_reference_list[str(id)] = [str(id), str(score.beatmap_id), str(score.score), str(get_acc(score)), score.rank, str(score.enabled_mods), get_osu_name(discord_id), str(score.maxcombo)]
    return id


# Creates the card from pillow assumes card ID has been created if card ID is not in the database It will create errors
# Returns the image name/location
async def create_card_image(card_id):

    card_info = card_reference_list.get(str(card_id))
    #            index0  difficultyID1 score2	accuracy3	rank4	mods5	initially obtained6 Combo7
    map_object = osuapi.get_beatmaps(beatmap_id=int(card_info[1]))[0]
    card_name = f"{card_id}"
    map_object = osuapi.get_beatmaps(mode=0, beatmap_id=card_info[1], limit=30)[0]
    response = requests.get(f"https://assets.ppy.sh/beatmaps/{map_object.beatmapset_id}/covers/cover.jpg")
    pprint("Grabbed map image")
    file = open(f"cards/{card_name}.png", "wb")
    file.write(response.content)
    file.close()
    img = Image.open(f"cards/{card_name}.png")
    img2 = Image.open(f"bace/cardbace{card_info[4]}.png")
    img2.paste(img, (15, 55))
    draw = ImageDraw.Draw(img2)
    font = ImageFont.truetype("font/Exo2.0-Regular.otf", 24)
    combo_font = ImageFont.truetype("font/Overpass-Regular.ttf", 70)
    score_font = ImageFont.truetype("font/Overpass-Regular.ttf", 60)

    draw.text((658, 320), f"{card_info[6]}", (0, 0, 0), font=font)  # name
    draw.text((390, 320), f"{card_info[3][:3]}%", (0, 0, 0), font=font)  # ACC
    draw.text((483, 320), f"id|{card_info[0]}", (0, 0, 0), font=font)  # Extra
    draw.text((20, 10), f"{map_object.title}", (0, 0, 0), font=font)  # Title
    draw.text((900, 10), f"{map_object.version}", (0, 0, 0), font=font, anchor="ra")  # difficulty
    draw.text((25, 320), f"AR: {round(map_object.diff_approach)}", (0, 0, 0), font=font)  # ar
    draw.text((116, 320), f"CS: {round(map_object.diff_size)}", (0, 0, 0), font=font)  # cs
    draw.text((206, 320), f"OD: {round(map_object.diff_overall)}", (0, 0, 0), font=font)  # od
    draw.text((296, 320), f"HP: {round(map_object.diff_drain)}", (0, 0, 0), font=font)  # HP
    draw.text((576, 320), f"{round(map_object.difficultyrating, 2)}", (0, 0, 0), font=font)  # star
    draw.text((140, 240), f"{card_info[7]}x", (0, 0, 0), font=combo_font, stroke_width=4, stroke_fill=(240, 240, 240),
              anchor="ma")  # Combo
    draw.text((30, 70), "{:,}".format(int(card_info[2])), (0, 0, 0), font=score_font, stroke_width=2, stroke_fill=(240, 240, 240))  # Combo


    if len(card_info[5]) > 0:
        score_mods = card_info[5].split(" ")
        for i, mods in enumerate(score_mods):
            try:
                mod_image = Image.open(f"mods/{mods.lower()}.png")
                img2.paste(mod_image, ((810 - (45 * i), 70)), mod_image)
            except:
                pass

    rank_image = Image.open(f"rank/{card_info[4]}.png")
    img2.paste(rank_image, (810, 180), mask=rank_image)
    img2.save(f'cards/{card_name}.png', optimize=True)

    return card_name


# Check if the players eligible for daily tokens
async def is_claim_eligible(discord_id):
    last = player_reference_list.get(str(discord_id))[7] #key=discord_id 0=row_index 1=osu_id 2=osu_name 3=state 4=points 5=cards 6=BB 7=last_claim
    return int(last) < int(claim_reset_time)

# attempts to claim daily tokens if not eligible does nothing if successful
# tells the local Database and the public sheet what time the token was claimed
async def claim_daily(discord_id):
    if await is_claim_eligible(discord_id):
        player_reference_list[str(discord_id)][7] = round(get_utc_timestep())
        p_sheet.update_cell(get_player_row_index(discord_id), 8, round(get_utc_timestep()))
        await give_tokens(discord_id, 6)


################################################################################################
# Beat map functions
################################################################################################

# Returns accuracy from a beat map object
def get_acc(bmap):
    sum = bmap.count50 + bmap.count100 + bmap.count300 + bmap.countmiss
    acc = (bmap.count50 + bmap.count100 * 2 + bmap.count300 * 6) / (sum * 6)
    return 100 * round((acc), 4)


# Returns text formatted maps and range only use for debug currently
async def get_random_map_in_range(min, max):
    maps_found = []
    for map in sorted_star_list:
        if float(min) < float(map[0]) < float(max):
            maps_found.append(map)

    if len(maps_found) > 0:
        choice = random.choice(maps_found)
        b_map = osuapi.get_beatmaps(beatmap_id=choice, limit=30)[0]
        return f"Map {b_map.title} \n Difficulty {b_map.version} \n Star {b_map.difficultyrating}"
    else:
        return "No maps found in range"


# Returns a random difficulty ID in range Return zero if none is found
async def get_random_mapID_in_range(min, max):
    maps_found = []
    for map in sorted_star_list:
        if float(min) < float(map[0]) < float(max):
            maps_found.append(map)

    if len(maps_found) > 0:
        choice = random.choice(maps_found)
        return int(choice[1])
    else:
        return 0

# Checks if the difficulty ID is in the local database
def is_valid_map(map_id):
    return str(map_id) in map_list


# Checks if the map_set ID is in the local database
def is_valid_mapset_id(set_id):
    return str(set_id) in map_set_ids


# Adds Adds a map ID to the Sheet and local database checks if the map ID is valid
# Gets the map from the osu API
async def add_map(map):
    if is_valid_map(map.beatmap_id) == False:
        if map.mode is map.mode.osu:
            try:
                map_list[map.beatmap_id] = [len(map_list) + 1, map.beatmapset_id]
                map_sheet.insert_row([map.beatmap_id,
                                      map.beatmapset_id,
                                      map.difficultyrating,
                                      map.title,
                                      map.version,
                                      map.bpm,
                                      map.diff_size,
                                      map.diff_overall,
                                      map.diff_approach,
                                      map.diff_drain,
                                      map.hit_length], len(map_list) + 1)
            except:
                return "API cooldown try again in 2 min"


# Takes Difficulty ID and returns the set ID
async def get_map_set_id(map_id):
    try:
        return osuapi.get_beatmaps(mode=0, beatmap_id=map_id, limit=30)[0].beatmapset_id # Check if difficulty exists
    except:
        try:
            return osuapi.get_beatmaps(mode=0, beatmapset_id=map_id, limit=30)[0].beatmapset_id # If not check if it's a set ID instead
        except:
               return [0,0]


# Very bad code used for adding maps
pending_map_list = []
async def add_map_set(map_id):
    if map_id in pending_map_list:
        return "Map pending..."
    else:
        pending_map_list.append(map_id)

    set_id = await get_map_set_id(map_id)

    if set_id != 0:
        map_set = osuapi.get_beatmaps(mode=0, beatmapset_id=set_id, limit=30)
    else:
        try:
            map_set = osuapi.get_beatmaps(mode=0, beatmapset_id=map_id, limit=30)
        except:
            pending_map_list.remove(map_id)
            return "Invalid map ID or Map set in list"

    if len(map_set) > 0 and is_valid_mapset_id(str(map_set[0].beatmapset_id)) == False: # DO NOT MOVE THIS IF Above everything else I know it seems like a good idea but it's not

        for maps in map_set:
            if await add_map(maps) ==  "API cooldown try again in 2 min":
                return "Invalid map ID or API cooldown try again in 2 min"

        if str(map_set[0].beatmapset_id) not in map_set_ids:
            map_set_ids.append(str(map_set[0].beatmapset_id))

        pending_map_list.remove(map_id)
        return f"Adding all maps in set {map_set[0].title}"
    else:
        pending_map_list.remove(map_id)
        return "Invalid map ID or Map set in list"


# Returns file location of a card if the card does not exist it will attempt to create one
async def get_card_file(card_id):
    card_glob = glob.glob("cards/*.png")
    card_ids = []
    for card in card_glob:
        current_card = card.split("cards\\")[1]
        if f"{card_id}.png" == current_card:
            pprint("Found existing")
            return f'cards/{current_card}'

    pprint("Creating card")
    current_card = await create_card_image(card_id)
    return f'cards/{current_card}.png'


################################################################################################
#Edit Message menus
################################################################################################


# This is called any time a reaction is made it will open other menus based on the players state and what they reacted with
async def reaction_response(menu_id, discord_id, edit_message):
    if is_registered(discord_id):

        if menu_id == "⛔": # Close all menus
            await close_menus(discord_id, edit_message.channel.id)

        if menu_id == "💼": # Open inventory
            substate = await get_player_sub_state(discord_id, "|")
            if len(substate) > 1:
                await open_inventory_menu(discord_id, edit_message, substate[1])
                return
            else:
                await open_inventory_menu(discord_id, edit_message)
                return

        if menu_id == "💰": # Open daily
            await open_daily_menu(discord_id, edit_message)
            return

        if menu_id == "🤝": # Open trade
            substate = await get_player_sub_state(discord_id, ":")
            if len(substate) > 1:
                await open_trade_menu(discord_id, edit_message, substate[1])
                return
            else:
                await open_trade_menu(discord_id, edit_message, 0)
                return

        if menu_id == "⏩": # Generic next
            if "inv" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "|")
                await open_inventory_menu(discord_id, edit_message, int(substate[1])+1)
                return
            else: # placeholder
                await edit_message.add_reaction("⏪")
                await edit_message.add_reaction("⏩")
                return

        if menu_id == "⏪": # Generic Previous
            if "inv" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "|")
                await open_inventory_menu(discord_id, edit_message, int(substate[1]) - 1)
                return
            else: # placeholder
                await edit_message.add_reaction("⏪")
                await edit_message.add_reaction("⏩")
                return

        if menu_id == "🤷‍♂️": # No cards in inventory open daily
            if "inv" in await get_player_state(discord_id):
                await open_daily_menu(discord_id, edit_message)
                return

        if menu_id == "👀": # Inspect card in inventory
            if "inv" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "|")
                user = await bot.fetch_user(int(discord_id))
                await edit_message.edit(content="Loading...", embed=None)
                upload =  await edit_message.channel.send(user.mention, file=discord.File(await get_card_file(substate[2])))
                await open_inventory_menu(discord_id, edit_message, substate)
                return

        if menu_id == "💲": # sell inventory card
            if "inv" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "|")
                await edit_message.edit(content="Loading...", embed=None)
                await confirm_sell_card(discord_id, edit_message, substate[2])
                return

        if menu_id == "✔": # Approve sell inventory card
            if "inv" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "|")
                await edit_message.edit(content="Loading...", embed=None)
                if len(substate) > 3:
                    await sell_card(discord_id, edit_message, substate[2])
                    return

        if menu_id == "🎲": # Daily random three
            if "day_m" in await get_player_state(discord_id):
                await random_approval_menu(discord_id, edit_message)
                return

        if menu_id == "⭐": # Claim daily token
            if "day_m" in await get_player_state(discord_id):
                await claim_daily(discord_id)
                await open_daily_menu(discord_id, edit_message)
                return

        if menu_id == "👍": # Generic thumbs-up
            if "RCM" in await get_player_state(discord_id): # random 3 approval menu
                if int(await get_tokens(discord_id)) > 0:
                    await give_tokens(discord_id, -1)
                    await get_random_choices(discord_id, edit_message)
                    return

            if"RRAM" in await get_player_state(discord_id): # Range approval menu
                if int(await get_tokens(discord_id)) > 1:
                    await give_tokens(discord_id, -2)
                    await random_range_menu(discord_id, edit_message)
                    return

            if "RRM^3" in await get_player_state(discord_id): # range approval menu range selected
                substate = await get_player_sub_state(discord_id, "^")
                await get_random_choices(discord_id, edit_message, substate[2], substate[3])
                return

            if "BTAM": # Approval menu for converting BB to daily token
                if int(await get_BB(discord_id)) >= 10:
                    await give_BB(discord_id, -10)
                    await give_tokens(discord_id, 1)
                    await open_daily_menu(discord_id, edit_message)
                    return

        if menu_id == "❌": # Generic X Opens daily menu
            await open_daily_menu(discord_id, edit_message)
            return

        if menu_id == "1️⃣": # Select Number 1 In random three card selection
            if "rmap" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "!")
                await map_card_menu(discord_id, edit_message, substate[1],1)
                return

        if menu_id == "2️⃣":# Select Number 2 In random three card selection
            if "rmap" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "!")
                await map_card_menu(discord_id, edit_message, substate[2],1)
                return

        if menu_id == "3️⃣":# Select Number 3 In random three card selection
            if "rmap" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "!")
                await map_card_menu(discord_id, edit_message, substate[3],1)
                return

        # Really messy way of looping through 1-9 emoji's and checking If there In random range menu
        num_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "♾"]

        for i, num in enumerate(num_list):
            if menu_id == num:

                substate = await get_player_sub_state(discord_id, "^")

                if "RRM" in await get_player_state(discord_id):
                    if substate[1] == "1":
                        await update_player_state(discord_id, f"RRM^2^{i+1}^-1")
                    elif substate[1] == "2":
                        if num_list[i] == "♾":
                            await update_player_state(discord_id, f"RRM^3^{int(substate[2])}^99")
                        else:
                            await update_player_state(discord_id, f"RRM^3^{int(substate[2])}^{i+1}")

                    await random_range_menu(discord_id, edit_message)
                    return


        if menu_id == "🔄": # Generic refresh

            if "map@" in await get_player_state(discord_id): # check for player recent score
                substate = await get_player_sub_state(discord_id, "@")
                await map_card_menu(discord_id, edit_message, substate[2],1)
                return

            if "day_m" in await get_player_state(discord_id): # opens BB to token approval menu
                await buy_token_approval_menu(discord_id, edit_message)
                return


            if "RRM" in await get_player_state(discord_id): # restarts targeted range menu
                await update_player_state(discord_id, "RRM^1^-1^-1")
                await random_range_menu(discord_id, edit_message)
                return

        if menu_id == "🎯": # opens targeted range approval menu
            if "day_m" in await get_player_state(discord_id):
                await random_range_approval_menu(discord_id, edit_message)
                return

        #if menu_id == "©":
         #   if "map@" in await get_player_state(discord_id):
           #     substate = await get_player_sub_state(discord_id, "@")
            #    await map_card_menu(discord_id, edit_message, substate[2],2)

        if menu_id == "👌": # aproval for submitting score
            if "map@" in await get_player_state(discord_id):
                substate = await get_player_sub_state(discord_id, "@")
                if int(substate[1]) == 100:
                    await award_card_menu(discord_id, edit_message, substate[2], substate[1])
                    return
                else: # Else we close the menu in case the player tries to react prematurely
                    await close_menus(discord_id, edit_message.channel.id)
                    return

# open Player inventory menu At a specific page Page is a string because discord api
async def open_inventory_menu(discord_id, edit_message, page='0'):
    card_ids = await get_all_cards(discord_id)

    try:
        if int(page) > len(card_ids):
            new_page = len(card_ids)-1
        else:
            new_page = int(page)
    except:
        new_page = 0
    osu_name = get_osu_name(discord_id)

    try:
        card_ids.remove('')
    except:
        pass

    pprint(card_ids)
    embed = discord.Embed(title=f"Inventory menu for {osu_name}",
                            description=f"You have {len(card_ids)} Cards\n"
                                        f"⏪ Previous 👀 View card image ⏩ Next\n"
                                        f"💲 Sell card for 5 BB\n"
                                        f"Inventory menu page: {new_page+1}")
    try:
        card = card_reference_list.get(card_ids[new_page])
        bmap = osuapi.get_beatmaps(beatmap_id=int(card[1]))[0]
        embed.add_field(name=f"Title {bmap.title}\n Difficulty ⭐ {round(bmap.difficultyrating,2)} {bmap.version}", value=f"Score {card[2]}\n"
                                                                    f"Accuracy %{card[3]}\n"
                                                                    f"Combo {card[7]}\n"
                                                                    f"Rank {card[4]}\n"
                                                                    f"mods {card[5]}")
        embed.set_image(url=f"https://assets.ppy.sh/beatmaps/{bmap.beatmapset_id}/covers/card.jpg")
    except:
        embed.add_field(name="No cards found :(", value="You don't have any cards feels bad")

    await edit_message.edit(embed=embed, content='')


    if new_page > 0:
        await edit_message.add_reaction("⏪")

    if len(card_ids) > 0:
        await edit_message.add_reaction("👀")
        await update_player_state(discord_id, f"inv_m|{new_page}|{card_ids[new_page]}")
    else:
        await edit_message.add_reaction("🤷‍♂️")
        await update_player_state(discord_id, f"inv_m|{new_page}")

    if new_page+1 < len(card_ids):
        await edit_message.add_reaction("⏩")

    await edit_message.add_reaction("💲")


# Confirm Sell card menu
async def confirm_sell_card(discord_id, edit_message, card_id):
    embed = discord.Embed(title=f"{get_osu_name(discord_id)}'s Sell Card Confirmation", description="✔ Sell card for 5 BB\n"
                                                                                                    "💼 Return to inventory")
    card = card_reference_list.get(card_id)
    bmap = osuapi.get_beatmaps(beatmap_id=int(card[1]))[0]
    embed.add_field(name=f"Title {bmap.title}\n Difficulty ⭐ {round(bmap.difficultyrating, 2)} {bmap.version}",
                    value=f"Score {card[2]}\n"
                          f"Accuracy %{card[3]}\n"
                          f"Combo {card[7]}\n"
                          f"Rank {card[4]}\n"
                          f"mods {card[5]}")
    embed.set_image(url=f"https://assets.ppy.sh/beatmaps/{bmap.beatmapset_id}/covers/card.jpg")

    await update_player_state(discord_id, f"inv_m|0|{card_id}|1")
    await edit_message.edit(content="", embed=embed)
    await edit_message.add_reaction("✔")
    await edit_message.add_reaction("💼")


# Actually sell the card
async def sell_card(discord_id, edit_message, card_id):
    cards = await get_all_cards(discord_id)
    if card_id in cards:
        await give_BB(discord_id, 5)
        embed = discord.Embed(title=f"{get_osu_name(discord_id)} Card sold",
                              description=f"Balance BB: {await get_BB(discord_id)}  +5\n"
                                          "💼 Return to inventory")
        await edit_message.edit(content="",embed=embed)
        await update_player_state(discord_id, f"inv_m|0")
        await remove_card(discord_id, card_id)
    else:
        await edit_message.edit(content="Can't find card")

    await edit_message.add_reaction("💼")


# daily menu
async def open_daily_menu(discord_id, edit_message):

    embed = discord.Embed(title=f"{get_osu_name(discord_id)}'s Daily menu",
                            description=f"You have {await get_tokens(discord_id)} Daily tokens\n"
                                        f"You have {await get_BB(discord_id)} BB\n\n"
                                    f"🎲 Costs 1 for three random map choices\n"
                                    f"🎯 Cost 2 for 3 Targeted range choices\n"
                                        f"🔄 Exchange 10 BB for 1 Daily Token\n"
                                    f"⭐ Claim 6 Tokens for today")

    await edit_message.edit(content="",embed=embed)

    if int(await get_tokens(discord_id)) > 0:
        await edit_message.add_reaction("🎲")

    if int(await get_tokens(discord_id)) > 1:
        await edit_message.add_reaction("🎯")

    if int(await get_BB(discord_id)) > 9:
        await edit_message.add_reaction("🔄")

    if await is_claim_eligible(discord_id):
        await edit_message.add_reaction("⭐")

    await update_player_state(discord_id, "day_m")


# Random range menu
async def random_range_menu(discord_id, edit_message, min=-1, max=-1):
    substate = await get_player_sub_state(discord_id, "^")

    if len(substate) >= 2:
        state = int(substate[1])
        min = int(substate[2])
        max = int(substate[3])
    else:
        await update_player_state(discord_id, "RRM^1^-1^-1")
        state = 0

    num_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "♾"]
    Menu_titles = ["Select range  Minimum", "Select range  Minimum", "Select range  Maximum", "Range selected Use 👍"]
    embed = discord.Embed(title=f"{get_osu_name(discord_id)} {Menu_titles[state]}\nmin {min} - max {max}",
                            description=f"Use 🔢 to select the range! \nif you make a mistake use 🔄 to reset selections\n Once you are happy use 👍 to confirm the selection\nGood luck!")

    await edit_message.edit(embed=embed)

    for i, nums in enumerate(num_list):
        if state < 2 and i != len(num_list) -1: # Selecting min
            await edit_message.add_reaction(nums)

        if state == 2: # Selecting max
            if i+1 > min:
                await edit_message.add_reaction(nums)

    if max > 0:
        await edit_message.add_reaction("👍")
    await edit_message.add_reaction("🔄")


# Buy token approval menu
async def buy_token_approval_menu(discord_id, edit_message):
    if int(await get_BB(discord_id)) > 9:
        embed = discord.Embed(title=f"{get_osu_name(discord_id)} Spend 10 BB for 1 Daily token?",
                                description=f"You have {await get_tokens(discord_id)} Daily tokens\n"
                                            f"You have {await get_BB(discord_id)} BB\n\n"
                                        f"👍 Accept (Cost 10 BB get 1 Daily token)   ❌ Decline")
        await edit_message.edit(content="", embed=embed)
        await edit_message.add_reaction("👍")
        await edit_message.add_reaction("❌")
        await update_player_state(discord_id, "BTAM")


async def random_range_approval_menu(discord_id, edit_message):
    if int(await get_tokens(discord_id)) > 1:
        embed = discord.Embed(title=f"{get_osu_name(discord_id)} Spend 2 token approval",
                                description=f"You have {await get_tokens(discord_id)} Daily tokens\n\n"
                                        f"You will choose a start range and be given three maps in that range\n"
                                        f"once you select a map you cannot change it until you submit the score\n"
                                        f"if you open any other menus your choice will be voided you will not get a refund\n\n"
                                        f"👍 Accept (Cost 2 Daily Token)   ❌ Decline")
        await edit_message.edit(content="", embed=embed)
        await edit_message.add_reaction("👍")
        await edit_message.add_reaction("❌")
        await update_player_state(discord_id, "RRAM")


async def random_approval_menu(discord_id, edit_message):
    if int(await get_tokens(discord_id)) > 0:
        embed = discord.Embed(title=f"{get_osu_name(discord_id)} Spend token approval",
                                description=f"You have {await get_tokens(discord_id)} Daily tokens\n\n"
                                        f"You will be given three random map choices\n"
                                        f"once you select a map you cannot change it until you submit the score\n"
                                        f"if you open any other menus your choice will be voided you will not get a refund\n\n"
                                        f"👍 Accept (Cost 1 Daily Token)   ❌ Decline")
        await edit_message.edit(content="", embed=embed)
        await edit_message.add_reaction("👍")
        await edit_message.add_reaction("❌")
        await update_player_state(discord_id, "RCM")


async def open_trade_menu(discord_id, edit_message, page=0):
    cards = await get_all_cards(discord_id)
    sub_state = await get_player_sub_state(discord_id, ":")
    embed = discord.Embed(title=f"{get_osu_name(discord_id)} Trade menu (Coming soon)",
                          description=f"You have {len(cards)} Tradable cards\n\nPage {int(page)+1}/{round(len(cards)/10)}")

    page_divider = int(page)*10
    for card in cards[page_divider:page_divider+10]:
        rcard = card_reference_list.get(card)
        try:
            bmap = osuapi.get_beatmaps(beatmap_id=rcard[1])[0]
            embed.add_field(name=f"{bmap.title}\n⭐ {round(bmap.difficultyrating, 2)} {bmap.version}",value=f"card ID {rcard[0]}")
        except:
            pass

    await edit_message.edit(content="",embed=embed)
    await update_player_state(discord_id, "trade_m:0")

# Gets a random card choice In the range
async def get_random_choices(discord_id, edit_message, min=0, max=99):
    choice1 = await get_random_mapID_in_range(min, max)
    choice2 = await get_random_mapID_in_range(min, max)
    choice3 = await get_random_mapID_in_range(min, max)
    map1 = osuapi.get_beatmaps(beatmap_id=int(choice1))[0]
    map2 = osuapi.get_beatmaps(beatmap_id=int(choice2))[0]
    map3 = osuapi.get_beatmaps(beatmap_id=int(choice3))[0]

    embed = discord.Embed(title=f"{get_osu_name(discord_id)}s Random choices",
                            description="")
    embed.add_field(name=f"1️⃣ {map1.title}  (http://osu.ppy.sh/b/{choice1})\n ⭐ {round(map1.difficultyrating, 2)} {map1.version}\n",
                    value=f"AR: {map1.diff_approach}    "
                          f"CS: {map1.diff_size}\n"
                          f"OD: {map1.diff_overall}    "
                          f"HP: {map1.diff_drain}",inline=False)

    embed.add_field(name=f"2️⃣ {map2.title}  (http://osu.ppy.sh/b/{choice2})\n ⭐ {round(map2.difficultyrating, 2)} {map2.version}\n",
                    value=f"AR: {map2.diff_approach}    "
                          f"CS: {map2.diff_size}\n"
                          f"OD: {map2.diff_overall}    "
                          f"HP: {map2.diff_drain}",inline=False)

    embed.add_field(name=f"3️⃣ {map3.title}  (http://osu.ppy.sh/b/{choice3})\n ⭐ {round(map3.difficultyrating, 2)} {map3.version}\n",
                    value=f"AR: {map3.diff_approach}    "
                          f"CS: {map3.diff_size}\n"
                          f"OD: {map3.diff_overall}    "
                          f"HP: {map3.diff_drain}",inline=False)

    await edit_message.edit(content=f"", embed=embed)

    await edit_message.add_reaction("1️⃣")
    await edit_message.add_reaction("2️⃣")
    await edit_message.add_reaction("3️⃣")
    await update_player_state(discord_id, f"rmap!{choice1}!{choice2}!{choice3}")


async def map_card_menu(discord_id, edit_message, map_id, play_id):
    await update_player_state(discord_id, f"map@{play_id}@{map_id}")

    bmap = osuapi.get_beatmaps(beatmap_id=int(map_id))[0]

    play_info = await get_play_info(play_id, discord_id)
    play = play_info[0]

    embed = discord.Embed(title=f"Waiting for play from {get_osu_name(discord_id)}",
                          description=f"{bmap.title}  (http://osu.ppy.sh/b/{map_id})\n ⭐ {round(bmap.difficultyrating, 2)} {bmap.version}\n"
                                      f"Use 🔄 To find recent play\n"
                                      f"REMEMBER TO USE 👌 once the play is found")

    if play_info[1] == 1 and play != None:
        embed.add_field(name=f"Found play", value=f"Score {play.score}\n"
                                                                    f"Accuracy %{get_acc(play)}\n"
                                                                    f"Combo {play.maxcombo}\n"
                                                                    f"Rank {play.rank}")

        embed.set_image(url=f"https://assets.ppy.sh/beatmaps/{bmap.beatmapset_id}/covers/card.jpg")
        await edit_message.add_reaction("👌")
        await update_player_state(discord_id, f"map@{play_info[2]}@{map_id}")

    await edit_message.edit(content=f"",embed=embed)

    await edit_message.add_reaction("🔄")

# Gets the play Info from local database takes
async def get_play_info(play_id, discord_id):
    substate = await get_player_sub_state(discord_id, "@")
    if play_id == 100 or play_id == 1:
        play = await get_matching_score(discord_id, int(substate[2]))
        if play != None:
            return [play, 1, 100]

    return [None, 0, 0]

# Award the player with the card
async def award_card_menu(discord_id, edit_message, map_id, play_id):
    if str(play_id) == "100":
        play = await get_matching_score(discord_id, map_id)
        card_id = await create_card(discord_id, play)
        await give_card(discord_id, card_id)
        await update_player_state(discord_id, f"earned_card")
        await edit_message.edit(content=f"Card acquired!")
        await edit_message.channel.send(file=discord.File(await get_card_file(card_id)))

# Closes open menus
async def close_menus(discord_id, channel_id):
    for menus in cashed_messages:
        if discord_id in menus:
            channel = await bot.fetch_channel(channel_id)
            message = await channel.fetch_message(menus[1])
            await message.delete()
            cashed_messages.remove(menus)

################################################################################################
#bot functions
################################################################################################

bot = commands.Bot(command_prefix='!')

# Adds a map set by difficulty ID to the local database and sheet
@bot.command(aliases=["addmap", 'AddMap', 'addMap'])
async def _addmap(ctx, *, map_id='0'):
    await ctx.send(await add_map_set(map_id))

# Registers a player in the database
@bot.command(aliases=["register", 'link', 'setup'])
async def _register(ctx, *, osu_name):
    await ctx.send(register_player(ctx.author.id, osu_name))

# Gets 4 random maps from the database In text readable format just for debugging
@bot.command(aliases=["GetMaps", 'getMaps', 'Getmaps', 'getmaps'])
async def _getmap(ctx, min="1.0", max="10.0"):
    await ctx.send(await get_random_map_in_range(min, max))
    await ctx.send(await get_random_map_in_range(min, max))
    await ctx.send(await get_random_map_in_range(min, max))
    await ctx.send(await get_random_map_in_range(min, max))

# Used to test whatever I'm working on
@bot.command(aliases=["test"])
async def _test(ctx):
    await claim_daily(ctx.author.id)

# Used to Test new menus
async def test_menu(discord_id):
    pass

# Returns the card image from the ID provided
@bot.command(aliases=["card", 'Card'])
async def _card(ctx, card_id="0"):
    try:
        await ctx.send(file=discord.File(await get_card_file(card_id)))
    except :
        await ctx.send("Card id not found in database")


# Opens the main player menu if there's already menu open closes it
# Also adds that message to the message cash
@bot.command(aliases=["m", 'Menu', 'menu'])
async def _menu(ctx):
    osu_name = get_osu_name(str(ctx.author.id))
    if osu_name != "null":
        await close_menus(ctx.author.id, ctx.channel.id)
        embed = discord.Embed(title=f"Player menu for {osu_name}", description=f"Welcome to the main menu good luck! \n"
                                                                               f"Daily Tokens: {await get_tokens(ctx.author.id)} BB: {await get_BB(ctx.author.id)}\n"
                                                                               f"⛔ Closes all open menus")  # ,color=Hex code
        embed.add_field(name="💰 Daily Tokens", value="Spend your tokens and get your daily tokens!")
        embed.add_field(name="💼 Inventory", value="View the cards you have obtained!")
        embed.add_field(name="🤝 Trade", value="Trade with other players!")

        message = await ctx.send(embed=embed)
        await message.add_reaction("💰")
        await message.add_reaction("💼")
        await message.add_reaction("🤝")
        await message.add_reaction("⛔")
        cashed_messages.append([ctx.author.id, message.id])
        await ctx.message.delete()
    else:
        await ctx.send("Discord ID not attached to existing account \nUse !register (osu_username)")

# Opens the random map or selected map menu if available
@bot.command(aliases=['b', 'Bump', 'bump'])
async def _bump(ctx):
    if is_registered(ctx.author.id):
        playerState = await get_player_state(ctx.author.id)
        if("rmap" in playerState) or ("map@" in playerState): #If player is choosing a random map or has chosen a map
            for menus in cashed_messages:
                if ctx.author.id in menus: 
                    message = await ctx.channel.fetch_message(menus[1])
                    newMessage = await ctx.send(embed=message.embeds[0]) #Resend the embed message
                    for react in message.reactions:
                        await newMessage.add_reaction(react) #Add the reactions in the old message
                    cashed_messages.append([ctx.author.id, newMessage.id]) #cache the new message
                    await message.delete() #Delete old message
                    cashed_messages.remove(menus) #Remove old message from cache
    else:
        await ctx.send("Discord ID not attached to existing account \nUse !register (osu_username)")


# Opens the inventory menu at a specified page Closes other menus
# Also adds that message to the message cash
@bot.command(aliases=["i", 'I', 'Inventory', 'inventory', "inv"])
async def _inventory_menu(ctx, page=0):
    if is_registered(ctx.author.id):
        await close_menus(ctx.author.id, ctx.channel.id)
        message = await ctx.send("Loading...")
        cashed_messages.append([ctx.author.id, message.id])
        card_ids = await get_all_cards(str(ctx.author.id))
        try:
            card_id = card_ids[int(page)]
            await update_player_state(ctx.author.id, f"inv_m|{str(page-1)}|{card_id}")
        except:
            await update_player_state(ctx.author.id, f"inv_m|{str(0)}|")
        await reaction_response("💼", ctx.author.id, message)
    else:
        await ctx.send("Discord ID not attached to existing account \nUse !register (osu_username)")

# Checks if a reaction can happen
async def is_valid_member_reaction(discord_id, message_id):
    if [discord_id, message_id] not in cashed_messages:
        return False
    else:
        return True

# When a player reacts clear all reactions and Then open the response menu
@bot.event
async def on_raw_reaction_add(payload):
    if await is_valid_member_reaction(payload.user_id, payload.message_id):
        channel = await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        await message.clear_reactions()
        await reaction_response(payload.emoji.name, payload.user_id, message)

# Print the current time at start
pprint(get_utc_timestep())

# Run the bot
bot.run(liveKey)