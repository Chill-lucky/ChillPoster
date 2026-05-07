# utils.py
import re
import unicodedata

def clean_character_name_static(character_name):
    """清洗角色名"""
    if not character_name:
        return ""
    name = str(character_name).strip()
    name = re.sub(r'\(.*?\)|\[.*?\]|（.*?）|【.*?】', '', name).strip()
    name = re.sub(r'^(as\s+)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'^((?:饰演|饰|扮演|扮|配音|配|as\b)\s*)+', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'(\s*(?:饰演|饰|配音|配))+$', '', name).strip()
    return name

def contains_chinese(text):
    """检查中文"""
    if not text: return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def normalize_name_for_matching(name):
    """标准化名字"""
    if not name: return ""
    nfkd_form = unicodedata.normalize('NFKD', str(name))
    ascii_name = u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return ''.join(filter(str.isalnum, ascii_name.lower()))