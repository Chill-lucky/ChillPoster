import regex as re

from core.meta.singleton import Singleton


class ReleaseGroupsMatcher(metaclass=Singleton):
    """
    识别制作组、字幕组
    """
    RELEASE_GROUPS: dict = {
        "0ff": ['FF(?:(?:A|WE)B|CD|E(?:DU|B)|TV)'],
        "audiences": ['Audies', 'AD(?:Audio|E(?:book|)|Music|Web)'],
        "beitai": ['BeiTai'],
        "btschool": ['Bts(?:CHOOL|HD|PAD|TV)', 'Zone'],
        "chdbits": ['CHD(?:Bits|Pad|(?:|HK)TV|Web|)', 'StBOX', 'OneHD', 'Lee', 'xiaopie'],
        "eastgame": ['(?:(?:iNT|(?:HALFC|Mini(?:S|H|FH)D))-|)TLF'],
        "gainbound": ['(?:DG|GBWE)B'],
        "hares": ['Hares(?:(?:M|T)V|Web|)'],
        "hdarea": ['HDA(?:Pad|rea|TV)', 'EPiC'],
        "hdchina": ['HDC(?:hina|TV|)', 'k9611', 'tudou', 'iHD'],
        "hddolby": ['D(?:ream|BTV)', '(?:HD|QHstudI)o'],
        "hdfans": ['beAst(?:TV|)'],
        "hdhome": ['HDH(?:ome|Pad|TV|Web|)'],
        "hdpt": ['HDPT(?:Web|)'],
        "hdsky": ['HDS(?:ky|TV|Pad|Web|)', 'AQLJ'],
        "hdzone": ['HDZ(?:one|)'],
        "hhanclub": ['HHWEB'],
        "htpt": ['HTPT'],
        "keepfrds": ['FRDS', 'Yumi', 'cXcY'],
        "lemonhd": ['L(?:eague(?:(?:C|H)D|(?:M|T)V|NF|Web)|HD)', 'i18n', 'CiNT'],
        "mteam": ['MTeam(?:TV|)', 'MPAD', 'MWeb'],
        "ourbits": ['Our(?:Bits|TV)', 'FLTTH', 'Ao', 'PbK', 'MGs', 'iLove(?:HD|TV)'],
        "panda": ['Panda', 'AilMWeb'],
        "piggo": ['PiGo(?:NF|(?:H|We)B)'],
        "pterclub": ['PTer(?:DIY|Game|(?:M|T)V|Web|)'],
        "pthome": ['PTH(?:Audio|eBook|music|ome|tv|Web|)'],
        "ptsbao": ['PTsbao', 'OPS', 'F(?:Fans(?:AIeNcE|BD|D(?:VD|IY)|TV|Web)|HDMv)', 'SGXT'],
        "putao": ['PuTao'],
        "springsunday": ['CMCT(?:V|)'],
        "sharkpt": ['Shark(?:Web|DIY|TV|MV|)'],
        "tjupt": ['TJUPT'],
        "tothenglory": ['TTG', 'WiKi', 'NGB', 'DoA', '(?:ARi|ExRE)N'],
        "others": ['B(?:MDru|eyondHD|TN)', 'C(?:fandora|trlhd|MRG)', 'DON', 'EVO', 'FLUX', 'HONE(?:yG|)',
                   'N(?:oGroup|T(?:b|G))', 'PandaMoon', 'SMURF', 'T(?:EPES|aengoo|rollHD )'],
        "anime": ['ANi', 'HYSUB', 'KTXP', 'LoliHouse', 'MCE', 'Nekomoe kissaten', 'SweetSub', 'MingY',
                  '(?:Lilith|NC)-Raws', '织梦字幕组', '枫叶字幕组', '猎户手抄部', '喵萌奶茶屋', '漫猫字幕社',
                  '霜庭云花Sub', '北宇治字幕组', '氢气烤肉架', '云歌字幕组', '萌樱字幕组', '极影字幕社',
                  '悠哈璃羽字幕社',
                  '沸羊羊(?:制作|字幕组)', '(?:桜|樱)都字幕组'],
        "forge": ['FROG(?:E|Web|)'],
        "ubits": ['UB(?:its|Web|TV)'],
    }

    def __init__(self):
        release_groups = []
        for site_groups in self.RELEASE_GROUPS.values():
            for release_group in site_groups:
                release_groups.append(release_group)
        self.__release_groups = '|'.join(release_groups)

    def match(self, title: str = None, groups: str = None):
        if not title:
            return ""
        if not groups:
            groups = self.__release_groups
        title = f"{title} "
        groups_re = re.compile(r"(?<=[-@\[￡【&])(?:(?:%s))(?=$|[@.\s\]\[】&])" % groups, re.I)
        unique_groups = []
        for item in re.findall(groups_re, title):
            item_str = item[0] if isinstance(item, tuple) else item
            if item_str not in unique_groups:
                unique_groups.append(item_str)
        return "@".join(unique_groups)
