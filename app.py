import streamlit as st
import pandas as pd
import re
import math

st.set_page_config(page_title="KEI指数算出システム", layout="wide")
st.title("🐎 KEI能力評価エンジン")

# --- 定数マスタ ---
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
    d = int(dist)
    if surface == '芝':
        if d <= 1100: return 1 # 超短
        if d <= 1400: return 2 # スプ
        if d == 1600: return 3 # マイル
        if d <= 2500: return 4 # 中
        return 5 # 長
    else: # ダート
        if d <= 1000: return 1
        if d <= 1200: return 2
        if d <= 1400: return 3
        if d <= 1600: return 4
        if d <= 1800: return 5
        if d <= 2100: return 6
        return 7

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

# --- UI ---
input_text = st.text_area("netkeibaのテキストデータを貼り付けてください", height=300)

if st.button("KEI指数を算出する"):
    try:
        # 1. 基準指数・レース条件抽出
        b_raw_match = re.search(r'タイム指数\s*\n(\d+)', input_text)
        if not b_raw_match:
            # 形式が違う場合の予備パース
            b_raw_match = re.search(r'タイム指数[:：]\s*(\d+)', input_text)
        
        b_raw = int(b_raw_match.group(1))
        class_adj = 0 if "未勝利" in input_text else 5
        race_info = re.search(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館).+?(芝|ダ)(\d+)m', input_text)
        cur_v, cur_s, cur_d = race_info.groups()
        now_adj = COURSE_MAP.get(cur_s, {}).get(f"{cur_v}{cur_d}", 0)
        b_final = b_raw + class_adj + now_adj

        # 2. 馬データ抽出
        horses = []
        # 馬番、馬名、過去成績ブロックを抽出
        horse_blocks = re.findall(r'(\d{1,2})\n\s*--\n.+?\n\s*--\n([^\n]+)\n(.*?)(?=\n\d{1,2}\n\s*--|\Z)', input_text, re.DOTALL)
        
        for num, name, past_text in horse_blocks:
            # 過去指数の抽出
            past_indices = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).+?(\d+)\s*\(([-0-9]+)\)', past_text)
            
            # 最大値と平均値の抽出
            max_1y_match = re.search(r'最高.+?(\d+)', past_text)
            avg_5_match = re.search(r'5走平均\s*(\d+)', past_text)
            
            max_1y = int(max_1y_match.group(1)) if max_1y_match else 0
            avg_5 = int(avg_5_match.group(1)) if avg_5_match else 0
            
            candidates = []
            for i, (v, s, d, idx, b_idx) in enumerate(past_indices):
                idx = int(idx)
                c_adj = COURSE_MAP.get(s, {}).get(f"{v}{d}", 0)
                penalty = 0
                if i >= 2: # 3走前以前
                    is_outlier = (max_1y - avg_5 >= 10) and (idx == max_1y)
                    is_mismatch = check_mismatch(s, d, cur_s, cur_d)
                    if is_outlier or is_mismatch:
                        penalty = -5
                candidates.append(idx + c_adj + penalty)
            
            ref = max(candidates) if candidates else max_1y
            linear = math.floor(60 + (ref - b_final))
            horses.append({'num': int(num), 'name': name, 'ref': ref, 'linear': linear, 'kei': linear})

        # 3. 救済ロジック
        def get_rank(s):
            if s >= 70: return 'S'
            if s >= 65: return 'A+'
            if s >= 60: return 'A'
            if s >= 55: return 'B'
            if s >= 50: return 'C'
            return 'D'

        if horses:
            horses.sort(key=lambda x: x['ref'], reverse=True)
            for i in range(1, len(horses)):
                p, c = horses[i-1], horses[i]
                if (p['ref'] - c['ref'] <= 1) and (get_rank(p['linear']) != get_rank(c['linear'])) and (p['linear'] - c['linear'] < 3):
                    c['kei'] = p['kei']

            # 4. 出力 (馬番順)
            res_df = pd.DataFrame(horses).sort_values('num')
            res_df['rank'] = res_df['kei'].apply(get_rank)
            
            st.subheader(f"解析結果 (B_final: {b_final})")
            st.table(res_df[['num', 'name', 'ref', 'linear', 'kei', 'rank']])
            st.success("結果をコピーしてスプレッドシートに貼り付けてください")
        else:
            st.warning("馬のデータが見つかりませんでした。テキストのコピー範囲を確認してください。")

    except Exception as e:
        st.error(f"エラーが発生しました。タイム指数マスターの画面全体をコピーしているか確認してください。: {e}")
