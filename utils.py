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
logger = logging.getLogger(name)
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
            }
