#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from .exceptions import CreateDirectoryException, MissingEnv
from redis import Redis
from redis.exceptions import ConnectionError
from datetime import datetime, timedelta
import time
import asyncio
from functools import lru_cache

from typing import Dict

def get_storage_path() -> Path:
    if not os.environ.get('VIRTUAL_ENV'):
        raise MissingEnv("VIRTUAL_ENV is missing. This project really wants to run from a virtual envoronment.")
    return Path(os.environ['VIRTUAL_ENV'])


@lru_cache(64)
def get_homedir() -> Path:
    if not os.environ.get('UWHOISD_HOME'):
        # Try to open a .env file in the home directory if it exists.
        if (Path(__file__).resolve().parent.parent / '.env').exists():
            with (Path(__file__).resolve().parent.parent / '.env').open() as f:
                for line in f:
                    key, value = line.strip().split('=', 1)
                    if value[0] in ['"', "'"]:
                        value = value[1:-1]
                    os.environ[key] = value

    if not os.environ.get('UWHOISD_HOME'):
        guessed_home = Path(__file__).resolve().parent.parent
        raise MissingEnv(f"UWHOISD_HOME is missing. \
Run the following command (assuming you run the code from the clonned repository):\
    export UWHOISD_HOME='{guessed_home}'")
    return Path(os.environ['UWHOISD_HOME'])


def safe_create_dir(to_create: Path) -> None:
    if to_create.exists() and not to_create.is_dir():
        raise CreateDirectoryException(f'The path {to_create} already exists and is not a directory')
    os.makedirs(to_create, exist_ok=True)


def set_running(name: str) -> None:
    r = Redis(unix_socket_path=get_socket_path('cache'), db=2, decode_responses=True)
    r.hset('running', name, 1)


def unset_running(name: str) -> None:
    r = Redis(unix_socket_path=get_socket_path('cache'), db=2, decode_responses=True)
    r.hdel('running', name)


def is_running() -> Dict[str, str]:
    r = Redis(unix_socket_path=get_socket_path('cache'), db=2, decode_responses=True)
    return r.hgetall('running')


def get_socket_path(name: str) -> str:
    mapping = {
        'cache': Path('cache', 'cache.sock'),
        'whowas': Path('whowas', 'whowas.sock'),
    }
    return str(get_homedir() / mapping[name])


def check_running(name: str) -> bool:
    socket_path = get_socket_path(name)
    try:
        r = Redis(unix_socket_path=socket_path)
        return True if r.ping() else False
    except ConnectionError:
        return False


def shutdown_requested() -> bool:
    try:
        r = Redis(unix_socket_path=get_socket_path('cache'), db=2, decode_responses=True)
        return True if r.exists('shutdown') else False
    except ConnectionRefusedError:
        return True
    except ConnectionError:
        return True


async def long_sleep_async(sleep_in_sec: int, shutdown_check: int=10) -> bool:
    if shutdown_check > sleep_in_sec:
        shutdown_check = sleep_in_sec
    sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
    while sleep_until > datetime.now():
        await asyncio.sleep(shutdown_check)
        if shutdown_requested():
            return False
    return True


def long_sleep(sleep_in_sec: int, shutdown_check: int=10) -> bool:
    if shutdown_check > sleep_in_sec:
        shutdown_check = sleep_in_sec
    sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
    while sleep_until > datetime.now():
        time.sleep(shutdown_check)
        if shutdown_requested():
            return False
    return True
