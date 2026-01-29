import streamlit as st
import pandas as pd
import re
import math

# --- 1. 定数・ロジック定義 ---
COURSE_MAP = {
    '芝': {'中山1200':-2, '中山2500':-3, '中京1200':-2, '新潟1000':-5, '小倉1200':-3},
    'ダ': {'東京1300':1, '東京1600':-5, '東京2100':-2, '中山1200':-2, '中山1800':2, '中山2400':-3, '中山2500':-3, '中京1400':-3, '中京1900':-2, '京都1400':-2, '京都1900':-2, '阪神2000':-2, '新潟1200':-2, '新潟2500':-3, '小倉1000':-3, '小倉1700':1, '小倉2400':-3, '福島1700':1, '福島2400':-2, '札幌1000':1, '札幌2400':-2, '函館1000':1, '函館2400':-2}
}

def get_cat(surface, dist):
    try:
        d = int(dist)
        if surface == '芝':
            if d <= 1100: return 1
            if d <= 1400: return 2
            if d == 1600: return 3
            if d <= 2500: return 4
            return 5
        else:
            if d <= 1000: return 1
            if d <= 1200: return 2
            if d <= 1400: return 3
            if d <= 1600: return 4
            if d <= 1800: return 5
            if d <= 2100: return 6
            return 7
    except: return 0

def check_mismatch(old_s, old_d, new_s, new_d):
    o, n = get_cat(old_s, old_d), get_cat(new_s, new_d)
    if new_s == '芝':
        if o in [1,2] and n in [3,4,5]: return True
        if o == 3 and n in [4,5]: return True
        if o == 5 and n != 5: return True
    else:
        if o == 1 and n != 1: return True
        if o in [2,3] and n in [4,5,6,7]: return True
        if o in [6,7] and n not in [6,7]: return True
    return False

def get_rank(s):
    if s >= 70: return 'S'
    if s >= 65: return 'A+'
    if s >= 60: return 'A'
    if s >= 55: return 'B'
    if s >= 50: return 'C'
    return 'D'

st.set_page_config(page_title="KEI System", layout="wide")
st.title("🐎 KEI Evaluation Engine")

input_text = st.text_area("ここにnetkeibaのデータを貼り付けてください", height=300)

if st.button("KEI指数を算出"):
    if not input_text:
        st.warning("データを入力してください")
    else:
        try:
            # A. レース条件の特定
            b_raw_m = re.search(r'タイム指数\s*\n\s*(\d+)', input_text)
            if not b_raw_m: b_raw_m = re.search(r'タイム指数[:：]\s*(\d+)', input_text)
            b_raw = int(b_raw_m.group(1)) if b_raw_m else 87
            
            venue = re.search(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', input_text).group(1)
            course_m = re.search(r'(芝|ダ)(\d+)m', input_text)
            cur_s, cur_d = course_m.groups()
            
            b_final = b_raw + (0 if "未勝利" in input_text else 5) + COURSE_MAP.get(cur_s, {}).get(f"{venue}{cur_d}", 0)

            # B. 馬ごとのデータ抽出
            parts = re.split(r'(\n\s*\d{1,2}\s*\n\s*--|\d{1,2}\s+--)', input_text)
            horses = []
            for i in range(1, len(parts), 2):
                num = re.search(r'\d+', parts[i]).group()
                data = parts[i+1]
                
                # 馬名抽出
                lines = [l.strip() for l in data.split('\n') if l.strip()]
                name = "Unknown"
                for l in lines:
                    if any(m in l for m in ['◎','◯','▲','△','☆','消','✓']): continue
                    if '--' in l: continue
                    name = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館|芝|ダ)', l)[0].strip()
                    break
                
                # 指数データ (地名+芝ダ+距離 ... ペース?+指数+馬場指数)
                past_runs = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?\s*([SMH]?)\s*(\d+)\s*\(([-0-9]+)\)', data)
                m_1y = int(re.search(r'最高\s*(\d+)', data).group(1)) if '最高' in data else 0
                a_5 = int(re.search(r'5走平均\s*(\d+)', data).group(1)) if '5走平均' in data else 0

                cands = []
                for j, (
