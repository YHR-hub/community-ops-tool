"""深渊数据抓取 —— 从 paimon.moe 拉取角色使用率"""
import requests
import db
import sys
import traceback

URL = "https://paimon.moe/api/abyss"
TIMEOUT = 15


def fetch_and_store():
    try:
        resp = requests.get(URL, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        print("[fetch_data] 网络超时：paimon.moe 无响应")
        return 0
    except requests.exceptions.ConnectionError:
        print("[fetch_data] 网络连接失败，请检查网络")
        return 0
    except requests.exceptions.HTTPError as e:
        print(f"[fetch_data] HTTP 错误：{e}")
        return 0
    except Exception as e:
        print(f"[fetch_data] JSON 解析或未知错误：{e}")
        return 0

    # paimon.moe 返回格式：{ "data": [ { "version": "4.5", "characters": [...] } ] }
    rows = 0
    try:
        entries = data.get("data", [])
        for entry in entries:
            version = entry.get("version", "")
            if not version:
                continue
            chars = entry.get("characters", [])
            batch = []
            for ch in chars:
                name = ch.get("name", "")
                rate = ch.get("usage_rate", 0)
                floor = ch.get("floor", 12)
                if name:
                    batch.append({
                        "version": version,
                        "character_name": name,
                        "usage_rate": rate,
                        "abyss_floor": floor,
                    })
            if batch:
                db.upsert_char_usage(batch)
                rows += len(batch)
                print(f"[fetch_data] {version}: {len(batch)} 条角色数据已入库")

        print(f"[fetch_data] 完成：共 {rows} 条")
        return rows

    except Exception as e:
        print(f"[fetch_data] 数据处理异常：{e}")
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    db.init_db()
    count = fetch_and_store()
    print(f"成功入库 {count} 条")
    sys.exit(0 if count > 0 else 1)
