"""
从 FLORAFAUNA1.gdb 的 VBA_FAUNA25 图层提取动物观测数据，
按最近邮编归类，插入到 species_cache 表中。
不修改现有数据，不新增列。
"""

import csv
import psycopg2
from scipy.spatial import KDTree
import numpy as np
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "echoes_of_earth",
    "user": "postgres",
    "password": "P@ssw0rd",
}

CSV_PATH = "/tmp/fauna_filtered.csv"

# FFG 状态码 -> state_conservation 映射
FFG_DESC_MAP = {
    "cr": "Critically Endangered",
    "en": "Endangered",
    "en-x": "Endangered",
    "vu": "Vulnerable",
    "cd": "Not listed",
    "ex": "Not listed",
    "": "Not listed",
}


def get_state_conservation(ffg_code: str) -> str:
    return FFG_DESC_MAP.get((ffg_code or "").lower().strip(), "Not listed")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 1. 读取所有邮编及质心
    cur.execute(
        "SELECT postcode, centroid_lat, centroid_lng FROM suburb_demographics WHERE state='VIC'"
    )
    rows = cur.fetchall()
    postcodes = [r[0].strip() for r in rows]
    coords = np.array([[r[1], r[2]] for r in rows], dtype=float)
    tree = KDTree(coords)
    print(f"已加载 {len(postcodes)} 个邮编")

    # 2. 读取已有记录的去重 key，避免重复插入
    cur.execute(
        "SELECT postcode, scientific_name, vernacular_name, observation_month FROM species_cache"
    )
    existing = set()
    for r in cur.fetchall():
        existing.add((r[0].strip(), r[1], r[2], r[3]))
    print(f"现有记录数: {len(existing)}")

    # 3. 最大匹配距离（度），约 30km
    MAX_DIST_DEG = 0.3

    # 4. 逐行处理 CSV，收集新记录（先在内存去重）
    new_records = {}  # key -> (postcode, vernacular, scientific, state_cons, lat, lng, month, hour)
    
    skipped_distance = 0
    skipped_existing = 0
    skipped_nocoord = 0
    total = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if total % 50000 == 0:
                print(f"  已处理 {total} 条，新记录 {len(new_records)} 条...")

            lat_s = row.get("LAT_DD94", "").strip()
            lng_s = row.get("LONG_DD94", "").strip()
            if not lat_s or not lng_s:
                skipped_nocoord += 1
                continue

            try:
                lat = float(lat_s)
                lng = float(lng_s)
            except ValueError:
                skipped_nocoord += 1
                continue

            sci_name = (row.get("SCI_NAME") or "").strip()
            comm_name = (row.get("COMM_NAME") or "").strip()
            if not sci_name or not comm_name:
                skipped_nocoord += 1
                continue

            # 找最近邮编
            dist, idx = tree.query([lat, lng])
            if dist > MAX_DIST_DEG:
                skipped_distance += 1
                continue

            postcode = postcodes[idx]
            ffg_code = (row.get("FFG") or "").strip()
            state_cons = get_state_conservation(ffg_code)

            obs_month_s = row.get("START_MTH", "").strip()
            try:
                obs_month = int(obs_month_s) if obs_month_s else None
            except ValueError:
                obs_month = None

            obs_hour = 0  # 数据集中所有时间均为 00:00:00

            # 检查是否已存在
            existing_key = (postcode, sci_name, comm_name, obs_month)
            if existing_key in existing:
                skipped_existing += 1
                continue

            # 内存去重 key
            dedup_key = (postcode, sci_name, comm_name, state_cons, obs_month)
            if dedup_key not in new_records:
                new_records[dedup_key] = (
                    postcode, comm_name, sci_name, state_cons,
                    lat, lng, obs_month, obs_hour
                )

    print(f"\n处理完成：")
    print(f"  总计处理: {total}")
    print(f"  跳过（无坐标/名称）: {skipped_nocoord}")
    print(f"  跳过（距离超限）: {skipped_distance}")
    print(f"  跳过（已存在）: {skipped_existing}")
    print(f"  待插入新记录: {len(new_records)}")

    # 5. 批量插入
    insert_sql = """
        INSERT INTO species_cache
          (postcode, vernacular_name, scientific_name, state_conservation,
           lat, lng, observation_month, observation_hour, cached_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    now = datetime.utcnow()
    batch = []
    inserted = 0

    for rec in new_records.values():
        postcode, vernacular, scientific, state_cons, lat, lng, obs_month, obs_hour = rec
        batch.append((postcode, vernacular, scientific, state_cons,
                      lat, lng, obs_month, obs_hour, now))
        if len(batch) >= 1000:
            cur.executemany(insert_sql, batch)
            conn.commit()
            inserted += len(batch)
            batch = []
            print(f"  已插入 {inserted} 条...")

    if batch:
        cur.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)

    print(f"\n插入完成，共插入 {inserted} 条新记录。")

    cur.execute("SELECT COUNT(*) FROM species_cache")
    total_now = cur.fetchone()[0]
    print(f"species_cache 当前总记录数: {total_now}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
