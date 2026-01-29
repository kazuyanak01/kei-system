import streamlit as st
import pandas as pd
import re
import math

# --- 1. 固定マスタ (一切の変更なし) ---
COURSE_MAP = {
    '芝': {'中山1200':-2, '中山2500':-3, '中京1200':-2, '新潟1000':-5, '小倉1200':-3},
    'ダ': {'東京1300':1, '東京1600':-5, '東京2100':-2, '中山1200':-2, '中山1800':2, '中山2400':-3, '中山2500':-3, '中京1400':-3, '中京1900':-2, '京都1400':-2, '京都1900':-2, '阪神2000':-2, '新潟1200':-2, '新潟2500':-3, '小倉1000':-3, '小倉1700':1, '小倉2400':-3, '福島1700':1, '福島2400':-2, '札幌1000':1, '札幌2400':-2, '函館1000':1, '函館2400':-2}
}

def get_dist_cat(surface, dist):
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
    o, n = get_dist_cat(old_s, old_d), get_dist_cat(new_s, new_d)
    if new_s == '芝':
        if o in [1,2] and n in [3,4,5]: return True # 延長
        if o == 3 and n in [4,5]: return True # 延長
        if o == 5 and n != 5: return True # 短縮
    else: # ダート
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

# --- 2. ツールUI ---
st.set_page_config(page_title="KEI Parser Pro", layout="wide")
st.title("🐎 KEI能力評価エンジン (最終運用版)")

input_text = st.text_area("netkeibaのデータを貼り付けてください", height=300)

if st.button("KEI指数を算出"):
    if not input_text:
        st.warning("データを入力してください")
    else:
        try:
            # A. レース条件の抽出
            # ヘッダ領域から基準指数、会場、距離を特定
            header = input_text[:2000]
            b_raw = int(re.search(r'タイム指数\s*\n\s*(\d+)', header).group(1))
            venue = re.search(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', header).group(1)
            course_m = re.search(r'(芝|ダ)(\d+)m', header)
            cur_s, cur_d = course_m.groups()
            
            b_final = b_raw + (0 if "未勝利" in header else 5) + COURSE_MAP.get(cur_s, {}).get(f"{venue}{cur_d}", 0)
            
            st.info(f"今回の条件: {venue}{cur_s}{cur_d}m (B_final: {b_final})")

            # B. 馬ごとのパース
            # 馬番 + '--' を区切りとして分割
            horse_parts = re.split(r'(\d{1,2})\n\s*--\n', input_text)
            processed_list = []

            for i in range(1, len(horse_parts), 2):
                h_num = int(horse_parts[i])
                h_data = horse_parts[i+1]
                
                # 馬名：記号を飛ばして最初の単語
                lines = [l.strip() for l in h_data.split('\n') if l.strip()]
                h_name = "不明"
                for l in lines:
                    if any(m in l for m in ['◎','◯','▲','△','☆','消','✓']): continue
                    h_name = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館|芝|ダ)', l)[0].strip()
                    if h_name: break
                
                # 指数データ (地名+芝ダ+距離 ... ペース?+指数+馬場指数)
                # 順序はnetkeibaの並び（左から5走前、4走前...右端が前走）を考慮
                past_runs = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?\s+([SMH]?)\s*(\d+)\s*\(([-0-9]+)\)', h_data)
                
                # 統計値
                max_1y = int(re.search(r'最高\s*(\d+)', h_data).group(1)) if '最高' in h_data else 0
                avg_5 = int(re.search(r'5走平均\s*(\d+)', h_data).group(1)) if '5走平均' in h_data else 0

                candidates = []
                # past_runsの最後から2つが「前走」「2走前」
                total_runs = len(past_runs)
                for idx_in_list, (v, s, d, p, val, b_idx) in enumerate(past_runs):
                    # 前走からの位置を特定 (total_runs-1 が前走)
                    pos_from_latest = (total_runs - 1) - idx_in_list 
                    
                    val_int = int(val)
                    adj = COURSE_MAP.get(s, {}).get(f"{v}{d}", 0)
                    penalty = 0
                    
                    if pos_from_latest >= 2: # 3走前以前のみ判定
                        is_outlier = (max_1y - avg_5 >= 10) and (val_int == max_1y)
                        is_mismatch = check_mismatch(s, d, cur_s, cur_d)
                        if is_outlier or is_mismatch:
                            penalty = -5
                    
                    if s == cur_s: # 同一サーフェスのみ計算対象
                        candidates.append(val_int + adj + penalty)
                
                ref = max(candidates) if candidates else max_1y
                linear = math.floor(60 + (ref - b_final))
                processed_list.append({'num': h_num, 'name': h_name, 'ref': ref, 'linear': linear, 'kei': linear})

            # C. 救済と出力
            if processed_list:
                # 参照指数降順で救済判定
                processed_list.sort(key=lambda x: x['ref'], reverse=True)
                for i in range(1, len(processed_list)):
                    p, c = processed_list[i-1], processed_list[i]
                    if (p['ref'] - c['ref'] <= 1) and (get_rank(p['linear']) != get_rank(c['linear'])) and (p['linear'] - c['linear'] < 3):
                        c['kei'] = p['kei']
                
                # 馬番順で確定
                df = pd.DataFrame(processed_list).sort_values('num').reset_index(drop=True)
                df['rank'] = df['kei'].apply(get_rank)
                
                st.table(df[['num', 'name', 'ref', 'linear', 'kei', 'rank']])
                st.write("### スプレッドシート用 (TSV)")
                st.text_area("全選択してコピー", df[['num', 'name', 'ref', 'linear', 'kei', 'rank']].to_csv(sep='\t', index=False), height=200)
            else:
                st.error("馬のデータが見つかりません。")
        except Exception as e:
            st.error(f"エラー: {e}")
