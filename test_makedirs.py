"""测试 fs_makedirs_app 在根目录创建三级文件夹，观察返回值"""
import json
from pprint import pprint
from p115client import P115Client

# 读取 cookie
with open("config/config_302.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

cookie = cfg["drives"][0]["cookie"]
client = P115Client(cookie)

# 测试路径：三级文件夹
test_path = "test_level1/test_level2/test_level3"

print(f"调用 fs_makedirs_app 创建路径: {test_path}")
print(f"parent_id (pid): 0 (根目录)")
print("=" * 60)

resp = client.fs_makedirs_app(test_path, pid=0)

print("\n返回结果:")
pprint(resp)

print("\n" + "=" * 60)
print(f"state: {resp.get('state')}")
print(f"cid:   {resp.get('cid')}")
print(f"其他字段: {[k for k in resp.keys() if k not in ('state', 'cid')]}")
