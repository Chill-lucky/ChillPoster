from pathlib import Path
from typing import Tuple

import regex as re

from core.meta.metabase import MetaBase
from core.meta.metavideo import MetaVideo
from core.meta.metaanime import MetaAnime
from core.meta.words import WordsMatcher
from core.meta.types import MediaType


def MetaInfo(title: str, subtitle: str = None) -> MetaBase:
    """
    根据标题和副标题识别元数据
    """
    org_title = title
    title, apply_words = WordsMatcher().prepare(title)
    title, metainfo = find_metainfo(title)
    isfile = bool(title and Path(title).suffix.lower() in [
        '.mp4', '.mpg', '.mkv', '.mpeg', '.ts', '.vob', '.iso', '.m4v',
        '.avi', '.3gp', '.wmv', '.webm', '.flv', '.mov', '.m2ts', '.rmvb',
        '.rm', '.asf', '.f4v', '.m2t', '.mts', '.mpe', '.tp', '.trp',
        '.divx', '.ogv', '.dv', '.strm'
    ])
    if isfile:
        title = Path(title).stem
    meta = MetaAnime(title, subtitle, isfile) if is_anime(title) else MetaVideo(title, subtitle, isfile)
    meta.title = org_title
    meta.apply_words = apply_words or []
    if metainfo.get('tmdbid'):
        try:
            meta.tmdbid = int(metainfo['tmdbid'])
        except ValueError:
            pass
    if metainfo.get('doubanid'):
        meta.doubanid = metainfo['doubanid']
    if metainfo.get('type'):
        meta.type = metainfo['type']
    if metainfo.get('begin_season'):
        meta.begin_season = metainfo['begin_season']
    if metainfo.get('end_season'):
        meta.end_season = metainfo['end_season']
    if metainfo.get('total_season'):
        meta.total_season = metainfo['total_season']
    if metainfo.get('begin_episode'):
        meta.begin_episode = metainfo['begin_episode']
    if metainfo.get('end_episode'):
        meta.end_episode = metainfo['end_episode']
    if metainfo.get('total_episode'):
        meta.total_episode = metainfo['total_episode']
    return meta


def MetaInfoPath(path: Path) -> MetaBase:
    """
    根据路径识别元数据，三级目录合并
    """
    file_meta = MetaInfo(title=path.name)
    file_meta.merge(MetaInfo(title=path.parent.name))
    file_meta.merge(MetaInfo(title=path.parent.parent.name))
    return file_meta


def is_anime(name: str) -> bool:
    """
    判断是否为动漫
    """
    if not name:
        return False
    if re.search(r'【[+0-9XVPI-]+】\s*【', name, re.IGNORECASE):
        return True
    if re.search(r'\s+-\s+[\dv]{1,4}\s+', name, re.IGNORECASE):
        return True
    if re.search(r"S\d{2}\s*-\s*S\d{2}|S\d{2}|\s+S\d{1,2}|EP?\d{2,4}\s*-\s*EP?\d{2,4}|EP?\d{2,4}|\s+EP?\d{1,4}", name, re.IGNORECASE):
        return False
    if re.search(r'\[[+0-9XVPI-]+]\s*\[', name, re.IGNORECASE):
        return True
    return False


def find_metainfo(title: str) -> Tuple[str, dict]:
    """
    从标题中提取内嵌元数据 {[tmdbid=xxx;type=xxx;s=x;e=x]}
    """
    metainfo = {
        'tmdbid': None, 'doubanid': None, 'type': None,
        'begin_season': None, 'end_season': None, 'total_season': None,
        'begin_episode': None, 'end_episode': None, 'total_episode': None,
    }
    if not title:
        return title, metainfo
    results = re.findall(r'(?<={\[)[\W\w]+(?=]})', title)
    if not results:
        return title, metainfo
    for result in results:
        tmdbid = re.findall(r'(?<=tmdbid=)\d+', result)
        if tmdbid and tmdbid[0].isdigit():
            metainfo['tmdbid'] = tmdbid[0]
        doubanid = re.findall(r'(?<=doubanid=)\d+', result)
        if doubanid and doubanid[0].isdigit():
            metainfo['doubanid'] = doubanid[0]
        mtype = re.findall(r'(?<=type=)\w+', result)
        if mtype:
            if mtype[0] == "movie":
                metainfo['type'] = MediaType.MOVIE
            elif mtype[0] == "tv":
                metainfo['type'] = MediaType.TV
        begin_season = re.findall(r'(?<=s=)\d+', result)
        if begin_season and begin_season[0].isdigit():
            metainfo['begin_season'] = int(begin_season[0])
        end_season = re.findall(r'(?<=s=\d+-)\d+', result)
        if end_season and end_season[0].isdigit():
            metainfo['end_season'] = int(end_season[0])
        begin_episode = re.findall(r'(?<=e=)\d+', result)
        if begin_episode and begin_episode[0].isdigit():
            metainfo['begin_episode'] = int(begin_episode[0])
        end_episode = re.findall(r'(?<=e=\d+-)\d+', result)
        if end_episode and end_episode[0].isdigit():
            metainfo['end_episode'] = int(end_episode[0])
        if tmdbid or mtype or begin_season or end_season or begin_episode or end_episode:
            title = title.replace(f"{{[{result}]}}", '')
    if metainfo.get('begin_season') and metainfo.get('end_season'):
        if metainfo['begin_season'] > metainfo['end_season']:
            metainfo['begin_season'], metainfo['end_season'] = metainfo['end_season'], metainfo['begin_season']
        metainfo['total_season'] = metainfo['end_season'] - metainfo['begin_season'] + 1
    elif metainfo.get('begin_season'):
        metainfo['total_season'] = 1
    if metainfo.get('begin_episode') and metainfo.get('end_episode'):
        if metainfo['begin_episode'] > metainfo['end_episode']:
            metainfo['begin_episode'], metainfo['end_episode'] = metainfo['end_episode'], metainfo['begin_episode']
        metainfo['total_episode'] = metainfo['end_episode'] - metainfo['begin_episode'] + 1
    elif metainfo.get('begin_episode'):
        metainfo['total_episode'] = 1
    return title, metainfo
