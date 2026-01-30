import streamlit as st
import pandas as pd
import re
import math

# --- 1. 定数マスタ (物理固定 29地点) ---
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

# --- 2. 距離区分ロジック (芝5 / ダ7) ---
def get_dist_cat(surface, dist):
    try:
        d = int(dist)
        if surface == '芝':
            if d <= 1100: return 1 # 超短
            if d <= 1400: return 2 # スプ
            if d == 1600: return 3 # マイル
            if d <= 2500: return 4 # 中
            return 5 # 長
        else: # ダート
            if d <= 1000: return 1 # 超短
            if d <= 1200: return 2 # スプ
            if d <= 1400: return 3 # 短
            if d <= 1600: return 4 # マイル
            if d <= 1800: return 5 # 中
            if d <= 2100: return 6 # 中長
            return 7 # 長
    except: return 0

def check_mismatch(old_s, old_d, cur_s, cur_d):
    o, n = get_dist_cat(old_s, old_d), get_dist_cat(cur_s, cur_d)
    if cur_s == '芝':
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

st.set_page_config(page_title="KEI System Ultimate", layout="wide")
st.title("🐎 KEI能力評価エンジン (地獄の強化・運用確定版)")

input_text = st.text_area("netkeibaのデータを貼り付けてください", height=300)

if st.button("KEI指数を算出"):
    if not input_text:
        st.warning("データを入力してください")
    else:
        try:
            # A. レース条件の物理特定 (ハルシネーション防止)
            header_area = input_text[:5000]
            # タイム指数の直前周辺から基準値、会場、距離を抜く
            b_raw_m = re.search(r'タイム指数\s*\n\s*(\d+)', header_area)
            b_raw = int(b_raw_m.group(1)) if b_raw_m else 87
            
            # 会場は「12R」等の付近から探す
            venue_m = re.search(r'(\d+)R[\s\S]+?(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', header_area)
            cur_v = venue_m.group(2) if venue_m else "小倉"
            
            course_m = re.search(r'(芝|ダ)(\d+)m', header_area)
            cur_s, cur_d = course_m.groups()
            
            b_final = b_raw + (0 if "未勝利" in header_area else 5) + COURSE_MAP.get(cur_s, {}).get(f"{cur_v}{cur_d}", 0)
            st.success(f"条件確定: {cur_v}{cur_s}{cur_d}m / B_final: {b_final}")

            # B. 馬ごとの分割 ( -- を絶対境界にする)
            blocks = re.split(r'\n(\d{1,2})\n\s*--\n', input_text)
            processed_data = []
            
            for i in range(1, len(blocks), 2):
                h_num = int(blocks[i])
                content = blocks[i+1]
                
                # 馬名抽出 (地名が出るまでを馬名とする。サラダ対策)
                name_p = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', content)[0]
                # 記号を除去
                name_l = [l.strip() for l in name_p.split('\n') if l.strip() and not any(m in l for m in ['◎','◯','▲','△','☆','消','✓','&#10003'])]
                h_name = name_l[0] if name_l else "不明"

                # 統計
                max_1y = int(re.search(r'最高\s*(\d+)', content).group(1)) if '最高' in content else 0
                avg_5 = int(re.search(r'5走平均\s*(\d+)', content).group(1)) if '5走平均' in content else 0
                
                # 過去走 (Regex強化: スペース、記号を完全に許容)
                past_runs = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?\s*([SMH]?)\s*(\d+)\s*\(([-0-9]+)\)', content)
                
                cands = []
                total = len(past_runs)
                for j, (v, s, d, p, val, b_idx) in enumerate(past_runs):
                    if s != cur_s: continue # 面違い除外
                    
                    val_int = int(val)
                    adj = COURSE_MAP.get(s, {}).get(f"{v}{d}", 0)
                    penalty = 0
                    
                    # 【重要】近2走例外 (j が total-1, total-2 以外のみペナルティ検討)
                    if j < total - 2:
                        # 1. 異常値ペナルティ
                        is_outlier = (max_1y - avg_5 >= 10) and (val_int == max_1y)
                        # 2. 距離区分不一致ペナルティ
                        is_mismatch = check_mismatch(s, d, cur_s, cur_d)
                        
                        if is_outlier or is_mismatch:
                            penalty = -5
                    
                    cands.append(val_int + adj + penalty)
                
                # 算出
                ref = max(cands) if cands else max_1y
                linear = math.floor(60 + (ref - b_final))
                processed_data.append({'num': h_num, 'name': h_name, 'ref': ref, 'linear': linear, 'kei': linear})

            # C. 救済と最終整形
            if processed_data:
                # 参照指数降順で救済処理
                processed_data.sort(key=lambda x: x['ref'], reverse=True)
                for k in range(1, len(processed_data)):
                    p, c = processed_data[k-1], processed_data[k]
                    if (p['ref'] - c['ref'] <= 1) and (get_rank(p['linear']) != get_rank(c['linear'])) and (p['linear'] - c['linear'] < 3):
                        c['kei'] = p['kei']
                
                # 馬番順で出力
                final_df = pd.DataFrame(processed_data).sort_values('num').reset_index(drop=True)
                final_df['rank'] = final_df['kei'].apply(get_rank)
                
                st.table(final_df[['num', 'name', 'ref', 'linear', 'kei', 'rank']])
                st.text_area("スプレッドシート用 (TSV)", final_df[['num', 'name', 'ref', 'linear', 'kei', 'rank']].to_csv(sep='\t', index=False))
            else:
                st.error("馬データが見つかりません。")
        except Exception as e:
            st.error(f"解析エラー: {e}")
