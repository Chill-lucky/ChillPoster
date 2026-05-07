"""
媒体整理模板相关函数。

从 app/routers/media_organize.py 中提取的模板构建、渲染与文件名处理函数。
"""

import os
import re
import subprocess
from typing import Optional

from core.logger import logger
from app.services.media_organize_tmdb import _normalize_title_for_match


# 拼音首字母映射表（常用字）
_PINYIN_MAP = {
    '阿': 'A', '爱': 'A', '安': 'A', '暗': 'A',
    '白': 'B', '百': 'B', '半': 'B', '包': 'B', '北': 'B', '本': 'B', '比': 'B', '变': 'B', '标': 'B', '表': 'B', '别': 'B', '冰': 'B', '兵': 'B', '并': 'B', '不': 'B', '部': 'B',
    '才': 'C', '菜': 'C', '参': 'C', '草': 'C', '层': 'C', '查': 'C', '产': 'C', '长': 'C', '常': 'C', '场': 'C', '车': 'C', '成': 'C', '城': 'C', '程': 'C', '吃': 'C', '出': 'C', '初': 'C', '除': 'C', '楚': 'C', '处': 'C', '传': 'C', '创': 'C', '春': 'C', '此': 'C', '从': 'C', '村': 'C', '存': 'C', '错': 'C',
    '大': 'D', '代': 'D', '待': 'D', '单': 'D', '当': 'D', '到': 'D', '的': 'D', '地': 'D', '第': 'D', '点': 'D', '电': 'D', '店': 'D', '定': 'D', '东': 'D', '冬': 'D', '动': 'D', '都': 'D', '读': 'D', '独': 'D', '短': 'D', '段': 'D', '对': 'D', '多': 'D',
    '儿': 'E', '而': 'E', '二': 'E',
    '发': 'F', '法': 'F', '反': 'F', '方': 'F', '房': 'F', '放': 'F', '飞': 'F', '非': 'F', '分': 'F', '风': 'F', '封': 'F', '否': 'F', '服': 'F', '福': 'F', '府': 'F', '父': 'F', '妇': 'F', '副': 'F',
    '该': 'G', '改': 'G', '概': 'G', '干': 'G', '感': 'G', '刚': 'G', '高': 'G', '告': 'G', '哥': 'G', '歌': 'G', '个': 'G', '给': 'G', '根': 'G', '更': 'G', '工': 'G', '公': 'G', '功': 'G', '宫': 'G', '共': 'G', '姑': 'G', '古': 'G', '故': 'G', '顾': 'G', '关': 'G', '观': 'G', '官': 'G', '馆': 'G', '光': 'G', '广': 'G', '规': 'G', '鬼': 'G', '国': 'G', '果': 'G', '过': 'G',
    '海': 'H', '汉': 'H', '好': 'H', '号': 'H', '合': 'H', '和': 'H', '河': 'H', '黑': 'H', '很': 'H', '红': 'H', '后': 'H', '候': 'H', '乎': 'H', '花': 'H', '华': 'H', '画': 'H', '话': 'H', '还': 'H', '环': 'H', '换': 'H', '黄': 'H', '回': 'H', '会': 'H', '婚': 'H', '火': 'H', '或': 'H',
    '机': 'J', '鸡': 'J', '积': 'J', '基': 'J', '及': 'J', '极': 'J', '急': 'J', '集': 'J', '计': 'J', '记': 'J', '技': 'J', '际': 'J', '季': 'J', '济': 'J', '继': 'J', '加': 'J', '家': 'J', '假': 'J', '间': 'J', '监': 'J', '见': 'J', '建': 'J', '健': 'J', '将': 'J', '江': 'J', '讲': 'J', '奖': 'J', '交': 'J', '教': 'J', '接': 'J', '街': 'J', '节': 'J', '结': 'J', '姐': 'J', '解': 'J', '今': 'J', '金': 'J', '仅': 'J', '进': 'J', '近': 'J', '京': 'J', '经': 'J', '精': 'J', '警': 'J', '静': 'J', '究': 'J', '九': 'J', '酒': 'J', '就': 'J', '局': 'J', '举': 'J', '句': 'J', '剧': 'J', '决': 'J', '绝': 'J',
    '开': 'K', '看': 'K', '考': 'K', '科': 'K', '可': 'K', '客': 'K', '课': 'K', '空': 'K', '口': 'K', '苦': 'K', '快': 'K', '困': 'K',
    '拉': 'L', '来': 'L', '老': 'L', '乐': 'L', '了': 'L', '类': 'L', '冷': 'L', '里': 'L', '理': 'L', '力': 'L', '历': 'L', '利': 'L', '连': 'L', '脸': 'L', '练': 'L', '良': 'L', '两': 'L', '亮': 'L', '林': 'L', '零': 'L', '领': 'L', '另': 'L', '流': 'L', '六': 'L', '龙': 'L', '楼': 'L', '路': 'L', '旅': 'L', '绿': 'L', '论': 'L', '落': 'L',
    '妈': 'M', '马': 'M', '吗': 'M', '买': 'M', '卖': 'M', '满': 'M', '慢': 'M', '忙': 'M', '毛': 'M', '没': 'M', '美': 'M', '妹': 'M', '门': 'M', '梦': 'M', '米': 'M', '面': 'M', '民': 'M', '明': 'M', '名': 'M', '命': 'M', '母': 'M', '目': 'M',
    '那': 'N', '男': 'N', '南': 'N', '难': 'N', '脑': 'N', '内': 'N', '能': 'N', '你': 'N', '年': 'N', '娘': 'N', '鸟': 'N', '牛': 'N', '农': 'N', '女': 'N', '暖': 'N',
    '怕': 'P', '跑': 'P', '朋': 'P', '片': 'P', '票': 'P', '品': 'P', '平': 'P', '评': 'P', '破': 'P', '普': 'P',
    '七': 'Q', '期': 'Q', '其': 'Q', '奇': 'Q', '骑': 'Q', '起': 'Q', '气': 'Q', '前': 'Q', '钱': 'Q', '强': 'Q', '桥': 'Q', '切': 'Q', '亲': 'Q', '青': 'Q', '清': 'Q', '情': 'Q', '请': 'Q', '秋': 'Q', '求': 'Q', '球': 'Q', '区': 'Q', '取': 'Q', '去': 'Q', '全': 'Q', '确': 'Q', '群': 'Q',
    '然': 'R', '让': 'R', '热': 'R', '人': 'R', '日': 'R', '如': 'R', '入': 'R',
    '三': 'S', '散': 'S', '色': 'S', '山': 'S', '伤': 'S', '上': 'S', '少': 'S', '设': 'S', '社': 'S', '身': 'S', '深': 'S', '神': 'S', '生': 'S', '声': 'S', '省': 'S', '师': 'S', '十': 'S', '石': 'S', '时': 'S', '实': 'S', '食': 'S', '史': 'S', '始': 'S', '世': 'S', '市': 'S', '事': 'S', '是': 'S', '室': 'S', '收': 'S', '手': 'S', '首': 'S', '受': 'S', '书': 'S', '术': 'S', '树': 'S', '数': 'S', '双': 'S', '谁': 'S', '水': 'S', '顺': 'S', '说': 'S', '思': 'S', '死': 'S', '四': 'S', '送': 'S', '搜': 'S', '诉': 'S', '算': 'S', '虽': 'S', '岁': 'S', '所': 'S',
    '他': 'T', '她': 'T', '太': 'T', '谈': 'T', '汤': 'T', '堂': 'T', '特': 'T', '疼': 'T', '提': 'T', '体': 'T', '天': 'T', '田': 'T', '条': 'T', '跳': 'T', '铁': 'T', '听': 'T', '庭': 'T', '通': 'T', '同': 'T', '头': 'T', '图': 'T', '团': 'T', '推': 'T', '退': 'T',
    '外': 'W', '完': 'W', '玩': 'W', '晚': 'W', '万': 'W', '王': 'W', '网': 'W', '忘': 'W', '望': 'W', '危': 'W', '为': 'W', '围': 'W', '唯': 'W', '维': 'W', '伟': 'W', '卫': 'W', '文': 'W', '闻': 'W', '问': 'W', '我': 'W', '五': 'W', '武': 'W', '舞': 'W', '物': 'W', '务': 'W',
    '西': 'X', '希': 'X', '息': 'X', '习': 'X', '喜': 'X', '系': 'X', '细': 'X', '下': 'X', '夏': 'X', '先': 'X', '鲜': 'X', '现': 'X', '线': 'X', '限': 'X', '相': 'X', '香': 'X', '想': 'X', '向': 'X', '象': 'X', '小': 'X', '校': 'X', '笑': 'X', '些': 'X', '心': 'X', '新': 'X', '信': 'X', '星': 'X', '行': 'X', '形': 'X', '性': 'X', '兄': 'X', '休': 'X', '修': 'X', '秀': 'X', '需': 'X', '许': 'X', '选': 'X', '学': 'X', '雪': 'X', '血': 'X', '寻': 'X',
    '呀': 'Y', '言': 'Y', '眼': 'Y', '演': 'Y', '央': 'Y', '羊': 'Y', '阳': 'Y', '样': 'Y', '要': 'Y', '药': 'Y', '也': 'Y', '业': 'Y', '夜': 'Y', '一': 'Y', '衣': 'Y', '医': 'Y', '已': 'Y', '以': 'Y', '亿': 'Y', '因': 'Y', '音': 'Y', '银': 'Y', '应': 'Y', '英': 'Y', '影': 'Y', '永': 'Y', '用': 'Y', '有': 'Y', '友': 'Y', '又': 'Y', '右': 'Y', '鱼': 'Y', '于': 'Y', '雨': 'Y', '语': 'Y', '育': 'Y', '元': 'Y', '园': 'Y', '原': 'Y', '远': 'Y', '院': 'Y', '愿': 'Y', '月': 'Y', '越': 'Y',
    '在': 'Z', '早': 'Z', '怎': 'Z', '展': 'Z', '站': 'Z', '长': 'Z', '找': 'Z', '照': 'Z', '这': 'Z', '真': 'Z', '正': 'Z', '知': 'Z', '之': 'Z', '直': 'Z', '只': 'Z', '纸': 'Z', '指': 'Z', '至': 'Z', '中': 'Z', '种': 'Z', '重': 'Z', '州': 'Z', '周': 'Z', '主': 'Z', '住': 'Z', '注': 'Z', '祝': 'Z', '专': 'Z', '转': 'Z', '装': 'Z', '准': 'Z', '子': 'Z', '自': 'Z', '字': 'Z', '走': 'Z', '最': 'Z', '昨': 'Z', '作': 'Z', '做': 'Z', '坐': 'Z',
}


def _get_first_letter(title: str) -> str:
    """获取标题首字母（拼音首字母）"""
    if not title:
        return ""
    first_char = title[0]
    if first_char.isascii():
        return first_char.upper()
    return _PINYIN_MAP.get(first_char, '#')


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", str(text or "")))


def _contains_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", str(text or "")))


def _normalize_title_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe_title_candidates(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        cleaned = _normalize_title_text(value)
        if not cleaned:
            continue
        normalized = _normalize_title_for_match(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(cleaned)
    return deduped


def _collect_translation_candidates(source: dict, field_name: str, languages: set[str], regions: set[str]) -> list[str]:
    candidates = []
    translations = source.get("translations", {})
    if not isinstance(translations, dict):
        return candidates
    for item in translations.get("translations", []) or []:
        if not isinstance(item, dict):
            continue
        iso_lang = str(item.get("iso_639_1") or "").lower()
        iso_region = str(item.get("iso_3166_1") or "").upper()
        if languages or regions:
            if iso_lang not in languages and iso_region not in regions:
                continue
        data = item.get("data") or {}
        candidate = _normalize_title_text(data.get(field_name, ""))
        if candidate:
            candidates.append(candidate)
    return candidates


def _collect_translation_candidates_by_regions(source: dict, field_name: str, languages: set[str], region_priority: list[str]) -> list[str]:
    candidates = []
    translations = source.get("translations", {})
    if not isinstance(translations, dict):
        return candidates
    for region in region_priority:
        for item in translations.get("translations", []) or []:
            if not isinstance(item, dict):
                continue
            iso_lang = str(item.get("iso_639_1") or "").lower()
            iso_region = str(item.get("iso_3166_1") or "").upper()
            if iso_region != region:
                continue
            if languages and iso_lang not in languages:
                continue
            data = item.get("data") or {}
            candidate = _normalize_title_text(data.get(field_name, ""))
            if candidate:
                candidates.append(candidate)
    return candidates


def _collect_alternative_title_candidates(source: dict, languages: set[str], regions: set[str]) -> list[str]:
    candidates = []
    alt_titles = source.get("alternative_titles", {})
    if not isinstance(alt_titles, dict):
        return candidates
    for key in ("results", "titles"):
        for item in alt_titles.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            iso_lang = str(item.get("iso_639_1") or "").lower()
            iso_region = str(item.get("iso_3166_1") or "").upper()
            if languages or regions:
                if iso_lang not in languages and iso_region not in regions:
                    continue
            candidate = _normalize_title_text(item.get("title") or item.get("name") or "")
            if candidate:
                candidates.append(candidate)
    return candidates


def _collect_alternative_title_candidates_by_regions(source: dict, languages: set[str], region_priority: list[str]) -> list[str]:
    candidates = []
    alt_titles = source.get("alternative_titles", {})
    if not isinstance(alt_titles, dict):
        return candidates
    for region in region_priority:
        for key in ("results", "titles"):
            for item in alt_titles.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                iso_lang = str(item.get("iso_639_1") or "").lower()
                iso_region = str(item.get("iso_3166_1") or "").upper()
                if iso_region != region:
                    continue
                if languages and iso_lang and iso_lang not in languages:
                    continue
                candidate = _normalize_title_text(item.get("title") or item.get("name") or "")
                if candidate:
                    candidates.append(candidate)
    return candidates


def _pick_preferred_cn_title(source: dict, primary_field: str, original_field: str) -> str:
    zh_languages = {"zh"}
    simplified_regions = ["CN", "SG", "MY"]
    traditional_regions = ["TW", "HK", "MO"]
    primary_title = _normalize_title_text(source.get(primary_field, ""))
    original_title = _normalize_title_text(source.get(original_field, ""))

    candidates = []
    if _contains_chinese(primary_title):
        candidates.append(primary_title)
    if _contains_chinese(original_title):
        candidates.append(original_title)

    alias_candidates = []
    alias_candidates.extend(_collect_translation_candidates_by_regions(source, primary_field, zh_languages, simplified_regions))
    alias_candidates.extend(_collect_alternative_title_candidates_by_regions(source, zh_languages, simplified_regions))
    alias_candidates.extend(_collect_translation_candidates_by_regions(source, primary_field, zh_languages, traditional_regions))
    alias_candidates.extend(_collect_alternative_title_candidates_by_regions(source, zh_languages, traditional_regions))
    candidates.extend(candidate for candidate in alias_candidates if _contains_chinese(candidate))

    deduped = _dedupe_title_candidates(candidates)
    if deduped:
        return deduped[0]
    return _pick_preferred_en_title(source, primary_field, original_field)


def _pick_preferred_en_title(source: dict, primary_field: str, original_field: str) -> str:
    english_regions = ["US", "GB", "CA", "AU", "NZ"]
    candidates = []
    candidates.extend(_collect_translation_candidates_by_regions(source, primary_field, {"en"}, english_regions))
    candidates.extend(_collect_alternative_title_candidates_by_regions(source, {"en"}, english_regions))
    candidates.extend(_collect_translation_candidates(source, primary_field, {"en"}, set()))
    candidates.extend(_collect_alternative_title_candidates(source, {"en"}, set()))
    candidates.append(source.get("english_title", ""))
    candidates.append(source.get("english_name", ""))

    original_title = _normalize_title_text(source.get(original_field, ""))
    primary_title = _normalize_title_text(source.get(primary_field, ""))
    if source.get("original_language") == "en" and _contains_latin(original_title):
        candidates.insert(0, original_title)
    elif _contains_latin(original_title):
        candidates.append(original_title)
    if _contains_latin(primary_title):
        candidates.append(primary_title)

    deduped = _dedupe_title_candidates(candidates)
    return deduped[0] if deduped else ""


def _build_template_variables(tmdb_data: dict, req, ext: str, meta_info: dict = None,
                              _title_cache: dict = None) -> dict:
    """
    构建模板变量字典。

    Args:
        tmdb_data:      TMDb 数据
        req:            请求对象 (含 media_type, tmdb_id, season_number, episode_number)
        ext:            文件扩展名 (含点，如 ".mkv")
        meta_info:      MetaVideo 从文件名解析的资源信息
        _title_cache:   可选的标题缓存 dict，同一批次剧集复用，避免重复计算
    """
    # 聚合数据时，顶层字段在 series_details 里
    source = tmdb_data.get("series_details") if "series_details" in tmdb_data else tmdb_data

    # 尝试从缓存获取标题相关字段（同一批次剧集完全相同）
    cached = None
    if _title_cache is not None:
        cache_key = id(source)
        cached = _title_cache.get(cache_key)

    if cached:
        title = cached["title"]
        en_title = cached["en_title"]
        original_title = cached["original_title"]
        year = cached["year"]
        tmdb_id_str = cached["tmdb_id"]
        first_letter = cached["first_letter"]
    else:
        if req.media_type == 'movie':
            primary_field = "title"
            original_field = "original_title"
            raw_title = _normalize_title_text(source.get(primary_field, ""))
            raw_original_title = _normalize_title_text(source.get(original_field, ""))
            year = (source.get("release_date") or "0000")[:4]
        else:
            primary_field = "name"
            original_field = "original_name"
            raw_title = _normalize_title_text(source.get(primary_field, ""))
            raw_original_title = _normalize_title_text(source.get(original_field, ""))
            year = (source.get("first_air_date") or "0000")[:4]

        title = _pick_preferred_cn_title(source, primary_field, original_field) or raw_title or raw_original_title
        en_title = _pick_preferred_en_title(source, primary_field, original_field)
        original_title = raw_original_title

        # original_title 仅在和主标题语义不同的时候保留
        if original_title and title:
            if _normalize_title_for_match(original_title) == _normalize_title_for_match(title):
                original_title = ""
            else:
                try:
                    import zhconv
                    norm_orig = _normalize_title_for_match(zhconv.convert(original_title, "zh-hans"))
                    norm_title = _normalize_title_for_match(zhconv.convert(title, "zh-hans"))
                    if norm_orig == norm_title:
                        original_title = ""
                except ImportError:
                    pass

        tmdb_id_str = str(source.get("id", req.tmdb_id))
        first_letter = _get_first_letter(title)

        # 缓存标题相关字段
        if _title_cache is not None:
            _title_cache[id(source)] = {
                "title": title, "en_title": en_title,
                "original_title": original_title, "year": year,
                "tmdb_id": tmdb_id_str, "first_letter": first_letter,
            }

    season_num = req.season_number
    episode_num = req.episode_number
    # 剧集有集号但没季号时，默认 S01
    if season_num is None and episode_num is not None:
        season_num = 1
    season_episode = ""
    if season_num is not None and episode_num is not None:
        season_episode = f"S{season_num:02d}E{episode_num:02d}"

    # MetaVideo 解析的资源信息（基础值）
    mi = dict(meta_info) if meta_info else {}

    final_en_title = _normalize_title_text(mi.get("en_title") or en_title)
    if not final_en_title:
        raw_title = _normalize_title_text(source.get("name" if req.media_type != 'movie' else "title", ""))
        raw_original_title = _normalize_title_text(source.get("original_name" if req.media_type != 'movie' else "original_title", ""))
        final_en_title = raw_title or raw_original_title or title

    return {
        "title": title,
        "original_title": original_title,
        "en_title": final_en_title,
        "year": year,
        "tmdb_id": tmdb_id_str,
        "season_episode": season_episode,
        "season_num": f"{season_num:02d}" if season_num is not None else "",
        "episode_num": f"{episode_num:02d}" if episode_num is not None else "",
        "first_letter": first_letter,
        "ext": ext,
        "resource_pix": mi.get("resource_pix", ""),
        "resource_type": mi.get("resource_type", ""),
        "resource_effect": mi.get("resource_effect", ""),
        "video_effect": mi.get("video_effect", ""),
        "color_depth": mi.get("color_depth", ""),
        "video_encode": mi.get("video_encode", ""),
        "audio_encode": mi.get("audio_encode", ""),
        "web_source": mi.get("web_source", ""),
        "resource_team": mi.get("resource_team", ""),
        "source": mi.get("source", ""),
        "release_group": mi.get("release_group", ""),
        "fps": mi.get("fps", ""),
        "part": mi.get("part", ""),
    }


_TEMPLATE_VAR_RE = re.compile(r'\{(\w+)\}')
_SEPARATOR_CLEANUP_RE = re.compile(r'(\.{2,}|-{2,}|_{2,}| {2,})')
_EMPTY_BRACKETS_RE = re.compile(r'(\(\s*\)|\[\s*\]|<\s*>)')


def _render_template(template: str, variables: dict) -> str:
    """
    渲染重命名模板。
    变量值为空时，删除整个 {var} 占位符。
    使用单次正则扫描替代多次 str.replace，提升批量场景性能。
    """
    def _replacer(match):
        key = match.group(1)
        value = variables.get(key)
        if value is not None:
            return str(value)
        return ""

    result = _TEMPLATE_VAR_RE.sub(_replacer, template)

    # 清理多余分隔符和空括号
    result = _SEPARATOR_CLEANUP_RE.sub(lambda m: m.group(0)[0], result)
    result = _EMPTY_BRACKETS_RE.sub('', result)
    result = result.strip('.-_ ')

    return _sanitize_filename(result)


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '', name).strip()
