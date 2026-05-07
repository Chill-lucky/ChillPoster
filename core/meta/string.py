import bisect
import datetime
import hashlib
import random
import re
from typing import Union, Tuple, Optional, List, Generator
from urllib import parse

import cn2an

from core.meta.types import MediaType

_special_domains = [
    'u2.dmhy.org',
    'pt.ecust.pp.ua',
    'pt.gtkpw.xyz',
    'pt.gtk.pw'
]

_version_map = {"stable": -1, "rc": -2, "beta": -3, "alpha": -4}
_other_version = -5
_max_media_title_words = 10
_min_media_title_length = 2
_non_media_title_pattern = re.compile(r"^#|^请[问帮你]|[?？]$|^继续$")
_chat_intent_pattern = re.compile(r"帮我|请问|怎么|如何|为什么|可以|能否|推荐|介绍|谢谢|想看|找一下|搜一下")
_media_feature_pattern = re.compile(
    r"第\s*[0-9一二三四五六七八九十百零]+\s*[季集]|S\d{1,2}(?:E\d{1,4})?|E\d{1,4}|(?:19|20)\d{2}",
    re.IGNORECASE
)
_media_separator_pattern = re.compile(r"[\s\-_.:：·'\"()\[\]【】]+")
_media_sentence_punctuation_pattern = re.compile(r"[，。！？!?,；;]")
_media_title_char_pattern = re.compile(r"[\u4e00-\u9fffA-Za-z]")


class StringUtils:

    @staticmethod
    def is_chinese(word: Union[str, list]) -> bool:
        if not word:
            return False
        if isinstance(word, list):
            word = " ".join(word)
        chn = re.compile(r'[\u4e00-\u9fff]')
        return bool(chn.search(word))

    @staticmethod
    def is_all_chinese(word: str) -> bool:
        for ch in word:
            if ch == ' ':
                continue
            if '\u4e00' <= ch <= '\u9fff':
                continue
            else:
                return False
        return True

    @staticmethod
    def str_title(s: Optional[str]) -> str:
        return s.title() if s else s

    @staticmethod
    def clear(text: Union[list, str], replace_word: str = "",
              allow_space: bool = False) -> Union[list, str]:
        CONVERT_EMPTY_CHARS = r"[、.。,，·:：;；!！'\'""()（）\[\]【】「」\-—―\+\|\\_/&#～~]"
        if not text:
            return text
        if not isinstance(text, list):
            text = re.sub(r"[\u200B-\u200D\uFEFF]", "",
                          re.sub(r"%s" % CONVERT_EMPTY_CHARS, replace_word, text),
                          flags=re.IGNORECASE)
            if not allow_space:
                return re.sub(r"\s+", "", text)
            else:
                return re.sub(r"\s+", " ", text).strip()
        else:
            return [StringUtils.clear(x) for x in text]

    @staticmethod
    def clear_upper(text: Optional[str]) -> str:
        if not text:
            return ""
        return StringUtils.clear(text).upper().strip()

    @staticmethod
    def is_number(text: str) -> bool:
        if not text:
            return False
        try:
            float(text)
            return True
        except ValueError:
            return False

    @staticmethod
    def get_keyword(content: str) \
            -> Tuple[Optional[MediaType], Optional[str], Optional[int], Optional[int], Optional[str], Optional[str]]:
        if not content:
            return None, None, None, None, None, None
        mtype = MediaType.TV if re.search(r'^(电视剧|动漫|\s+电视剧|\s+动漫)', content) else None
        content = re.sub(r'^(电影|电视剧|动漫|\s+电影|\s+电视剧|\s+动漫)', '', content).strip()
        season_num = None
        episode_num = None
        season_re = re.search(r'第\s*([0-9一二三四五六七八九十]+)\s*季', content, re.IGNORECASE)
        if season_re:
            mtype = MediaType.TV
            season_num = int(cn2an.cn2an(season_re.group(1), mode='smart'))
        episode_re = re.search(r'第\s*([0-9一二三四五六七八九十百零]+)\s*集', content, re.IGNORECASE)
        if episode_re:
            mtype = MediaType.TV
            episode_num = int(cn2an.cn2an(episode_re.group(1), mode='smart'))
            if episode_num and not season_num:
                season_num = 1
        year_re = re.search(r'[\s(]+(\d{4})[\s)]*', content)
        year = year_re.group(1) if year_re else None
        key_word = re.sub(
            r'第\s*[0-9一二三四五六七八九十]+\s*季|第\s*[0-9一二三四五六七八九十百零]+\s*集|[\s(]+(\d{4})[\s)]*', '',
            content, flags=re.IGNORECASE).strip()
        key_word = re.sub(r'\s+', ' ', key_word) if key_word else year
        return mtype, key_word, season_num, episode_num, year, content

    @staticmethod
    def count_words(text: str) -> int:
        if not text:
            return 0
        chinese_pattern = '[\u4e00-\u9fa5]'
        english_pattern = '[a-zA-Z]+'
        chinese_matches = re.findall(chinese_pattern, text)
        english_matches = re.findall(english_pattern, text)
        chinese_words = [word for word in chinese_matches if word.isalpha()]
        english_words = [word for word in english_matches if word.isalpha()]
        return len(chinese_words) + len(english_words)

    @staticmethod
    def num_filesize(text: Union[str, int, float]) -> int:
        if not text:
            return 0
        if not isinstance(text, str):
            text = str(text)
        if text.isdigit():
            return int(text)
        text = text.replace(",", "").replace(" ", "").upper()
        size = re.sub(r"[KMGTPI]*B?", "", text, flags=re.IGNORECASE)
        try:
            size = float(size)
        except ValueError:
            return 0
        if text.find("PB") != -1 or text.find("PIB") != -1:
            size *= 1024 ** 5
        elif text.find("TB") != -1 or text.find("TIB") != -1:
            size *= 1024 ** 4
        elif text.find("GB") != -1 or text.find("GIB") != -1:
            size *= 1024 ** 3
        elif text.find("MB") != -1 or text.find("MIB") != -1:
            size *= 1024 ** 2
        elif text.find("KB") != -1 or text.find("KIB") != -1:
            size *= 1024
        return round(size)

    @staticmethod
    def str_filesize(size: Union[str, float, int], pre: int = 2) -> str:
        if size is None:
            return ""
        size = re.sub(r"\s|B|iB", "", str(size), re.I)
        if size.replace(".", "").isdigit():
            try:
                size = float(size)
                d = [(1024 - 1, 'K'), (1024 ** 2 - 1, 'M'), (1024 ** 3 - 1, 'G'), (1024 ** 4 - 1, 'T')]
                s = [x[0] for x in d]
                index = bisect.bisect_left(s, size) - 1
                if index == -1:
                    return str(size) + "B"
                else:
                    b, u = d[index]
                return str(round(size / (b + 1), pre)) + u
            except ValueError:
                return ""
        if re.findall(r"[KMGTP]", size, re.I):
            return size
        else:
            return size + "B"

    @staticmethod
    def format_size(size_bytes: int) -> str:
        if not size_bytes or size_bytes == 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = float(size_bytes)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        return f"{size:.2f} {units[unit_index]}"

    @staticmethod
    def safe_strip(value) -> Optional[str]:
        return value.strip() if value is not None else None

    @staticmethod
    def escape_markdown(content: str) -> str:
        parses = re.sub(r"([_*\[\]()~`>#+\-=|.!{}])", r"\\\1", content)
        reparse = re.sub(r"\\\\([_*\[\]()~`>#+\-=|.!{}])", r"\1", parses)
        return reparse

    @staticmethod
    def natural_sort_key(text: str) -> List[Union[int, str]]:
        if text is None:
            return []
        if not isinstance(text, str):
            text = str(text)
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]

    @staticmethod
    def generate_random_str(randomlength: int = 16) -> str:
        random_str = ''
        base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789'
        length = len(base_str) - 1
        for i in range(randomlength):
            random_str += base_str[random.randint(0, length)]
        return random_str

    @staticmethod
    def md5_hash(data) -> str:
        if not data:
            return ""
        return hashlib.md5(str(data).encode()).hexdigest()
