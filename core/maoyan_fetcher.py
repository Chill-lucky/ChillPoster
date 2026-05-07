# core/maoyan_fetcher.py
import logging
import requests
import argparse
import json
import sys
import os
import time
from typing import List, Dict, Tuple

# --- 关键：确保可以导入项目中的其他模块 ---
# 将父目录加入 path，以便能导入 core.tmdb
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    # 尝试导入我们刚升级过的 tmdb 模块
    import core.tmdb as tmdb
except ImportError:
    try:
        # 回退尝试：如果是在 core 目录下直接运行
        import tmdb
    except ImportError as e:
        print(f"Error importing tmdb module: {e}")
        sys.exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MaoyanFetcher")

def get_maoyan_rank_titles(types_to_fetch: List[str], platform: str = 'all', num: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """
    获取猫眼榜单标题 (爬虫部分)
    """
    movies_list = []
    tv_list = []
    headers = {
        'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        'Referer': 'https://piaofang.maoyan.com/dashboard'
    }
    maoyan_url = 'https://piaofang.maoyan.com'

    # 1. 电影榜单
    if 'movie' in types_to_fetch:
        try:
            url = f'{maoyan_url}/dashboard-ajax/movie'
            logger.info(f"Fetching Maoyan Movie Rank...")
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json().get('movieList', {}).get('list', [])
            # 提取前 num 个
            for m in data[:num]:
                name = m.get('movieInfo', {}).get('movieName')
                if name:
                    movies_list.append({"title": name})
        except Exception as e:
            logger.error(f"Failed to fetch Maoyan Movie Rank: {e}")

    # 2. 剧集/综艺榜单
    # 映射关系: 猫眼参数 seriesType -> 含义
    # 0: 网络剧 (web-heat)
    # 1: 电视剧 (web-tv / TV Series) 
    # 2: 综艺 (zongyi)
    tv_heat_map = {'web-heat': '0', 'web-tv': '1', 'zongyi': '2'}
    
    # 平台映射
    platform_code_map = {'all': '', 'tencent': '3', 'iqiyi': '2', 'youku': '1', 'mango': '7'}
    p_code = platform_code_map.get(platform, '')

    # 过滤出需要抓取的 TV 类型
    active_tv_types = [t for t in types_to_fetch if t in tv_heat_map]

    for t_type in active_tv_types:
        try:
            logger.info(f"Fetching Maoyan TV Rank ({t_type})...")
            # showDate=2 表示最近更新/昨日热度
            url = f'{maoyan_url}/dashboard/webHeatData?seriesType={tv_heat_map[t_type]}&platformType={p_code}&showDate=2'
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json().get('dataList', {}).get('list', [])
            
            for item in data[:num]:
                name = item.get('seriesInfo', {}).get('name')
                if name:
                    # 综艺也算作 Series 处理
                    tv_list.append({"title": name})
        except Exception as e:
            logger.error(f"Failed to fetch Maoyan TV Rank ({t_type}): {e}")

    return movies_list, tv_list

def match_titles_to_tmdb(titles_list: List[Dict], item_type: str, api_key: str) -> List[Dict]:
    """
    [大佬核心逻辑]
    将裸标题列表转换为带有 TMDb ID 的精准数据。
    这一步至关重要，它把模糊的中文名变成了全球唯一的 ID。
    """
    matched = []
    total = len(titles_list)
    logger.info(f"Starting TMDb matching for {total} {item_type} items...")

    for i, item in enumerate(titles_list):
        title = item.get('title')
        if not title: continue
        
        # 简单进度日志
        if i % 5 == 0:
            logger.info(f"Processing {i+1}/{total}: {title}")

        # 调用 core.tmdb.search_media (我们在上一步 tmdb.py 中新增的高级接口)
        # 这里不传 year，因为猫眼榜单通常不带明确年份，交给 search_media 的模糊匹配
        try:
            # 搜索
            results = tmdb.search_media(title, api_key, item_type, year=None)
            
            if results:
                # 命中！取第一个结果 (通常是最准的，因为猫眼的热度通常对应 TMDb 的高热度)
                best_match = results[0]
                
                # 构造返回对象
                res_obj = {
                    'title': title, # 保持原始标题，方便对应
                    'id': str(best_match['id']), # 兼容旧字段
                    'tmdb_id': str(best_match['id']), # 标准字段
                    'type': item_type,
                    'year': best_match.get('release_date', '')[:4] if item_type == 'Movie' else best_match.get('first_air_date', '')[:4],
                    'overview': best_match.get('overview', ''),
                    'poster_path': best_match.get('poster_path', '')
                }
                
                logger.info(f"  -> Match: {title} => {best_match.get('title', 'Unknown')} (ID: {best_match['id']})")
                matched.append(res_obj)
            else:
                logger.warning(f"  -> No TMDb match found for: {title}")
                # 即使没匹配到 ID，也保留原始标题，主程序可能有兜底策略
                matched.append({
                    'title': title,
                    'type': item_type,
                    'id': None,
                    'tmdb_id': None
                })
                
        except Exception as e:
            logger.error(f"Error matching {title}: {e}")
            
        # 礼貌性延时，防止 API 速率限制
        time.sleep(0.2)
        
    return matched

def main():
    # 独立的参数解析，由 importer.py 的 subprocess 调用
    parser = argparse.ArgumentParser(description="Maoyan Fetcher & TMDb Matcher")
    parser.add_argument('--api-key', required=True, help="TMDb API Key")
    parser.add_argument('--output-file', required=True, help="JSON Output File Path")
    parser.add_argument('--num', type=int, default=20, help="Number of items to fetch")
    parser.add_argument('--types', nargs='+', default=['movie'], help="Types: movie, web-heat, web-tv, zongyi")
    parser.add_argument('--platform', default='all', help="Platform: all, tencent, iqiyi, youku, mango")
    
    args = parser.parse_args()
    
    logger.info(">>> Maoyan Fetcher Started")
    
    # 1. 抓取裸数据
    movies_raw, tv_raw = get_maoyan_rank_titles(args.types, args.platform, args.num)
    logger.info(f"Fetched {len(movies_raw)} movies and {len(tv_raw)} TV shows from Maoyan.")
    
    # 2. 执行 TMDb 精准匹配
    final_results = []
    
    if movies_raw:
        matched_movies = match_titles_to_tmdb(movies_raw, 'Movie', args.api_key)
        final_results.extend(matched_movies)
        
    if tv_raw:
        # 综艺和剧集统称为 Series
        matched_tv = match_titles_to_tmdb(tv_raw, 'Series', args.api_key)
        final_results.extend(matched_tv)
        
    # 3. 输出结果到 JSON 文件 (供 importer.py 读取)
    try:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=4)
        logger.info(f"Results saved to {args.output_file}")
    except Exception as e:
        logger.error(f"Failed to save output: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()