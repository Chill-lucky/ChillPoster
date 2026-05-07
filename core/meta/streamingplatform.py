from typing import Optional, List, Tuple

from core.meta.singleton import Singleton


class StreamingPlatforms(metaclass=Singleton):
    """
    流媒体平台简称与全称。
    """
    STREAMING_PLATFORMS: List[Tuple[str, str]] = [
        ("AMZN", "Amazon"),
        ("NF", "Netflix"),
        ("ATVP", "Apple TV+"),
        ("iT", "iTunes"),
        ("DSNP", "Disney+"),
        ("HS", "Hotstar"),
        ("PMTP", "Paramount+"),
        ("HMAX", "Max"),
        ("", "Max"),
        ("HULU", "Hulu Networks"),
        ("MA", "Movies Anywhere"),
        ("BCORE", "Bravia Core"),
        ("MS", "Microsoft Store"),
        ("SHO", "Showtime"),
        ("STAN", "Stan"),
        ("PCOK", "Peacock"),
        ("SKST", "SkyShowtime"),
        ("NOW", "Now"),
        ("FXTL", "Foxtel Now"),
        ("BNGE", "Binge"),
        ("CRKL", "Crackle"),
        ("RKTN", "Rakuten TV"),
        ("ALL4", "Channel 4"),
        ("MUBI", "Mubi"),
        ("PLAY", "Google Play"),
        ("YT", "YouTube"),
        ("Hami", "Hami Video"),
        ("HamiVideo", "Hami Video"),
        ("MW", "meWATCH"),
        ("CATCHPLAY", "CATCHPLAY+"),
        ("CPP", "CATCHPLAY+"),
        ("LINETV", "LINE TV"),
        ("VIU", "Viu"),
        ("ABMA", "Abema"),
        ("ADN", ""),
        ("AT-X", ""),
        ("BG", "B-Global"),
        ("CR", "Crunchyroll"),
        ("FOD", ""),
        ("FUNi", "Funimation"),
        ("HIDI", "HIDIVE"),
        ("UNXT", "U-NEXT"),
        ("iP", "BBC iPlayer"),
        ("ROKU", "Roku"),
        ("VIKI", "Rakuten Viki"),
        ("PLEX", "Plex"),
        ("CRAV", "Crave"),
        ("VIAP", "Viaplay"),
        ("TUBI", "TubiTV"),
        ("PBS", ""),
        ("PBSK", "PBS KIDS"),
        ("MP", "Movistar Plus+"),
        ("STZ", "STARZ"),
        ("FUBO", "fuboTV"),
        ("CW", "The CW"),
        ("FOX", ""),
        ("ITVX", "ITV"),
        ("HBO", "HBO"),
        ("HBOGO", "HBO GO"),
        ("EPIX", "EPIX MGM+"),
        ("SYFY", "SyFy"),
        ("DISC", "Discovery Channel"),
        ("NATG", "National Geographic"),
        ("NICK", "Nickelodeon"),
        ("BBC", ""),
        ("DW", "DailyWire+"),
        ("DLWP", "DailyWire+"),
        ("PlutoTV", "Pluto TV"),
        ("AbemaTV", "Abema"),
        ("TVER", "TVer"),
        ("VIDIO", "Vidio"),
        ("WAVVE", "Wavve"),
        ("WAKA", "Wakanim"),
        ("WAKANIM", "Wakanim"),
        ("AO", "AnimeOnegai"),
        ("OV", "OceanVeil"),
    ]

    def __init__(self):
        self._lookup_cache = {}
        self._build_cache()

    def _build_cache(self) -> None:
        self._lookup_cache.clear()
        for short_name, full_name in self.STREAMING_PLATFORMS:
            canonical_name = full_name or short_name
            if not canonical_name:
                continue
            aliases = {short_name, full_name}
            for alias in aliases:
                if alias:
                    self._lookup_cache[alias.upper()] = canonical_name

    def get_streaming_platform_name(self, platform_code: str) -> Optional[str]:
        if platform_code is None:
            return None
        return self._lookup_cache.get(platform_code.upper())

    def is_streaming_platform(self, name: str) -> bool:
        if name is None:
            return False
        return name.upper() in self._lookup_cache
