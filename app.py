import streamlit as st
import pandas as pd
import re
import math

# --- 1. 定数マスタ (不変) ---
COURSE_MAP = {
    '芝': {'中山1200':-2, '中山2500':-3, '中京1200':-2, '新潟1000':-5, '小倉1200':-3},
    'ダ': {
        '東京1300':1, '東京1600':-5, '東京2100':-2, '中山1200':-2, '中山1800':2, 
        '中山2400':-3, '中山2500':-3, '中京1400':-3, '中京1900':-2, '京都1400':-2, 
        '京都1900':-2, '阪神2000':-2, '新潟1200':-2, '新潟2500':-3, '小倉1000':-3, 
        '小倉1700':1, '小倉2400':-3, '福島1700':1, '福島2400':-2, '札幌1000':1, 
        '札幌2400':-2, '函館1000':1, '函館2400':-2
    }
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
        return 4 # ダートは一旦中距離扱い
    except: return 0

# --- UI ---
st.title("🐎 KEI指数算出 (高精度・安全運用版)")
input_text = st.text_area("netkeibaのテキストを貼り付けてください", height=300)

if st.button("KEI指数を算出する"):
    try:
        # A. レース情報の抽出
        b_raw_m = re.search(r'タイム指数\s*\n\s*(\d+)', input_text)
        b_raw = int(b_raw_m.group(1)) if b_raw_m else 87
        venue = re.search(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', input_text).group(1)
        course_m = re.search(r'(芝|ダ)(\d+)m', input_text)
        cur_s, cur_d = course_m.groups()
        b_final = b_raw + (0 if "未勝利" in input_text else 5) + COURSE_MAP.get(cur_s, {}).get(f"{venue}{cur_d}", 0)

        # B. 馬ごとのブロック分割 (改善された分割ロジック)
        blocks = re.split(r'\n\s*(\d{1,2})\n\s*--\n', input_text)
        processed_horses = []
        
        # re.splitの結果、[ヘッダ, 馬番1, データ1, 馬番2, データ2...] となる
        for i in range(1, len(blocks), 2):
            num = blocks[i]
            data = blocks[i+1]
            
            # 馬名の抽出 (余計な記号を排除)
            name_line = [l for l in data.split('\n') if l.strip() and '--' not in l and not any(m in l for m in '◎◯▲△☆消')][0]
            name = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館|芝|ダ)', name_line)[0].strip()

            # 指数データの抽出 (形式: 地名+芝ダ+距離 ... 指数(馬場指数))
            # 例: 福島芝2600 S 95 (-4)
            past_runs = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?(\d+)\s*\(([-0-9]+)\)', data)
            
            max_1y = int(re.search(r'最高\s*(\d+)', data).group(1)) if '最高' in data else 0
            avg_5 = int(re.search(r'5走平均\s*(\d+)', data).group(1)) if '5走平均' in data else 0

            candidates = []
            for j, (v, s, d, idx, b_idx) in enumerate(past_runs):
                if s != cur_s: continue # 面が違う場合は除外
                
                idx_val = int(idx)
                penalty = 0
                if j >= 2: # 3走前以前
                    is_outlier = (max_1y - avg_5 >= 10) and (idx_val == max_1y)
                    if is_outlier or (get_cat(s, d) != get_cat(cur_s, cur_d)): # 簡易区分不一致
                        penalty = -5
                candidates.append(idx_val + COURSE_MAP.get(s, {}).get(f"{v}{d}", 0) + penalty)

            # 万が一過去走が一つもヒットしなかった場合は最高値を参照
            ref = max(candidates) if candidates else max_1y
            
            if ref == 0:
                st.warning(f"馬番 {num} ({name}) の指数が読み取れませんでした。")
                continue

            linear = math.floor(60 + (ref - b_final))
            processed_horses.append({'num': int(num), 'name': name, 'ref': ref, 'linear': linear, 'kei': linear})

        # C. 救済・ソート・出力
        if processed_horses:
            df = pd.DataFrame(processed_horses).sort_values('num')
            # (ここに先ほどの救済ロジックを実装)
            # ...
            st.table(df) # プレビュー用
            st.text_area("貼り付け用データ (TSV)", df.to_csv(sep='\t', index=False))
        else:
            st.error("馬のデータが1頭も読み取れませんでした。")

    except Exception as e:
        st.error(f"解析失敗: {e}")
