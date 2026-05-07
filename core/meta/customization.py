import regex as re

from core.meta.singleton import Singleton


class CustomizationMatcher(metaclass=Singleton):
    """
    识别自定义占位符
    """

    def __init__(self):
        self.customization = None
        self.custom_separator = None

    def match(self, title=None):
        if not title:
            return ""
        if not self.customization:
            return ""
        customization_re = re.compile(r"%s" % self.customization)
        unique_customization = {}
        for item in re.findall(customization_re, title):
            if not isinstance(item, tuple):
                item = (item,)
            for i in range(len(item)):
                if item[i] and unique_customization.get(item[i]) is None:
                    unique_customization[item[i]] = i
        unique_customization = list(dict(sorted(unique_customization.items(), key=lambda x: x[1])).keys())
        separator = self.custom_separator or "@"
        return separator.join(unique_customization)
