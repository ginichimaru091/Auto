import logging
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from info import AUTH_CHANNEL, LONG_IMDB_DESCRIPTION, IS_VERIFY, SETTINGS, START_IMG
from imdb import Cinemagoer
import asyncio
from pyrogram.types import Message
from pyrogram import enums
import pytz, re, os
from shortzy import Shortzy
from datetime import datetime
from typing import Any
from database.users_chats_db import db

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BANNED = {}
imdb = Cinemagoer()

class Temp:
    ME = None
    CURRENT = int(os.environ.get("SKIP", 2))
    CANCEL = False
    U_NAME = None
    B_NAME = None
    B_LINK = None
    SETTINGS = {}
    FILES_ID = {}
    USERS_CANCEL = False
    GROUPS_CANCEL = False
    CHAT = {}
    BANNED_USERS = []
    BANNED_CHATS = []

temp = Temp()

def formate_file_name(file_name):
    """Formats file name by removing unwanted prefixes."""
    return ' '.join(
        filter(
            lambda x: not x.startswith(('[@', '[www.')),
            file_name.split()
        )
    )

async def is_req_subscribed(bot, query):
    """Checks if the user is subscribed to a required channel."""
    try:
        if await db.find_join_req(query.from_user.id):
            return True

        user = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
        if user.status != enums.ChatMemberStatus.BANNED:
            return True
    except UserNotParticipant:
        pass
    except Exception as e:
        logger.exception(f"Error in is_req_subscribed: {e}")
    return False

def list_to_str(data):
    """Converts a list to a comma-separated string."""
    if not data:
        return "N/A"
    return ', '.join(map(str, data))

async def get_poster(query, bulk=False, id=False, file=None):
    """Fetches movie details from IMDb."""
    try:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r'[1-2]\d{3}$', query)
            if year:
                year = year[0]
                title = query.replace(year, "").strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file)
                year = year[0] if year else None

            movies = imdb.search_movie(title.lower(), results=10)
            if not movies:
                return None

            if year:
                movies = [m for m in movies if str(m.get('year')) == str(year)]
            movies = [m for m in movies if m.get('kind') in ['movie', 'tv series']]

            if bulk:
                return movies
            movie_id = movies[0].movieID
        else:
            movie_id = query

        movie = imdb.get_movie(movie_id)
        date = movie.get("original air date") or movie.get("year") or "N/A"
        plot = movie.get('plot outline') if LONG_IMDB_DESCRIPTION else movie.get('plot', [""])[0]
        plot = (plot[:800] + "...") if plot and len(plot) > 800 else plot

        return {
            'title': movie.get('title'),
            'votes': movie.get('votes'),
            "aka": list_to_str(movie.get("akas")),
            "seasons": movie.get("number of seasons"),
            "box_office": movie.get('box office'),
            'localized_title': movie.get('localized title'),
            'kind': movie.get("kind"),
            "imdb_id": f"tt{movie_id}",
            "cast": list_to_str(movie.get("cast")),
            "runtime": list_to_str(movie.get("runtimes")),
            "countries": list_to_str(movie.get("countries")),
            "certificates": list_to_str(movie.get("certificates")),
            "languages": list_to_str(movie.get("languages")),
            "director": list_to_str(movie.get("director")),
            "writer": list_to_str(movie.get("writer")),
            "producer": list_to_str(movie.get("producer")),
            "composer": list_to_str(movie.get("composer")),
            "cinematographer": list_to_str(movie.get("cinematographer")),
            "music_team": list_to_str(movie.get("music department")),
            "distributors": list_to_str(movie.get("distributors")),
            'release_date': date,
            'year': movie.get('year'),
            'genres': list_to_str(movie.get("genres")),
            'poster': movie.get('full-size cover url') or START_IMG,
            'plot': plot,
            'rating': str(movie.get("rating")),
            'url': f'https://www.imdb.com/title/tt{movie_id}'
        }
    except Exception as e:
        logger.exception(f"Error in get_poster: {e}")
        return None

async def users_broadcast(user_id, message, is_pin):
    """Broadcasts a message to users."""
    try:
        m = await message.copy(chat_id=user_id)
        if is_pin:
            await m.pin(both_sides=True)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await users_broadcast(user_id, message, is_pin)
    except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid) as e:
        await db.delete_user(user_id)
        logger.info(f"Removed user {user_id} from DB: {e}")
        return False, str(e)
    except Exception as e:
        logger.exception(f"Error in users_broadcast: {e}")
        return False, "Error"

async def groups_broadcast(chat_id, message, is_pin):
    """Broadcasts a message to groups."""
    try:
        m = await message.copy(chat_id=chat_id)
        if is_pin:
            try:
                await m.pin()
            except:
                pass
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await groups_broadcast(chat_id, message, is_pin)
    except Exception as e:
        await db.delete_chat(chat_id)
        logger.exception(f"Error in groups_broadcast: {e}")
        return "Error"

async def get_settings(group_id, pm_mode=False):
    """Retrieves group or PM mode settings."""
    return SETTINGS.copy() if pm_mode else await db.get_settings(group_id)

async def save_group_settings(group_id, key, value):
    """Updates and saves group settings."""
    current = await get_settings(group_id)
    current.update({key: value})
    temp.SETTINGS.update({group_id: current})
    await db.update_settings(group_id, current)

def get_size(size):
    """Returns human-readable file size."""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def get_readable_time(seconds):
    """Converts seconds to a readable time format."""
    periods = [('days', 86400), ('hours', 3600), ('minutes', 60), ('seconds', 1)]
    result = []
    for period, period_seconds in periods:
        if seconds >= period_seconds:
            value, seconds = divmod(seconds, period_seconds)
            result.append(f"{int(value)} {period}")
    return ', '.join(result)

async def save_default_settings(group_id):
    """Resets and saves default group settings."""
    await db.reset_group_settings(group_id)
    current = await db.get_settings(group_id)
    temp.SETTINGS.update({group_id: current})
    BANNED_CHATS = []
def formate_file_name(file_name):
    file_name = ' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name
async def is_req_subscribed(bot, query):
    if await db.find_join_req(query.from_user.id):
        return True
    try:
        user = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
    except UserNotParticipant:
        pass
    except Exception as e:
        logger.exception(e)
    else:
        if user.status != enums.ChatMemberStatus.BANNED:
            return True
    return False

async def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1]) 
        else:
            year = None
        movieid = imdb.search_movie(title.lower(), results=10)
        if not movieid:
            return None
        if year:
            filtered=list(filter(lambda k: str(k.get('year')) == str(year), movieid))
            if not filtered:
                filtered = movieid
        else:
            filtered = movieid
        movieid=list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
        if not movieid:
            movieid = filtered
        if bulk:
            return movieid
        movieid = movieid[0].movieID
    else:
        movieid = query
    movie = imdb.get_movie(movieid)
    if movie.get("original air date"):
        date = movie["original air date"]
    elif movie.get("year"):
        date = movie.get("year")
    else:
        date = "N/A"
    plot = ""
    if not LONG_IMDB_DESCRIPTION:
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
    else:
        plot = movie.get('plot outline')
    if plot and len(plot) > 800:
        plot = plot[0:800] + "..."

    return {
        'title': movie.get('title'),
        'votes': movie.get('votes'),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(movie.get("runtimes")),
        "countries": list_to_str(movie.get("countries")),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_str(movie.get("languages")),
