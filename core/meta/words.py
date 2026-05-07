from typing import List, Tuple

import cn2an
import regex as re

from core.logger import logger
from core.meta.singleton import Singleton


class WordsMatcher(metaclass=Singleton):

    def __init__(self):
        self._custom_words = []

    def set_custom_words(self, words: List[str]):
        self._custom_words = words

    def prepare(self, title: str, custom_words: List[str] = None) -> Tuple[str, List[str]]:
        appley_words = []
        words: List[str] = custom_words or self._custom_words or []
        for word in words:
            if not word or word.startswith("#"):
                continue
            try:
                if word.count(" => ") and word.count(" && ") and word.count(" >> ") and word.count(" <> "):
                    thc = str(re.findall(r'(.*?)\s*=>', word)[0]).strip()
                    bthc = str(re.findall(r'=>\s*(.*?)\s*&&', word)[0]).strip()
                    pyq = str(re.findall(r'&&\s*(.*?)\s*<>', word)[0]).strip()
                    pyh = str(re.findall(r'<>(.*?)\s*>>', word)[0]).strip()
                    offsets = str(re.findall(r'>>\s*(.*?)$', word)[0]).strip()
                    title, message, state = self.__replace_regex(title, thc, bthc)
                    if state:
                        title, message, state = self.__episode_offset(title, pyq, pyh, offsets)
                elif word.count(" => "):
                    strings = word.split(" => ")
                    title, message, state = self.__replace_regex(title, strings[0], strings[1])
                elif word.count(" >> ") and word.count(" <> "):
                    strings = word.split(" <> ")
                    offsets = strings[1].split(" >> ")
                    strings[1] = offsets[0]
                    title, message, state = self.__episode_offset(title, strings[0], strings[1], offsets[1])
                else:
                    if not word.strip():
                        continue
                    title, message, state = self.__replace_regex(title, word, "")
                if state:
                    appley_words.append(word)
            except Exception as err:
                logger.warn(f"自定义识别词 {word} 预理标题失败：{str(err)} - 标题：{title}")
        return title, appley_words

    @staticmethod
    def __replace_regex(title: str, replaced: str, replace: str) -> Tuple[str, str, bool]:
        try:
            if not re.findall(r'%s' % replaced, title):
                return title, "", False
            else:
                return re.sub(r'%s' % replaced, r'%s' % replace, title), "", True
        except Exception as err:
            return title, str(err), False

    @staticmethod
    def __episode_offset(title: str, front: str, back: str, offset: str) -> Tuple[str, str, bool]:
        try:
            if back and not re.findall(r'%s' % back, title):
                return title, "", False
            if front and not re.findall(r'%s' % front, title):
                return title, "", False
            offset_word_info_re = re.compile(r'(?<=%s.*?)[0-9一二三四五六七八九十]+(?=.*?%s)' % (front, back))
            episode_nums_str = re.findall(offset_word_info_re, title)
            if not episode_nums_str:
                return title, "", False
            episode_nums_offset_str = []
            offset_order_flag = False
            for episode_num_str in episode_nums_str:
                episode_num_int = int(cn2an.cn2an(episode_num_str, "smart"))
                offset_caculate = offset.replace("EP", str(episode_num_int))
                episode_num_offset_int = int(eval(offset_caculate))
                if episode_num_int > episode_num_offset_int:
                    offset_order_flag = True
                elif episode_num_int < episode_num_offset_int:
                    offset_order_flag = False
                if not episode_num_str.isdigit():
                    episode_num_offset_str = cn2an.an2cn(episode_num_offset_int, "low")
                else:
                    count_0 = re.findall(r"^0+", episode_num_str)
                    if count_0:
                        episode_num_offset_str = f"{count_0[0]}{episode_num_offset_int}"
                    else:
                        episode_num_offset_str = str(episode_num_offset_int)
                episode_nums_offset_str.append(episode_num_offset_str)
            episode_nums_dict = dict(zip(episode_nums_str, episode_nums_offset_str))
            if offset_order_flag:
                episode_nums_list = sorted(episode_nums_dict.items(), key=lambda x: x[1])
            else:
                episode_nums_list = sorted(episode_nums_dict.items(), key=lambda x: x[1], reverse=True)
            for episode_num in episode_nums_list:
                episode_offset_re = re.compile(
                    r'(?<=%s.*?)%s(?=.*?%s)' % (front, episode_num[0], back))
                title = re.sub(episode_offset_re, r'%s' % episode_num[1], title)
            return title, "", True
        except Exception as err:
            return title, str(err), False
