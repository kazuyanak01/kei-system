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
        else: # ダート
            if d <= 1000: return 1
            if d <= 1200: return 2
            if d <= 1400: return 3
            if d <= 1600: return 4
            if d <= 1800: return 5
            if d <= 2100: return 6
            return 7
    except: return 0

def check_mismatch(old_s, old_d, new_s, new_d):
    o = get_cat(old_s, old_d)
    n = get_cat(new_s, new_d)
    if new_s == '芝':
        if o in [1,2] and n in [3,4,5]: return True
        if o == 3 and n in [4,5]: return True
        if o == 5 and n != 5: return True
    else:
        if o == 1 and n != 1: return True
        if o in [2,3] and n in [4,5,6,7]: return True
        if o in [6,7] and n not in [6,7]: return True
    return False

# --- アプリ画面設定 ---
st.set_page_config(page_title="KEI指数算出システム", layout="wide")
st.title("🐎 KEI能力評価エンジン (高耐久パース版)")

input_text = st.text_area("netkeibaのテキストデータを貼り付けてください", height=300)

if st.button("KEI指数を算出する"):
    if not input_text:
        st.warning("データを入力してください")
    else:
        try:
            # 1. 基準指数・レース条件抽出
            b_raw_match = re.search(r'タイム指数\s*\n\s*(\d+)', input_text)
            if not b_raw_match:
                b_raw_match = re.search(r'タイム指数[:：]\s*(\d+)', input_text)
            b_raw = int(b_raw_match.group(1)) if b_raw_match else 87
            
            venue_match = re.search(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', input_text)
            course_match = re.search(r'(芝|ダ)(\d+)m', input_text)
            if not (venue_match and course_match):
                st.error("レース情報（会場や距離）が読み取れませんでした。")
                st.stop()
            
            cur_v, cur_s, cur_d = venue_match.group(1), course_match.group(1), course_match.group(2)
            class_adj = 0 if "未勝利" in input_text else 5
            now_adj = COURSE_MAP.get(cur_s, {}).get(f"{cur_v}{cur_d}", 0)
            b_final = b_raw + class_adj + now_adj

            # 2. 馬データの分割
            parts = re.split(r'(\n\d{1,2}\s*\n\s*--)', input_text)
            processed_horses = []
            
            for i in range(1, len(parts), 2):
                num = re.search(r'\d+', parts[i]).group()
                data = parts[i+1]
                
                # 馬名抽出：記号を飛ばした最初の意味のある行
                lines = [l.strip() for l in data.split('\n') if l.strip()]
                name = "不明"
                for l in lines:
                    if any(m in l for m in ['◎','◯','▲','△','☆','消','✓','&#10003']): continue
                    if '--' in l: continue
                    name = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館|芝|ダ)', l)[0].strip()
                    break
                
                # 指数データ抽出 (ペース文字 [SMH]? を考慮)
                past_runs = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?\s+([SMH]?)\s*(\d+)\s*\(([-0-9]+)\)', data)
                
                max_1y = int(re.search(r'最高\s*(\d+)', data).group(1)) if '最高' in data else 0
                avg_5 = int(re.search(r'5走平均\s*(\d+)', data).group(1)) if '5走平均' in data else 0

                candidates = []
                for j, (v, s, d, p_char, idx, b_idx) in enumerate(past_runs):
                    if s != cur_s: continue 
                    idx_val = int(idx)
                    c_adj = COURSE_MAP.get(s, {}).get(f"{v}{d}", 0)
                    penalty = 0
                    if j >= 2: # 3走前以前
                        is_outlier = (max_1y - avg_5 >= 10) and (idx_val == max_1y)
                        if is_outlier or check_mismatch(s, d, cur_s, cur_d):
                            penalty = -5
                    candidates.append(idx_val + c_adj + penalty)
                
                ref = max(candidates) if candidates else max_1y
                linear = math.floor(60 + (ref - b_final))
                processed_horses.append({'num': int(num), 'name': name, 'ref': ref, 'linear': linear, 'kei': linear})

            # 3. 救済ロジック
            if processed_horses:
                def get_rank(s):
                    if s >= 70: return 'S'
                    elif s >= 65: return 'A+'
                    elif s >= 60: return 'A'
                    elif s >= 55: return 'B'
                    elif s >= 50: return 'C'
                    else: return 'D'

                processed_horses.sort(key=lambda x: x['ref'], reverse=True)
                for i in range(1, len(processed_horses)):
                    p, c = processed_horses[i-1], processed_horses[i]
                    if (p['ref'] - c['ref'] <= 1) and (get_rank(p['linear']) != get_rank(c['linear'])) and (p['linear'] - c['linear'] < 3):
                        c['kei'] = p['kei']

                df = pd.DataFrame(processed_horses).sort_values('num')
                df['rank'] = df['kei'].apply(get_rank)
                
                st.subheader(f"解析結果: {cur_v}{cur_s}{cur_d}m (B_final: {b_final})")
                st.table(df[['num', 'name', 'ref', 'linear', 'kei', 'rank']])
                
                st.write("### スプレッドシート貼り付け用データ (TSV)")
                tsv = df[['num', 'name', 'ref', 'linear', 'kei', 'rank']].to_csv(sep='\t', index=False)
                st.text_area("Copy and paste to Excel", tsv, height=200)
            else:
                st.error("馬のデータを読み取れませんでした
