#!/usr/bin/env python3
"""读取 docs/music/playlist.txt 里的 B 站收藏夹，生成 docs/music/bilibili.json。

浏览器不能直接读 B 站接口（跨域限制），所以在部署网页时由 GitHub 的服务器读取，
把每个收藏夹里的视频（BV 号、标题、时长）写进 JSON，网页再按顺序播放。

收藏夹必须是“公开”的。读取失败只打印警告、不影响网页部署；
这时如果仓库里已有旧的 bilibili.json，会继续使用旧的。
"""

import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "docs" / "music" / "playlist.txt"
OUT = ROOT / "docs" / "music" / "bilibili.json"
API = "https://api.bilibili.com/x/v3/fav/resource/list?media_id={mid}&pn={pn}&ps=20&platform=web"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
MAX_PAGES = 50


def warn(msg):
    print(f"::warning::{msg}", flush=True)


def list_ids(text):
    ids = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = (re.search(r"bilibili\.com/list/ml(\d+)", line)
             or re.search(r"bilibili\.com/medialist/(?:detail|play)/ml(\d+)", line)
             or re.search(r"bilibili\.com/\d+/favlist\?[^ ]*fid=(\d+)", line))
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


# B 站对没有浏览器 cookie（buvid3）的请求常常拒绝（HTTP 412 / code -352），
# 所以先像浏览器一样拿一个访客 cookie，再读收藏夹
JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))
HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with OPENER.open(req, timeout=20) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def visitor_cookie():
    try:
        d = get("https://api.bilibili.com/x/frontend/finger/spi").get("data") or {}
        extra = []
        if d.get("b_3"):
            extra.append(f"buvid3={d['b_3']}")
        if d.get("b_4"):
            extra.append(f"buvid4={d['b_4']}")
        if extra:
            HEADERS["Cookie"] = "; ".join(extra + [f"b_nut={int(time.time())}"])
            print("已获取 B 站访客 cookie")
    except Exception as e:  # 拿不到也继续试
        warn(f"获取 B 站访客 cookie 失败：{e}")


def fetch_ids(mid):
    """备用接口：只给 BV 号，再逐个查标题和时长。"""
    data = get(f"https://api.bilibili.com/x/v3/fav/resource/ids?media_id={mid}&platform=web")
    if data.get("code") != 0:
        raise RuntimeError(f"备用接口返回 code={data.get('code')} {data.get('message', '')}")
    items = []
    for x in (data.get("data") or [])[:300]:
        bvid = x.get("bvid") or x.get("bv_id")
        if not bvid:
            continue
        item = {"bvid": bvid, "title": "", "duration": 0}
        try:
            v = get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", tries=1)
            if v.get("code") == 0:
                item["title"] = v["data"].get("title", "")
                item["duration"] = v["data"].get("duration") or 0
            elif v.get("code") in (-404, 62002, 62004):
                continue  # 视频已失效
        except Exception:
            pass
        items.append(item)
        time.sleep(0.3)
    return items


def fetch_list(mid):
    items, title = [], ""
    for pn in range(1, MAX_PAGES + 1):
        data = get(API.format(mid=mid, pn=pn))
        if data.get("code") != 0:
            raise RuntimeError(f"接口返回 code={data.get('code')} {data.get('message', '')}"
                               "（收藏夹需要设为公开）")
        d = data.get("data") or {}
        title = title or (d.get("info") or {}).get("title", "")
        for m in d.get("medias") or []:
            if not m.get("bvid") or m.get("title") == "已失效视频":
                continue
            items.append({"bvid": m["bvid"], "title": m.get("title", ""), "duration": m.get("duration") or 0})
        if not d.get("has_more"):
            break
        time.sleep(0.5)
    return title, items


def main():
    if not PLAYLIST.exists():
        return 0
    ids = list_ids(PLAYLIST.read_text("utf-8"))
    if not ids:
        print("清单里没有 B 站收藏夹。")
        return 0
    old = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"lists": {}}
    lists = {}
    visitor_cookie()
    for mid in ids:
        try:
            try:
                title, items = fetch_list(mid)
            except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as e:
                warn(f"读取 B 站收藏夹 ml{mid} 失败（{e}），改用备用接口")
                title, items = "", fetch_ids(mid)
            if not items:
                raise RuntimeError("收藏夹里没有可播放的视频")
            lists[mid] = {"title": title, "items": items}
            print(f"B 站收藏夹 ml{mid}「{title}」：{len(items)} 个视频")
        except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as e:
            warn(f"读取 B 站收藏夹 ml{mid} 失败：{e}")
            if mid in old.get("lists", {}):
                lists[mid] = old["lists"][mid]
                warn(f"继续使用上次保存的 ml{mid} 列表")
    OUT.write_text(json.dumps({
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "lists": lists,
    }, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
