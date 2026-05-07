from enum import Enum


class MediaType(Enum):
    """
    媒体类型
    """
    UNKNOWN = 0
    MOVIE = 1
    TV = 2


class SystemConfigKey(Enum):
    """
    系统配置Key
    """
    CustomIdentifiers = "CustomIdentifiers"
    CustomReleaseGroups = "CustomReleaseGroups"
    Customization = "Customization"
