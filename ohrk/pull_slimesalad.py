#!/usr/bin/env python3

from calendar import timegm
from datetime import datetime, timezone
import re
import time
import os
from io import StringIO
from collections import defaultdict
import bs4

if __name__ == '__main__':
    import ohrkpaths  # Setup sys.path

from ohrk import db_layer, gamedb, scrape, urlimp, util
from ohrk.urlimp import urljoin
from ohrk.slimesalad_gamedump import ChunkReader, GameInfo


verbose = True

GAMEDUMP_URL = 'https://www.slimesalad.com/forum/gamedump.php'
OLD_GAMEDUMP_URL = 'https://www.slimesalad.com/phpbb2/gamedump.php'


db = None
#link_db = db_layer.load('ss_links')
link_db = {'p2t':{}, 't2p':{}}  # post -> topic and topic -> post mappings
zips_db = None


# Whether to cache gamedump.php (True/False), or how long for (seconds, as int)
# (Note: caching game pages may cause problems with listed downloads. Ideally
# should intelligently figure out which caches to drop)
CACHE_INDEX = True #False

def tostr(strnode: bs4.NavigableString):
    ret = str(strnode.string)
    return util.fix_double_utf8(ret)

def rewrite_img_urls(url_or_html):
    "Special cases"
    # Fix Star Trucker screenshots, which were moved,
    # and SS smileys
    return (url_or_html.replace('spacetru.files.wordpress', 'startru.files.wordpress')
            .replace('src="images/smiles', 'src="https://www.slimesalad.com/forum/images/smiles')
            .replace('src="images/smilies', 'src="https://www.slimesalad.com/forum/images/smilies'))

def clean_description(descrip_tag):
    # Delete inline attachments including broken links which display "The attachment
    # <strong>fname</strong> is no longer available" (happens when image is reuploaded).
    # Currently https://www.slimesalad.com/forum/viewgame.php?t=8278 is the only game that
    # puts an inline attachment somewhere other than the bottom -- it puts it at the top.
    # Just delete inline attachments (other inline images remain inline)
    for attach in descrip_tag.find_all(class_='inline-attachment'):
        # Ugh clean this up
        attach.replace_with()  # Delete

    for tag in descrip_tag.find_all(class_='codebox'):
        # Remove "Code" and "Select all" button
        tag.p.replace_with()

    for tag in descrip_tag.find_all(onclick=True):
        #print("ONCLICK TAG", tag)
        assert 'ss-spoiler' in tag.get('class')

    for tag in descrip_tag.find_all(class_=True):
        del tag['class']

    # Remove <br> tags which are added on every newline
    # (Note: same games like Willy's also include <p> html, which gets lost
    #return '\n'.join(line.encode('utf-8').strip() for line in descrip_tag.strings)
    # Preserve all
    ret = rewrite_img_urls(scrape.tag_contents(descrip_tag))


    return ret


stats = {'inline_screens': 0, 'downloaded_inline_ok': 0, 'files_processed': 0, 'files_not_on_page': 0, 'files_not_in_gamedump': 0}

seen_tags = defaultdict(int)

def process_game_page(url, gameinfo: GameInfo = None, cache = True, download_screens = True):
    global zips_db

    # Every game on SS has *four* valid links, for example:
    # http://www.slimesalad.com/forum/viewgame.php?t=1021
    # http://www.slimesalad.com/forum/viewtopic.php?t=1021
    # http://www.slimesalad.com/forum/viewtopic.php?p=15109
    # http://www.slimesalad.com/forum/viewgame.php?p=15109
    # (?t= is topic number ?p= is post number)
    # While viewtopic.php can be used instead of viewgame.php, it's missing
    # the tags. Use topic number as srcid.

    url = url.replace('viewtopic.php', 'viewgame.php')
    url = util.remove_sid(url)
    assert 'viewgame.php' in url

    parsed_url = urlimp.urlparse(url)
    url_query = urlimp.parse_qs(parsed_url.query)  # Parse to dict containing lists of values
    if 't' in url_query:
        if url_query['t'][0] == '0':
            # Deleted game
            # When a game is deleted sometimes there's a phantom gamedump.php entry with garbage data.
            # And the old URL may either not exist, or go to a Deleted Game page with original author
            # and review link remnants
            print("Skipping deleted game")
            return
    else:
        assert 'p' in url_query

    dom = scrape.get_page(url, cache = cache)

    title_node = dom.find(class_='title')
    if title_node is None:  #phpbb3
        title_node = dom.find(class_='topic-title')

    title_query = urlimp.parse_qs(title_node.a['href'].split('?')[1])
    topicnum = int(title_query['t'][0])
    srcid = str(topicnum)

    # Get postnum and update the database mapping between the t= and p= links

    post = dom.find(alt='Post')
    if post:  # phpbb2
        link = post.parent['href']
        phpbb = 2
    else:  #phpbb3
        link = dom.find(title='Post')['href']
        phpbb = 3

    postnum = int(link.split('#')[-1].replace('p', ''))  #phpbb3 prefixes a 'p'

    # Sanity check that url matches what we found on the page
    if 't' in url_query:
        assert topicnum == int(url_query['t'][0])
    else:
        assert postnum == int(url_query['p'][0])

    link_db['p2t'][postnum] = topicnum
    link_db['t2p'][topicnum] = postnum


    if gameinfo:
        gameinfo_files = list(gameinfo.files + gameinfo.pics)

    def seen_file(fname):
        stats['files_processed'] += 1
        if gameinfo == None:
            return
        for gf in gameinfo_files:
            if gf.name == fname:
                gameinfo_files.remove(gf)
                return
        print("Couldn't find in gamedump.php:", fname)

    game = gamedb.Game()
    game.name = tostr(title_node)
    game.url = f"https://{parsed_url.netloc}{parsed_url.path}?t={topicnum}"
    print("Processing game:", game.name, "  \tsrcid:", srcid)

    author_box = dom.find(class_='gameauthor')
    if author_box:  #phpbb2
        game.author = tostr(author_box.find(class_='title'))
        author_link = author_box.a
    else:  # phpbb3
        author_box = dom.find(class_='author')
        author_link = author_box.find(class_='username')
        if author_link is None:
            author_link = author_box.find(class_='username-coloured')  # Mods and admins
        game.author = tostr(author_link)
    game.author_link = urljoin(url, util.remove_sid(author_link['href']))

    # Grab description
    if phpbb == 2:
        descrip_tag = dom.find(class_='postbody')
    else:
        descrip_tag = dom.find(class_='content')

    # Downloads

    def parse_phpbb3_attachment(link_tag):
        "link_tag can be either an <img> or an <a> in the <dt> of an attachment"
        #print(link_tag.parent.parent)
        # The <img> is in a <dt> in a <dl> followed by an optional <dd> with
        # the description, and another <dd> with the filename/size/view count
        dd_tags = link_tag.find_parent('dl').find_all('dd')
        if len(dd_tags) == 1:
            description = ""
        else:
            description = tostr(dd_tags[0])
        infotext = tostr(dd_tags[-1])
        info = infotext.split()
        # Could get the filename from the gameinfo instead.
        # infotext for images:
        #   Viking0004.png (23.56 KiB) Viewed 3860 times
        # for files:
        #   (45.93 MiB) Downloaded 219 times
        if 'postlink' in link_tag['class']:
            # A download link found in the attachments section, its infotext doesn't duplicate the filename
            print("download in attachments")
            fname = tostr(link_tag)
        else:
            if 'postimage' in link_tag.parent['class']:
                match = re.match('(.*) \(.*\) Viewed', infotext)
                fname = match.group(1)
            else:
                fname = infotext.split(info[-5])[0].strip()
        sizestr = info[-5][1:] + ' ' + info[-4][:-1]
        download_count = int(info[-2])
        return fname, description, sizestr, download_count

    def parse_game_download(a_tag):
        "Parse a download link in the viewgame.php Downloads section, both phpbb 2 and 3"
        info, descrip_tag, _ = a_tag.next_siblings
        # info is e.g. phpbb2: "(37.5 KB; downloaded 351 times)" or phpbb3: "(0MB; 22867 downloads)"
        # the latter being SS custom php so it's formatted differently
        info = info.split()
        # The title of the download displayed on the page is the original
        # file name, need to use gamedump.php to find the mangled name.
        if phpbb == 2:
            title = tostr(a_tag.b)  # Display name
        else:
            title = tostr(a_tag)
        download_count = int(info[-2])
        if phpbb == 2:
            sizestr = info[0][1:] + ' ' + info[1][:-1]
        else:
            sizestr = info[0][1:-1]
        description = descrip_tag.string and tostr(descrip_tag)
        return title, description, sizestr, download_count

    # Have to match up the downloads on gamedump.php (with the mtimes and
    # actual download links) with the entries on the game page (with the descriptions).
    # The order in which the downloads appear in gamedump.php is mostly sorted by ascending
    # download id (which is not shown), but sometimes differs (probably when multiple
    # downloads were uploaded at once).
    # The order the downloads appear on the page is usually but not always
    # (e.g. http://www.slimesalad.com/forum/viewgame.php?t=220) the opposite order
    # (again, multi-uploads seem to cause some permutations).
    # So the kludge is to first match up the download names, and assume multiple downloads
    # with the same name were uploaded separately, and rely on the order of them being
    # opposite in the two lists.
    download_php = 'download\.php' if phpbb == 2 else 'download/file\.php'
    download_tags = dom.find_all('a', href=re.compile(download_php))
    def download_id(a_tag):
        ret = int(util.remove_sid(a_tag['href']).split('id=')[1])
        return ret
    #download_tags.sort(key = download_id)   # This also works instead of inverting
    download_tags = download_tags[::-1]

    # Sometimes e.g. http://www.slimesalad.com/forum/viewgame.php?t=5996
    # an image is listed as a download, so doesn't appear in gameinfo.files
    #assert len(gameinfo.files) == len(download_tags)
    for a_tag in download_tags:
        #print("<<<A_TAG>>>", a_tag)
        #print()
        #print("<<PARENT>>>", a_tag.parent, "\n\n")
        # Bug on phpbb3 site: .tar.gz downloads are in the attachments rather than
        # downloads section. Also they have the <a> illegally inside the icon's <img>
        if a_tag.find_parent('dl'):
            title, description, sizestr, download_count = parse_phpbb3_attachment(a_tag)
        else:
            title, description, sizestr, download_count = parse_game_download(a_tag)
        download_url = urljoin(url, util.remove_sid(a_tag['href']))

        download_mtime = None
        if gameinfo:
            # The title is not unique!
            #gamefile = gameinfo.file_by_name(title)
            gamefile = gameinfo.file_by_url(download_url)
            if not gamefile:
                print("!! Couldn't find %s, maybe the cached game page has a download that's since "
                      "been removed (not in gamedump.php)" % title)
                zip_fname = "(Removed)"
            else:
                #print("  Found file in gameinfo:", gamefile.name)
                assert gamefile.name == title
                if phpbb == 2:
                    # Note! This is a managled filename like dwarvinity_183.zip,
                    # which is what it actually downloads as
                    zip_fname = gamefile.url.split('/')[-1]
                else:
                    # Downloads now download with their original filename (while
                    # the download URL doesn't contain the filename)
                    zip_fname = gamefile.name
                download_mtime = gamefile.date.timestamp()
        else:
            zip_fname = title
            stats['files_not_in_gamedump'] += 1
        seen_file(title)

        download = gamedb.DownloadLink('ss', zip_fname, download_url, title)
        download.description = description
        download.sizestr = sizestr
        download.download_count = download_count
        download.mtime = download_mtime

        # TODO: download file naming has changed, match up all the old downloads without redownloading

        if zips_db and download.zipkey() in zips_db:
            # Double check we matched the files correcting by checking the sizes match
            expected = util.format_filesize(zips_db[download.zipkey()].size)
            if phpbb == 2:
                if download.sizestr != expected:
                    print("WARNING: expected size", expected, "got", download.sizestr)
            else:
                # Size string is garbage (but we could copy it from viewtopic.php page instead)
                download.sizestr = expected
        if verbose: print(download.dumpinfo())
        game.downloads.append(download)


    # Download any images embedded in the description... excluding inline attachments, which are handled
    # with other image attachments, and then deleted from the description so will no longer be inline.
    for img_tag in descrip_tag.find_all('img'):
        # But ignore smilies...
        src = img_tag['src']
        if src.startswith('images/smiles') or src.startswith('./images/smilies'):
            continue
        if img_tag.find_parent(class_ = 'inline-attachment'):  #phpbb3
            continue

        stats['inline_screens'] += 1
        img_url = rewrite_img_urls(util.remove_sid(urljoin(url, img_tag['src'])))
        if download_screens:
            stats['downloaded_inline_ok'] += game.add_screenshot_link(db.name, srcid, img_url, is_inline = True)
        else:
            game.add_screenshot_no_download(img_url, is_inline = True)

    # Grab screenshots (and embedded images)
    screenshot_class = 'attach_img' if phpbb == 2 else 'postimage'
    for img_tag in dom.find_all('img', class_=screenshot_class):
        # print("\nscreen:")
        # print("<<<IMG_TAG>>>", img_tag)
        # print()
        # print("<<PARENT>>>", img_tag.parent, "\n\n")
        if phpbb == 2:
            caption = img_tag.parent.find_next_sibling('div', class_='attachheader').string
            # caption is either None or a NavigableString
            if caption:
                caption = tostr(caption)
            fname = img_tag['alt']  # The original name without mangling
        else:
            # if img_tag.find_parent(class_=('content', 'signature')):
            #     # This image is in the description (gets postimage class added), we already handled it
            #     # or is in the signature (which shouldn't be there), ignore it
            #     continue

            if img_tag.find_parent(class_='content') and not img_tag.find_parent(class_='inline-attachment'):
                # Only handle images in the description (they get postimage class added) which are inline
                # attaches, otherwiser handled above
                continue

            if img_tag.find_parent(class_='signature'):
                # This image is in the signature (which shouldn't actually be there), ignore it
                continue

            #print(img_tag.parent.parent)
            fname, caption, _, _ = parse_phpbb3_attachment(img_tag)
        img_url = urljoin(url, util.remove_sid(img_tag['src']))
        if download_screens:
            game.add_screenshot_link(db.name, srcid, img_url, caption, filename = fname, verbose = verbose)
        else:
            game.add_screenshot_no_download(img_url, caption, verbose = verbose)
        seen_file(fname)

    # Reviews
    game.reviews = []

    # The review links appear after  are in <p>'s sandwiched
    review_header = dom.find('div', string='Reviews')
    review_row = review_header.next_sibling
    while True:
        if isinstance(review_row, bs4.NavigableString):  # Blank space
            review_row = review_row.next_sibling
            continue
        # "[icon] [review] by [author]" lines are wrapped in <p> in phpbb3, <div class="attachrow"><a href=""> in phpbb2
        by = review_row.find(string = " by ")
        if not by:
            break
        review_row = review_row.next_sibling

        review_link = by.previous_sibling
        author_link = by.next_sibling
        assert review_link.name == 'a' and author_link.name == 'a'

        # There are two review link styles on the phpbb3 site:
        #<p><img src=...> <a href="http://.../forum/viewtopic.php?t=5655" class="postlink">Second Review</a> by <a href="http://.../profile.php?mode=viewprofile&amp;u=3" class="postlink">Meatballsub</a></p>
        #<p><img src=...> <a href="/forum/viewtopic.php?f=5&amp;t=8189">Vikings of Midgard Review</a> by <a href="/forum/memberlist.php?mode=viewprofile&amp;u=203">Baconlabs</a></p>
        # urljoin cleans up the &amp;
        # TODO: but should remove the f=5
        rurl = urljoin(url, review_link['href']).replace('http://', 'https://')

        # Could use to_str(review_link) as the review title, but typically it's just "Review"
        review = gamedb.Review(rurl, tostr(author_link), game.name, location = 'on Slime Salad')
        if verbose: print(review.dumpinfo())
        game.reviews.append(review)

    # Tags
    for tag in dom.find_all(attrs = {'data-tag': True}):
        game.tags.append(tostr(tag.a))

    # Description
    game.description = clean_description(descrip_tag)
    #print("description:\n", repr(game.description))

    # Edit time. But it seems only older games show last edit time
    # at the bottom of the post.
    if phpbb == 3:
        notice = dom.find(class_='notice')
        if notice:
            # Use notice.text to ignore the user profile link
            match = re.search('on (.*), edited', notice.text)
            # E.g. Thu Jul 12, 2018 12:11 pm, in UTC
            game.mtime = timegm(time.strptime(match.group(1), "%a %b %d, %Y %I:%M %p"))
            #print("edit time", datetime.utcfromtimestamp(game.mtime).ctime())
        else:
            # No edit info? Use original post time
            time_tag = dom.find('time')
            if time_tag:
                game.mtime = datetime.fromisoformat(time_tag['datetime']).timestamp()
                #print("post time", datetime.utcfromtimestamp(game.mtime).ctime())


    # Double-check that there are no NavigableStrings or undecoded strings
    game = scrape.clean_strings(game)

    if gameinfo:
        if len(gameinfo_files):
            stats['files_not_on_page'] += len(gameinfo_files)
            print("FILES NOT ON PAGE:")
            for gf in gameinfo_files:
                print(gf.serialize())

    if db:
        db.games[srcid] = game
    return game

def get_gamedump(phpbb2 = False, cache = CACHE_INDEX):
    url = OLD_GAMEDUMP_URL if phpbb2 else GAMEDUMP_URL
    print("Fetching/parsing", url)
    return scrape.get_url(url, cache = cache).decode('utf8') #('windows-1252')

def process_gamedump(phpbb2 = False, limit = 9999, cache_index = CACHE_INDEX):
    """
    Generate the db and link_db databases (both global variables)
    """

    seen_names = set()
    seen_urls = set()
    file = StringIO(get_gamedump(phpbb2, cache_index))
    for chunk in ChunkReader(file).each():
        gameinfo = GameInfo(chunk)
        assert gameinfo.name not in seen_names
        assert gameinfo.url not in seen_urls
        seen_names.add(gameinfo.name)
        seen_urls.add(gameinfo.url)

        pageurl = gameinfo.url.replace('http://', 'https://')
        if phpbb2:
            pageurl = pageurl.replace('/forum', '/phpbb2')
        game = process_game_page(pageurl, gameinfo)
        print(game.__dict__)

        limit -= 1
        if limit <= 0:
            break

def compare_gamedumps(old_path, new_path):
    "Diff two copies of gamedump.php"

    def load_games(path):
        with open(path, 'r') as fil:
            games = {}
            for chunk in ChunkReader(fil).each():
                gameinfo = GameInfo(chunk)
                games[gameinfo.url] = gameinfo
            return games

    old_games = load_games(old_path)
    new_games = load_games(new_path)

    old = set(old_games.keys())
    new = set(new_games.keys())

    added = [new_games[url] for url in new.difference(old)]
    removed = [old_games[url] for url in old.difference(new)]
    changed = []
    for url in new.intersection(old):
        oldgame = old_games[url]
        newgame = new_games[url]
        if oldgame.serialize() != newgame.serialize():
            changed.append( (oldgame, newgame) )

    return added, removed, changed

def process_one_game(url):
    """
    Calls process_game_page() with gamedump.php entry
    """
    game = process_game_page(url.replace('http://', 'https://'), get_gameinfo(url))
    print(game.__dict__)
    return game

def list_downloads_by_mod_date():
    """
    See which downloads have been modified recently
    (Not used anyway; useful utility function)
    """
    files = []  # timestamp -> info

    file = StringIO(get_gamedump())
    for chunk in ChunkReader(file).each():
        game = GameInfo(chunk)
        ginfo = "%s  %s %s" % (game.name.ljust(42), game.author.ljust(15), game.url)
        for fil in game.files:
            if os.path.splitext(fil.name.lower())[1] not in ('.png'):
                files.append( (fil.date, ginfo + "  " + fil.name))

    files.sort(reverse=1)
    for date, info in files[:52]:
        print(date, info)

def srcid_for_SS_link(url):
    """
    Given a link to a game on SS, returns the srcid for the
    game, or None if it's not a link to a game.
    """
    parsed = urlimp.urlparse(url)
    if (parsed.netloc != "www.slimesalad.com"
        or parsed.path not in ("/forum/viewtopic.php", "/forum/viewgame.php")):
        return None

    query = urlimp.parse_qs(parsed.query)  # Parse to dict containing lists of values
    if 't' in query:
        topicnum = int(query['t'][0])
        # Don't need to fail in this case
        # if topicnum not in link_db['t2p']:
        #     return None
        return topicnum
    elif 'p' in query:
        postnum = int(query['p'][0])
        return link_db['p2t'].get(postnum)
    return None

def normalise_game_url(url):
    "If it's a recognised SS game will remove any other query parameters from the url"
    srcid = srcid_for_SS_link(url)
    if srcid:
        return "https://www.slimesalad.com/forum/viewgame.php?t=" + str(srcid)
    return url

# Used by discord bot
def get_gameinfo(url, cache = CACHE_INDEX) -> GameInfo:
    gamedump = get_gamedump(cache = cache)
    chunks = ChunkReader(StringIO(gamedump))
    url = normalise_game_url(url)
    return chunks.find_game(url)

if __name__ == '__main__':
    #list_downloads_by_mod_date()

    link_db = db_layer.load('ss_links')
    # This is optional (OK to fail loading); used for double checking downloads match
    zips_db = db_layer.load('zips')

    db = gamedb.GameList('ss')
    process_gamedump(phpbb2 = False)
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=7976') #  Double-UTF8 mangled filename
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=38')  # Double-UTF8 mangled filenames
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=8294')
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=6041')  # Two downloads with same filename
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=354')  # Had a (dead) embedded image link
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=8239')  # Inline attachments that are "no longer available"
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=7045')
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=360')
    #process_one_game('http://www.slimesalad.com/forum/viewgame.php?t=6677')  # Code block
    #process_one_game('https://www.slimesalad.com/forum/viewtopic.php?t=38')  # Weird review links
    db.save()
    db_layer.save('ss_links', link_db)
    print(stats)

    # Tests
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewtopic.php?p=15109#15109') == 1021
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewgame.php?t=345') == 345
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewgame.php?t=9999') == None
    assert srcid_for_SS_link('http://www.slimesalad.com/forum/viewtopic.php?t=7123') == None
