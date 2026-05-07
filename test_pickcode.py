import asyncio
import sys
import time
from app.services.drive115_service import drive115_service

# 从日志中提取的超时 pickcode
test_pickcodes = [
    ("ektkwvztndpmozfar", "S01E13.2013.1080p.Netflix.WEB-DL.H264.8bit.25fps.AAC2.0-FLTTH@OurTV.mkv"),
    ("dhmh213vrrhd4xl89", "S01E08.2017.1080p.H264.8bit.25fps.AAC2.0.mkv"),
    ("bdyfa9p7jqrc88lk0", "大秦帝国之纵横.2013.S01E14.第14集.mp4"),
    ("bdyfainidrip58lk0", "大秦帝国之崛起.2017.S01E09.第9集.mp4"),
    ("ektkwvhw7kxhdzfar", "S01E14.2013.1080p.Netflix.WEB-DL.H264.8bit.25fps.AAC2.0-FLTTH@OurTV.mkv"),
]

async def test_single_pickcode(pickcode: str, filename: str):
    print(f"\n{'='*60}")
    print(f"测试: {filename}")
    print(f"Pickcode: {pickcode}")
    print(f"{'='*60}")

    start = time.time()
    try:
        url = await drive115_service.get_direct_url_by_pickcode(
            pickcode=pickcode,
            user_agent="",
            emby_index=0,
            filename=filename
        )
        elapsed = time.time() - start

        if url:
            print(f"✓ 成功获取直链 (耗时: {elapsed:.2f}s)")
            print(f"URL: {url[:100]}..." if len(url) > 100 else f"URL: {url}")
        else:
            print(f"✗ 获取失败 (耗时: {elapsed:.2f}s)")

    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ 异常 (耗时: {elapsed:.2f}s): {e}")

    return elapsed

async def main():
    print("开始测试 115 直链接口...")
    print(f"测试数量: {len(test_pickcodes)}")

    total_time = 0
    for pickcode, filename in test_pickcodes:
        elapsed = await test_single_pickcode(pickcode, filename)
        total_time += elapsed
        await asyncio.sleep(0.5)  # 避免请求过快

    print(f"\n{'='*60}")
    print(f"测试完成")
    print(f"总耗时: {total_time:.2f}s")
    print(f"平均耗时: {total_time/len(test_pickcodes):.2f}s")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
