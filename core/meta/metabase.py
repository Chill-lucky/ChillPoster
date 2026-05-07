import traceback
from dataclasses import dataclass
from typing import Union, Optional, List, Self

import cn2an
import regex as re

from core.logger import logger
from core.meta.types import MediaType
from core.meta.string import StringUtils


@dataclass
class MetaBase(object):
    """
    媒体信息基类
    """
    isfile: bool = False
    title: str = ""
    org_string: Optional[str] = None
    subtitle: Optional[str] = None
    type: MediaType = MediaType.UNKNOWN
    cn_name: Optional[str] = None
    en_name: Optional[str] = None
    year: Optional[str] = None
    total_season: int = 0
    begin_season: Optional[int] = None
    end_season: Optional[int] = None
    total_episode: int = 0
    begin_episode: Optional[int] = None
    end_episode: Optional[int] = None
    part: Optional[str] = None
    resource_type: Optional[str] = None
    resource_effect: Optional[str] = None
    video_effect: Optional[str] = None
    resource_pix: Optional[str] = None
    resource_team: Optional[str] = None
    customization: Optional[str] = None
    web_source: Optional[str] = None
    video_encode: Optional[str] = None
    audio_encode: Optional[str] = None
    apply_words: Optional[List[str]] = None
    tmdbid: int = None
    doubanid: str = None
    fps: Optional[int] = None

    _subtitle_flag = False
    _title_episodel_re = r"Episode\s+(\d{1,4})"
    _subtitle_season_re = r"(?<![全共]\s*)[第\s]+([0-9一二三四五六七八九十S\-]+)\s*季(?!\s*[全共])"
    _subtitle_season_all_re = r"[全共]\s*([0-9一二三四五六七八九十]+)\s*季|([0-9一二三四五六七八九十]+)\s*季\s*全"
    _subtitle_episode_re = r"(?<![全共]\s*)[第\s]+([0-9一二三四五六七八九十百零EP]+)\s*[集话話期幕](?!\s*[全共])"
    _subtitle_episode_between_re = r"[第]*\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]?\s*-\s*第*\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]"
    _subtitle_episode_all_re = r"([0-9一二三四五六七八九十百零]+)\s*集\s*全|[全共]\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]"

    def __init__(self, title: str, subtitle: str = None, isfile: bool = False):
        if not title:
            return
        self.org_string = title.strip() if title else None
        self.subtitle = subtitle.strip() if subtitle else None
        self.isfile = isfile

    @property
    def name(self) -> str:
        if self.cn_name and StringUtils.is_all_chinese(self.cn_name):
            return self.cn_name
        elif self.en_name:
            return self.en_name
        elif self.cn_name:
            return self.cn_name
        return ""

    @name.setter
    def name(self, name: str):
        if StringUtils.is_all_chinese(name):
            self.cn_name = name
        else:
            self.en_name = name
            self.cn_name = None

    def init_subtitle(self, title_text: str):
        if not title_text:
            return
        title_text = f" {title_text} "
        if re.search(r"%s" % self._title_episodel_re, title_text, re.IGNORECASE):
            episode_str = re.search(r'%s' % self._title_episodel_re, title_text, re.IGNORECASE)
            if episode_str:
                try:
                    episode = int(episode_str.group(1))
                except Exception as err:
                    logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                    return
                if episode >= 10000:
                    return
                if self.begin_episode is None:
                    self.begin_episode = episode
                    self.total_episode = 1
                self.type = MediaType.TV
                self._subtitle_flag = True
        elif re.search(r'[全第季集话話期幕]', title_text, re.IGNORECASE):
            season_all_str = re.search(r"%s" % self._subtitle_season_all_re, title_text, re.IGNORECASE)
            if season_all_str:
                season_all = season_all_str.group(1)
                if not season_all:
                    season_all = season_all_str.group(2)
                if season_all and self.begin_season is None and self.begin_episode is None:
                    try:
                        self.total_season = int(cn2an.cn2an(season_all.strip(), mode='smart'))
                    except Exception as err:
                        logger.debug(f'识别季失败：{str(err)} - {traceback.format_exc()}')
                        return
                    self.begin_season = 1
                    self.end_season = self.total_season
                    self.type = MediaType.TV
                    self._subtitle_flag = True
                return
            season_str = re.search(r'%s' % self._subtitle_season_re, title_text, re.IGNORECASE)
            if season_str:
                seasons = season_str.group(1)
                if seasons:
                    seasons = seasons.upper().replace("S", "").strip()
                else:
                    return
                try:
                    end_season = None
                    if seasons.find('-') != -1:
                        seasons = seasons.split('-')
                        begin_season = int(cn2an.cn2an(seasons[0].strip(), mode='smart'))
                        if len(seasons) > 1:
                            end_season = int(cn2an.cn2an(seasons[1].strip(), mode='smart'))
                    else:
                        begin_season = int(cn2an.cn2an(seasons, mode='smart'))
                except Exception as err:
                    logger.debug(f'识别季失败：{str(err)} - {traceback.format_exc()}')
                    return
                if begin_season and begin_season > 100:
                    return
                if end_season and end_season > 100:
                    return
                if self.begin_season is None and isinstance(begin_season, int):
                    self.begin_season = begin_season
                    self.total_season = 1
                if self.begin_season is not None \
                        and self.end_season is None \
                        and isinstance(end_season, int) \
                        and end_season != self.begin_season:
                    self.end_season = end_season
                    self.total_season = (self.end_season - self.begin_season) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
            episode_between_str = re.search(r'%s' % self._subtitle_episode_between_re, title_text, re.IGNORECASE)
            if episode_between_str:
                episodes = episode_between_str.groups()
                if episodes:
                    begin_episode = episodes[0]
                    end_episode = episodes[1]
                else:
                    return
                try:
                    begin_episode = int(cn2an.cn2an(begin_episode.strip(), mode='smart'))
                    end_episode = int(cn2an.cn2an(end_episode.strip(), mode='smart'))
                except Exception as err:
                    logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                    return
                if begin_episode and begin_episode >= 10000:
                    return
                if end_episode and end_episode >= 10000:
                    return
                if self.begin_episode is None and isinstance(begin_episode, int):
                    self.begin_episode = begin_episode
                    self.total_episode = 1
                if self.begin_episode is not None \
                        and self.end_episode is None \
                        and isinstance(end_episode, int) \
                        and end_episode != self.begin_episode:
                    self.end_episode = end_episode
                    self.total_episode = (self.end_episode - self.begin_episode) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
                return
            episode_str = re.search(r'%s' % self._subtitle_episode_re, title_text, re.IGNORECASE)
            if episode_str:
                episodes = episode_str.group(1)
                if episodes:
                    episodes = episodes.upper().replace("E", "").replace("P", "").strip()
                else:
                    return
                try:
                    end_episode = None
                    if episodes.find('-') != -1:
                        episodes = episodes.split('-')
                        begin_episode = int(cn2an.cn2an(episodes[0].strip(), mode='smart'))
                        if len(episodes) > 1:
                            end_episode = int(cn2an.cn2an(episodes[1].strip(), mode='smart'))
                    else:
                        begin_episode = int(cn2an.cn2an(episodes, mode='smart'))
                except Exception as err:
                    logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                    return
                if begin_episode and begin_episode >= 10000:
                    return
                if end_episode and end_episode >= 10000:
                    return
                if self.begin_episode is None and isinstance(begin_episode, int):
                    self.begin_episode = begin_episode
                    self.total_episode = 1
                if self.begin_episode is not None \
                        and self.end_episode is None \
                        and isinstance(end_episode, int) \
                        and end_episode != self.begin_episode:
                    self.end_episode = end_episode
                    self.total_episode = (self.end_episode - self.begin_episode) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
                return
            episode_all_str = re.search(r'%s' % self._subtitle_episode_all_re, title_text, re.IGNORECASE)
            if episode_all_str:
                episode_all = episode_all_str.group(1)
                if not episode_all:
                    episode_all = episode_all_str.group(2)
                if episode_all and self.begin_episode is None:
                    try:
                        self.total_episode = int(cn2an.cn2an(episode_all.strip(), mode='smart'))
                    except Exception as err:
                        logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                        return
                    self.type = MediaType.TV
                    self._subtitle_flag = True
                return

    @property
    def season(self) -> str:
        if self.begin_season is not None:
            return "S%s" % str(self.begin_season).rjust(2, "0") \
                if self.end_season is None \
                else "S%s-S%s" % \
                     (str(self.begin_season).rjust(2, "0"),
                      str(self.end_season).rjust(2, "0"))
        else:
            if self.type == MediaType.TV:
                return "S01"
            else:
                return ""

    @property
    def sea(self) -> str:
        if self.begin_season is not None:
            return self.season
        else:
            return ""

    @property
    def season_seq(self) -> str:
        if self.begin_season is not None:
            return str(self.begin_season)
        else:
            if self.type == MediaType.TV:
                return "1"
            else:
                return ""

    @property
    def season_list(self) -> List[int]:
        if self.begin_season is None:
            if self.type == MediaType.TV:
                return [1]
            else:
                return []
        elif self.end_season is not None:
            return [season for season in range(self.begin_season, self.end_season + 1)]
        else:
            return [self.begin_season]

    @property
    def episode(self) -> str:
        if self.begin_episode is not None:
            return "E%s" % str(self.begin_episode).rjust(2, "0") \
                if self.end_episode is None \
                else "E%s-E%s" % \
                     (
                         str(self.begin_episode).rjust(2, "0"),
                         str(self.end_episode).rjust(2, "0"))
        else:
            return ""

    @property
    def episode_list(self) -> List[int]:
        if self.begin_episode is None:
            return []
        elif self.end_episode is not None:
            return [episode for episode in range(self.begin_episode, self.end_episode + 1)]
        else:
            return [self.begin_episode]

    @property
    def episodes(self) -> str:
        return "E%s" % "E".join(str(episode).rjust(2, '0') for episode in self.episode_list)

    @property
    def episode_seqs(self) -> str:
        episodes = self.episode_list
        if episodes:
            if len(episodes) == 1:
                return str(episodes[0])
            else:
                return "%s-%s" % (episodes[0], episodes[-1])
        else:
            return ""

    @property
    def episode_seq(self) -> str:
        episodes = self.episode_list
        if episodes:
            return str(episodes[0])
        else:
            return ""

    @property
    def season_episode(self) -> str:
        if self.type == MediaType.TV:
            seaion = self.season
            episode = self.episode
            if seaion and episode:
                return "%s %s" % (seaion, episode)
            elif seaion:
                return "%s" % seaion
            elif episode:
                return "%s" % episode
        else:
            return ""
        return ""

    @property
    def resource_term(self) -> str:
        ret_string = ""
        if self.resource_type:
            ret_string = f"{ret_string} {self.resource_type}"
        if self.resource_effect:
            ret_string = f"{ret_string} {self.resource_effect}"
        if self.resource_pix:
            ret_string = f"{ret_string} {self.resource_pix}"
        return ret_string

    @property
    def edition(self) -> str:
        ret_string = ""
        if self.resource_type:
            ret_string = f"{ret_string} {self.resource_type}"
        if self.resource_effect:
            ret_string = f"{ret_string} {self.resource_effect}"
        return ret_string.strip()

    @property
    def release_group(self) -> str:
        if self.resource_team:
            return self.resource_team
        else:
            return ""

    @property
    def video_term(self) -> str:
        return self.video_encode or ""

    @property
    def audio_term(self) -> str:
        return self.audio_encode or ""

    @property
    def frame_rate(self) -> int:
        return self.fps or None

    def is_in_season(self, season: Union[list, int, str]) -> bool:
        if isinstance(season, list):
            if self.end_season is not None:
                meta_season = list(range(self.begin_season, self.end_season + 1))
            else:
                if self.begin_season is not None:
                    meta_season = [self.begin_season]
                else:
                    meta_season = [1]
            return set(meta_season).issuperset(set(season))
        else:
            if self.end_season is not None:
                return self.begin_season <= int(season) <= self.end_season
            else:
                if self.begin_season is not None:
                    return int(season) == self.begin_season
                else:
                    return int(season) == 1

    def is_in_episode(self, episode: Union[list, int, str]) -> bool:
        if isinstance(episode, list):
            if self.end_episode is not None:
                meta_episode = list(range(self.begin_episode, self.end_episode + 1))
            else:
                meta_episode = [self.begin_episode]
            return set(meta_episode).issuperset(set(episode))
        else:
            if self.end_episode is not None:
                return self.begin_episode <= int(episode) <= self.end_episode
            else:
                return int(episode) == self.begin_episode

    def set_season(self, sea: Union[list, int, str]):
        if not sea:
            return
        if isinstance(sea, list):
            if len(sea) == 1 and str(sea[0]).isdigit():
                self.begin_season = int(sea[0])
                self.end_season = None
            elif len(sea) > 1 and str(sea[0]).isdigit() and str(sea[-1]).isdigit():
                self.begin_season = int(sea[0])
                self.end_season = int(sea[-1])
        elif str(sea).isdigit():
            self.begin_season = int(sea)
            self.end_season = None

    def set_episode(self, ep: Union[list, int, str]):
        if not ep:
            return
        if isinstance(ep, list):
            if len(ep) == 1 and str(ep[0]).isdigit():
                self.begin_episode = int(ep[0])
                self.end_episode = None
            elif len(ep) > 1 and str(ep[0]).isdigit() and str(ep[-1]).isdigit():
                self.begin_episode = int(ep[0])
                self.end_episode = int(ep[-1])
                self.total_episode = (self.end_episode - self.begin_episode) + 1
        elif str(ep).isdigit():
            self.begin_episode = int(ep)
            self.end_episode = None

    def set_episodes(self, begin: int, end: int):
        if begin:
            self.begin_episode = begin
        if end:
            self.end_episode = end
        if self.begin_episode and self.end_episode:
            self.total_episode = (self.end_episode - self.begin_episode) + 1

    def merge(self, meta: Self):
        if self.type == MediaType.UNKNOWN \
                and meta.type != MediaType.UNKNOWN:
            self.type = meta.type
        if not self.name:
            self.cn_name = meta.cn_name
            self.en_name = meta.en_name
        if not self.year:
            self.year = meta.year
        if (self.type == MediaType.TV
                and self.begin_season is None):
            self.begin_season = meta.begin_season
            self.end_season = meta.end_season
            self.total_season = meta.total_season
        if (self.type == MediaType.TV
                and self.begin_episode is None):
            self.begin_episode = meta.begin_episode
            self.end_episode = meta.end_episode
            self.total_episode = meta.total_episode
        if not self.resource_type:
            self.resource_type = meta.resource_type
        if not self.resource_pix:
            self.resource_pix = meta.resource_pix
        if not self.resource_team:
            self.resource_team = meta.resource_team
        if not self.customization:
            self.customization = meta.customization
        if not self.resource_effect:
            self.resource_effect = meta.resource_effect
        if not self.video_effect:
            self.video_effect = meta.video_effect
        if not self.video_encode:
            self.video_encode = meta.video_encode
        if not self.audio_encode:
            self.audio_encode = meta.audio_encode
        if not self.fps:
            self.fps = meta.fps
        if not self.part:
            self.part = meta.part
        if not self.tmdbid and meta.tmdbid:
            self.tmdbid = meta.tmdbid
        if not self.doubanid and meta.doubanid:
            self.doubanid = meta.doubanid

    def to_dict(self):
        dicts = vars(self).copy()
        dicts["type"] = self.type.value if self.type else None
        dicts["season_episode"] = self.season_episode
        dicts["edition"] = self.edition
        dicts["name"] = self.name
        dicts["episode_list"] = self.episode_list
        return dicts
